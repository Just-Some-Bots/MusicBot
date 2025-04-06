#!/usr/bin/env python3

import json
import os
import re
import sys
import textwrap
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Set

try:
    import curses
    from curses import textpad
except Exception as e1:
    if sys.platform.startswith("win"):
        import subprocess

        try:
            print("You need to install the windows-curses pip package.")
            print("Please wait while we try automatically...\n")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-U", "windows-curses"],
            )
            print("Trying to restart python / this tool...")
            subprocess.Popen(  # pylint: disable=consider-using-with
                [sys.executable] + sys.argv,
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
            )
        except Exception as e2:
            print(
                "\n\nSomething failed.\nYou need the pip package named: windows-curses\n"
                "Try to install it with pip and any python verion supported by MusicBot.\n\n"
            )
            raise e2 from e1
        sys.exit(1)
    raise e1

from musicbot import parse_write_base_arg, write_path
from musicbot.aliases import Aliases
from musicbot.bot import MusicBot
from musicbot.config import Config, ConfigOption
from musicbot.constants import (
    DATA_FILE_SERVERS,
    DATA_GUILD_FILE_OPTIONS,
    DEFAULT_COMMAND_ALIAS_FILE,
    DEFAULT_DATA_DIR,
    DEFAULT_OPTIONS_FILE,
    DEFAULT_PERMS_FILE,
)
from musicbot.permissions import Permissions

# Constants
KEY_ESCAPE = 27
KEY_FTAB = ord("\t")
KEY_RETURN = ord("\n")
KEYS_NAV_PREV = [curses.KEY_LEFT, curses.KEY_UP, curses.KEY_BTAB]
KEYS_NAV_NEXT = [curses.KEY_RIGHT, curses.KEY_DOWN, KEY_FTAB]
KEYS_ENTER = [KEY_RETURN, curses.KEY_ENTER]

# Mode constants are duplicated for easier reading in later code.
MODE_PICK_EDITOR = 0
MODE_PICK_ALIAS = 1
MODE_PICK_SERVER = 1
MODE_PICK_SECTION = 1
MODE_PICK_GROUP = 1
MODE_PICK_OPTION = 2
MODE_PICK_FIELD = 2
MODE_EDIT_OPTION = 3
MODE_EDIT_FIELD = 3

# Status codes for token verification.
VERIFY_SUCCESS = 0
VERIFY_FAILED_LIBRARY = 1
VERIFY_FAILED_API = 2
VERIFY_FAILED_MGR = 3


class ServerData:
    """
    Represents a single discord server's options.json data.
    """

    def __init__(self, guild_id: str, guild_name: Optional[str]) -> None:
        """
        Create a server data object and load in the options data.
        """
        self.id = guild_id
        if isinstance(guild_name, str):
            self.name = guild_name
        else:
            self.name = "[Unknown]"
        self.known = bool(guild_name)
        self.edited = False
        self.path = write_path(DEFAULT_DATA_DIR).joinpath(
            guild_id, DATA_GUILD_FILE_OPTIONS
        )
        self._options: Dict[str, Any] = {}
        self.load()

    @property
    def has_options(self) -> bool:
        """Test if the server has a data file."""
        return self.path.is_file()

    def __hash__(self) -> int:
        return int(self.id)

    def set(self, option: str, value: Any) -> None:
        """Set the server option value to the given value."""
        self._options[option] = value
        self.edited = True

    def get(self, option: str, default: str) -> Any:
        """Get a server option value or return the given default."""
        return self._options.get(option, default)

    def load(self) -> None:
        """Read the options.json file."""
        parsed: Dict[str, Any] = {}
        if not self.path.is_file():
            self._options = parsed
            return
        with open(self.path, "r", encoding="utf8") as fh:
            parsed = json.load(fh)
            if not isinstance(parsed, dict):
                raise TypeError("Parsed information must be of type Dict[str, Any]")
        self.edited = False
        self._options = parsed

    def save(self) -> None:
        """Save the options.json file"""
        with open(self.path, "w", encoding="utf8") as fh:
            json.dump(self._options, fh)
        self.edited = False


class ConfigAssistantTextSystem:
    """
    An ncurses application for messing with configs.
    CATs for short.
    """

    def __init__(self, stdscr: curses.window) -> None:
        """
        The CATS initializer which starts CATS.
        Should be called from curses.wrapper()
        """

        self.scr = stdscr
        self.win = curses.newwin(1, 1, 0, 0)

        # turn off the cursor
        curses.curs_set(0)
        # set escape delay to 100 ms, if possible.
        # on some versions of windows-curses this seems to be missing.
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(100)
        # Initialize colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(10, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(11, curses.COLOR_RED, curses.COLOR_WHITE)
        curses.init_pair(12, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(13, curses.COLOR_YELLOW, curses.COLOR_WHITE)
        curses.init_pair(14, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(15, curses.COLOR_BLUE, curses.COLOR_WHITE)

        # set up editor selection and mode vars.
        self.edit_error_msg = ""
        self.edit_mode = MODE_PICK_EDITOR
        self.sct_selno = 0
        self.opt_selno = 0

        # Managers / buffers for editor data.
        self.mgr_alias: Optional[Aliases] = None
        self.mgr_perms: Optional[Permissions] = None
        self.mgr_opts: Optional[Config] = None
        self.mgr_srvs: List[ServerData] = self._get_servers()
        self.edited_opts: Set[ConfigOption] = set()
        self.edited_perms: Set[ConfigOption] = set()
        self.edited_aliases: Set[str] = set()
        self.token_status: int = 0

        # store valid commands from musicbot.
        self.top_commands: Set[str] = set()
        self.sub_commands: DefaultDict[str, Set[str]] = defaultdict(set)
        self.sub_cmd_pattern = re.compile(r"^{prefix}[a-z]+\s{1}([a-z0-9]+)", re.I)
        self._get_natural_commands()

        self.main_screen()

    def _get_natural_commands(self) -> None:
        """
        Loops over MusicBot's attributes and extracts a set of commands
        which are avaialble in `self.top_commands`.
        """
        for attr in dir(MusicBot):
            if attr.startswith("cmd_"):
                cmd_name = attr.replace("cmd_", "")
                # attempt to get sub-commands from usage strings.
                cmd = getattr(MusicBot, attr, None)
                if hasattr(cmd, "admin_only") or hasattr(cmd, "dev_cmd"):
                    continue
                if cmd:
                    self._get_sub_commands(cmd)
                    self.top_commands.add(cmd_name)

    def _get_sub_commands(self, cmd: Callable[..., Any]) -> None:
        """
        Takes a valid command attribute from musicbot then extracts possible
        sub-commands from the usage stirngs.
        The results are available in self.sub_commands as a dictionary of sets.
        """
        usage = getattr(cmd, "help_usage", [])
        cmd_name = cmd.__name__.replace("cmd_", "")
        for ustr in usage:
            ulines = ustr.split("\n")
            for uline in ulines:
                m = self.sub_cmd_pattern.match(uline)
                if m:
                    self.sub_commands[cmd_name].add(m.group(1))

    def _get_servers(self) -> List[ServerData]:
        """Build a list of possible servers from servers.txt and data files."""
        data_path = write_path(DEFAULT_DATA_DIR)
        servers_path = data_path.joinpath(DATA_FILE_SERVERS)
        opt_pattern = "*/"

        # known servers have entries in data/server txt
        srvs: Dict[str, ServerData] = {}
        names: Dict[str, str] = {}
        if servers_path.is_file():
            slines = servers_path.read_text(encoding="utf8").split("\n")
            for line in slines:
                line = line.strip()
                if not line:
                    continue

                bits = line.split(": ", maxsplit=1)
                gid = bits[0]
                sname = bits[1]
                names[gid] = sname
                srvs[gid] = ServerData(gid, sname)

        for path in data_path.glob(opt_pattern):
            if not path.is_dir():
                continue
            gid = path.name
            name: Optional[str] = names.get(gid, None)
            srvs[gid] = ServerData(gid, name)

        return list(srvs.values())

    def _verify_bot_token(self) -> int:
        """Create a discord client which immediately closes, to test tokens."""
        try:
            import discord
        except Exception:  # pylint: disable=broad-exception-caught
            return VERIFY_FAILED_LIBRARY

        if self.mgr_opts is None:
            return VERIFY_FAILED_MGR

        try:
            client = discord.Client(intents=discord.Intents.default())

            @client.event
            async def on_ready() -> None:
                await client.close()

            @client.event
            async def on_error() -> None:
                await client.close()

            client.run(
                self.mgr_opts._login_token,  # pylint: disable=protected-access
                log_handler=None,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return VERIFY_FAILED_API
        return VERIFY_SUCCESS

    def _remake_subwindow(self) -> None:
        """(re) create the main sub-window using current screen size."""
        self.win = curses.newwin(
            max(1, curses.LINES - 3),  # pylint: disable=no-member
            curses.COLS,  # pylint: disable=no-member
            min(3, curses.LINES),  # pylint: disable=no-member
            0,
        )

    def _process_resize(self) -> None:
        """Calls common resize functions to update curses screen and window sizes."""
        ny, nx = self.scr.getmaxyx()
        curses.resize_term(ny, nx)
        curses.update_lines_cols()
        self.win.resize(max(1, ny - 3), nx)
        self.scr.refresh()
        self.win.refresh()

    def winaddstr(self, y: int, x: int, data: str, flags: Optional[Any] = None) -> None:
        """Wrapper for self.win.adddstr() which enforces bounds to prevent crashes."""
        max_y, max_x = self.win.getmaxyx()
        max_y -= 1
        max_x -= 1
        by = min(y, max_y)
        bx = min(x, max_x)
        data = data[: max(0, max_x - x)]
        if flags is not None:
            self.win.addstr(by, bx, data, flags)
        else:
            self.win.addstr(by, bx, data)

    def get_text_input(
        self, lines: int, cols: int, y: int, x: int, value: str = ""
    ) -> str:
        """
        Create a single-line text input with optional value for editing.
        Value is returned with leading and trailing space removed.
        """
        curses.curs_set(1)
        lines = min(lines, curses.LINES - 1 - y)  # pylint: disable=no-member
        cols = min(cols, curses.COLS - 1 - x)  # pylint: disable=no-member
        twin = curses.newwin(lines, cols, y, x)
        twin.addstr(0, 0, value)
        tpad = textpad.Textbox(twin, insert_mode=True)
        tpad.stripspaces = False
        t = tpad.edit().strip()
        curses.curs_set(0)
        return t

    def do_key_nav(
        self,
        max_scts: int,
        max_opts: int,
        save_callback: Callable[..., None],
        reload_callback: Callable[..., None],
        remove_callback: Optional[Callable[..., None]] = None,
        add_callback: Optional[Callable[..., None]] = None,
    ) -> bool:
        """
        Handle user inputs via curses key input method.
        This usually gets skipped when text-input is active.
        """
        key = self.scr.getch()

        def empty() -> None:
            return

        if remove_callback is None:
            remove_callback = empty
        if add_callback is None:
            add_callback = empty

        # select previous
        if key in KEYS_NAV_PREV:
            self.edit_error_msg = ""
            if self.edit_mode == MODE_PICK_OPTION:
                if self.opt_selno > 0:
                    self.opt_selno -= 1
                else:
                    self.opt_selno = max_opts
            elif self.edit_mode == MODE_PICK_SECTION:
                if self.sct_selno > 0:
                    self.sct_selno -= 1
                else:
                    self.sct_selno = max_scts

        # select next
        elif key in KEYS_NAV_NEXT:
            self.edit_error_msg = ""
            if self.edit_mode == MODE_PICK_OPTION:
                if self.opt_selno < max_opts:
                    self.opt_selno += 1
                else:
                    self.opt_selno = 0
            elif self.edit_mode == MODE_PICK_SECTION:
                if self.sct_selno < max_scts:
                    self.sct_selno += 1
                else:
                    self.sct_selno = 0

        # confirm selection
        elif key in KEYS_ENTER:
            self.edit_error_msg = ""
            # picking aliases
            if self.edit_mode == MODE_PICK_SECTION:
                self.edit_mode = MODE_PICK_OPTION
                self.opt_selno = 0
            # picking alias component fields
            elif self.edit_mode == MODE_PICK_OPTION:
                self.edit_mode = MODE_EDIT_OPTION

        # Add data
        elif key == curses.KEY_F8:
            add_callback()

        # Remove data
        elif key == curses.KEY_F7:
            remove_callback()

        # Reload data
        elif key == curses.KEY_F5:
            reload_callback()

        # Save data
        elif key == curses.KEY_F2:
            save_callback()

        # Go back
        elif key == KEY_ESCAPE:
            if self.edit_mode == MODE_PICK_SECTION:
                self.opt_selno = 0
                self.sct_selno = 0
                return True
            if self.edit_mode == MODE_PICK_OPTION:
                self.edit_mode = MODE_PICK_SECTION
                self.opt_selno = 0

        # handle resize
        elif key == curses.KEY_RESIZE:
            self._process_resize()

        return False

    def select_cmd_perms(self, cur_val: Set[str]) -> str:
        """Special input method use for Permissions command list options."""
        perms = list(self.top_commands)
        max_px = 0
        for cmd, subs in self.sub_commands.items():
            for sub in subs:
                perm = f"{cmd}_{sub}"
                perms.append(perm)
                max_px = max(max_px, len(perm))

        perms = sorted(perms)
        selno = 0
        selected: Set[str] = set(cur_val)

        while True:
            maxy, maxx = self.scr.getmaxyx()
            maxy -= 1
            maxx -= 1
            padx = 6
            midx = (maxx) // 2
            midwx = midx - ((max_px + padx) // 2)
            win = curses.newwin(max(1, maxy - 3), max_px + padx, min(3, maxy), midwx)
            wmaxy, _wmaxx = win.getmaxyx()
            win.clear()
            win.refresh()
            self.scr.refresh()
            win.box()

            if wmaxy > 1:
                win.addstr(
                    min(1, maxy), min(1, maxx), "Select Commands:", curses.A_BOLD
                )

            hud = "[SPACE] Select  [ENTER] Confirm Selected  [ESC] Go Back"
            self.scr.addstr(
                max(0, maxy),
                0,
                hud.center(maxx)[:maxx],
                curses.color_pair(1) | curses.A_BOLD,
            )

            viewno = max(0, (selno - (maxy - 6)) + 1)
            view = list(perms)[viewno : viewno + (maxy - 6)]
            for i, perm in enumerate(view):
                flags = 0
                if i + viewno == selno:
                    flags = curses.color_pair(1)
                if perm in selected:
                    win.addstr(min(i + 2, maxy), 1, f"[x] {perm}", flags)
                else:
                    win.addstr(min(i + 2, maxy), 1, f"[ ] {perm}", flags)

            win.refresh()
            self.scr.refresh()

            key = self.scr.getch()
            if key == KEY_ESCAPE:
                return " ".join(cur_val)
            if key in KEYS_ENTER:
                return " ".join(sorted(list(selected)))
            if key in KEYS_NAV_NEXT:
                if selno < len(perms) - 1:
                    selno += 1
                else:
                    selno = 0
            elif key in KEYS_NAV_PREV:
                if selno > 0:
                    selno -= 1
                else:
                    selno = len(perms) - 1
            elif key == curses.KEY_RESIZE:
                self._process_resize()
            elif key == ord(" "):
                perm = list(perms)[selno]
                if perm in selected:
                    selected.discard(perm)
                else:
                    selected.add(perm)
        return ""

    def main_screen(self) -> None:
        """Process the CATS main menu screen."""
        # Create a list of config types to manage.
        config_files = {
            "Options": "Manage settings saved in options.ini file.",
            "Permissions": "Manage groups saved in permissions.ini file.",
            "Aliases": "Manage aliases saved in aliases.json file.",
            "Servers": "Manage per-server settings saved in data files.",
        }
        config_types = list(config_files.keys())
        config_edited = [False for _ in config_types]
        config_sel = 0
        selected = False

        # update/input loop for the main screen.
        while True:
            # get screen size and adjust them for use in layout logic.
            max_y, max_x = self.scr.getmaxyx()
            max_y -= 1
            max_x -= 1

            # reset everything on the screen in prep for output.
            self.scr.clear()
            self.scr.addstr(0, 0, "Select configuration to edit:", curses.A_BOLD)

            # build config selection at top.
            c = 2
            line_offset = 0
            xlimit = max_x - c
            for i, option in enumerate(config_types):
                opt_str = f" {option} "
                opt_desc = config_files[config_types[config_sel]]

                # prevent printing the option if the screen is too narrow.
                if c >= xlimit or c + len(opt_str) >= xlimit:
                    break

                # if the screen is too narrow for the description, add a line so it can fold.
                if len(opt_desc) > max_x:
                    line_offset = 1

                # determine how to highlight the option
                flags = 0
                if i == config_sel:
                    flags = curses.color_pair(1)
                    if config_edited[i]:
                        flags = curses.color_pair(15)
                    self.scr.addstr(1, c, opt_str[:xlimit], flags)
                else:
                    if config_edited[i]:
                        flags = curses.color_pair(14)
                    self.scr.addstr(1, c, opt_str[:xlimit], flags)
                c += len(opt_str)

                # tell the user about unsaved edits for the selected option.
                if config_edited[i]:
                    self.scr.addstr(
                        min(4 + line_offset, max_y),
                        2,
                        "You have unsaved edits!"[: max_x - 2],
                        curses.color_pair(14),
                    )

                # disable server options if no servers are found.
                elif config_sel == 3 and not self.mgr_srvs:
                    self.scr.addstr(
                        min(4 + line_offset, max_y),
                        2,
                        "No servers available to edit!"[: max_x - 2],
                        curses.color_pair(12),
                    )

            # draw the horizontal line and selected sections description.
            self.scr.hline(min(2, max_y), 0, curses.ACS_HLINE, max_x)
            self.scr.addstr(min(3, max_y), 2, opt_desc[: max_x - 2])

            # Draw the HUD
            hud = " [ESC] Quit  [ENTER] Confirm  [ARROW KEYS] Navigate"
            pad = max(0, max_x - len(hud))
            hud += " " * pad
            self.scr.addstr(max_y, 0, hud[:max_x], curses.color_pair(1) | curses.A_BOLD)

            # Get user input
            key = self.scr.getch()
            if key in KEYS_NAV_PREV:
                if config_sel > 0:
                    config_sel -= 1
                else:
                    config_sel = len(config_types) - 1
            elif key in KEYS_NAV_NEXT:
                if config_sel < len(config_types) - 1:
                    config_sel += 1
                else:
                    config_sel = 0
            elif key in KEYS_ENTER and not selected:
                selected = True
            elif key == KEY_ESCAPE:
                selected = False
                if any(x for x in config_edited):
                    self.scr.addstr(
                        min(4, max_y),
                        min(2, max_x),
                        "You have unsaved edits!",
                        curses.color_pair(10),
                    )
                    self.scr.addstr(
                        min(5, max_y),
                        min(2, max_x),
                        "Press [ESC] again to exit anyway.",
                        curses.color_pair(10) | curses.A_BOLD,
                    )
                    key = self.scr.getch()
                    if key == KEY_ESCAPE:
                        break
                else:
                    break
            elif key == curses.KEY_RESIZE:
                self._process_resize()

            if selected:
                # enter Options editor
                if config_sel == 0:
                    self.edit_mode = MODE_PICK_SECTION
                    config_edited[0] = self.config_options()
                    selected = False

                # enter Permissions editor
                elif config_sel == 1:
                    self.edit_mode = MODE_PICK_GROUP
                    config_edited[1] = self.config_permissions()
                    selected = False

                # enter Aliases editor
                elif config_sel == 2:
                    self.edit_mode = MODE_PICK_ALIAS
                    config_edited[2] = self.config_aliases()
                    selected = False

                # enter Server options editor.
                elif config_sel == 3 and self.mgr_srvs:
                    self.edit_mode = MODE_PICK_SERVER
                    config_edited[3] = self.config_servers()
                    selected = False
                else:
                    selected = False

            self.scr.refresh()

    def config_options(self) -> bool:
        """Run CATS in options editing mode."""
        if not self.mgr_opts:
            self.mgr_opts = Config(write_path(DEFAULT_OPTIONS_FILE))
        sections = self.mgr_opts.parser.sections()

        edit_buffer = ""

        missing_options: Dict[str, List[str]] = defaultdict(list)
        for mopt in self.mgr_opts.register.ini_missing_options:
            missing_options[mopt.section].append(mopt.option)

        def save_callback() -> None:
            eopts = list(self.edited_opts)
            if not self.mgr_opts:
                return
            for eopt in eopts:
                if self.mgr_opts.save_option(eopt):
                    self.edited_opts.discard(eopt)

        def reload_callback() -> None:
            nonlocal sections
            self.mgr_opts = Config(write_path(DEFAULT_OPTIONS_FILE))
            sections = self.mgr_opts.parser.sections()
            self.edited_opts.clear()
            missing_options.clear()
            for mopt in self.mgr_opts.register.ini_missing_options:
                missing_options[mopt.section].append(mopt.option)

        while True:
            # setup the window for this frame.
            self._remake_subwindow()
            max_y, max_x = self.win.getmaxyx()
            max_y -= 1
            max_x -= 1
            self.win.clear()

            # update selected section
            selected_sct: str = sections[self.sct_selno]

            # Layout window.
            self.win.hline(min(2, max_y), 0, curses.ACS_HLINE, max_x)
            if max_x > 30:
                self.win.vline(min(2, max_y), min(30, max_x), curses.ACS_VLINE, max_y)
                self.win.addch(min(2, max_y), min(30, max_x), curses.ACS_TTEE)
            if self.edit_error_msg:
                self.winaddstr(0, 1, self.edit_error_msg, curses.color_pair(12))
            else:
                self.winaddstr(0, 1, "Select a section and option to edit.")
            self.winaddstr(1, 1, "Section:", curses.A_BOLD)
            self.winaddstr(1, 10, "[", curses.A_DIM)
            if self.edit_mode == MODE_PICK_SECTION:
                self.winaddstr(1, 11, selected_sct, curses.color_pair(1))
            else:
                self.winaddstr(1, 11, selected_sct)
            self.winaddstr(1, 11 + len(selected_sct), "]", curses.A_DIM)

            # build options from the above selected section
            options = (
                self.mgr_opts.parser.options(selected_sct)
                + missing_options[selected_sct]
            )
            selected_opt = self.mgr_opts.register.get_config_option(
                selected_sct, options[self.opt_selno]
            )
            opt_viewno = max(0, (self.opt_selno - (max_y - 2)) + 1)
            visopts = options[opt_viewno : opt_viewno + (max_y - 2)]
            cnf_opt: Optional[ConfigOption] = None
            for i, opt in enumerate(visopts):
                cnf_opt = self.mgr_opts.register.get_config_option(selected_sct, opt)
                if (
                    i + opt_viewno == self.opt_selno
                    and self.edit_mode == MODE_PICK_OPTION
                ):
                    flags = curses.color_pair(1)
                    # If register returns None, the option does not exist.
                    if cnf_opt is None:
                        flags = curses.color_pair(11)
                    if cnf_opt in self.edited_opts:
                        flags = curses.color_pair(15)
                    # If opt is listed in missing_options, mark it so.
                    elif opt in missing_options[selected_sct]:
                        flags = curses.color_pair(13)
                    self.winaddstr(i + 3, 0, f" {opt[:28]} ", flags)
                else:
                    flags = 0
                    if cnf_opt is None:
                        flags = curses.color_pair(10)
                    if cnf_opt in self.edited_opts:
                        flags = curses.color_pair(14)
                    elif opt in missing_options[selected_sct]:
                        flags = curses.color_pair(12)
                    self.winaddstr(i + 3, 0, f" {opt[:28]} ", flags)

            # build info for selected option.
            if selected_opt:
                max_desc_x = max_x - 34
                # vals = mgr.register.get_values(selected_opt)
                comment = selected_opt.comment
                if selected_opt.comment_args:
                    comment %= selected_opt.comment_args
                comment_lines = []
                for line in comment.split("\n"):
                    if len(line) > max_desc_x:
                        ls = textwrap.wrap(line, width=max(1, max_desc_x))
                        comment_lines += ls
                    else:
                        comment_lines.append(line)

                lbl_option = "Option:"
                lbl_default = "Default Setting:"
                lbl_current = "Current Setting:"
                lbl_desc = "Description:"

                # option name
                self.winaddstr(3, 31, lbl_option, curses.A_BOLD)
                self.winaddstr(3, 32 + len(lbl_option), selected_opt.option)

                # default value
                dval = self.mgr_opts.register.to_ini(selected_opt, use_default=True)
                self.winaddstr(4, 31, lbl_default, curses.A_BOLD)
                self.winaddstr(4, 32 + len(lbl_default), dval)

                # current setting
                cval = self.mgr_opts.register.to_ini(selected_opt)
                self.winaddstr(5, 31, lbl_current, curses.A_BOLD)
                if selected_opt.option in missing_options[selected_sct]:
                    self.winaddstr(
                        5,
                        33 + len(lbl_current),
                        "This option is missing from your INI file.",
                        curses.color_pair(12),
                    )
                if selected_opt.option == "Token" and self.token_status:
                    if self.token_status == VERIFY_FAILED_API:
                        self.winaddstr(
                            5,
                            33 + len(lbl_current),
                            "ERROR: Token failed to log in!",
                            curses.color_pair(12),
                        )
                    elif self.token_status == VERIFY_FAILED_LIBRARY:
                        self.winaddstr(
                            5,
                            33 + len(lbl_current),
                            f"WARNING: Cannot verify, internal error {self.token_status}",
                            curses.color_pair(12),
                        )
                cflags = 0
                if len(cval) >= 199:
                    cflags = curses.color_pair(12)
                if len(cval) <= max_desc_x:
                    self.winaddstr(6, 33, cval, cflags)
                    last_y = 7
                else:
                    cval_lines = textwrap.wrap(cval, width=max(1, max_desc_x))
                    for i, line in enumerate(cval_lines):
                        y = 6 + i
                        self.winaddstr(y, 33, line, cflags)
                        last_y = y + 1

                # description
                self.winaddstr(last_y + 1, 31, lbl_desc, curses.A_BOLD)
                for i, line in enumerate(comment_lines):
                    yline = last_y + 2 + i
                    if yline >= max_y:
                        continue
                    self.winaddstr(yline, 33, line)

            # display a message for non-existing options.
            else:
                self.winaddstr(4, 33, "This option is invalid.", curses.A_BOLD)
                self.winaddstr(5, 33, "It can be removed from your INI file.")

            # Draw HUD
            hud = " [F2] Save  [F5] Reload  [ESC] Go Back"
            pad = max_x - len(hud) - 31
            hud += " " * pad
            self.winaddstr(max_y, 31, hud, curses.color_pair(1) | curses.A_BOLD)

            self.win.refresh()

            # handle getting the edited string.
            edit_buffer = ""
            if self.edit_mode == MODE_EDIT_OPTION:
                if selected_opt is None:
                    self.winaddstr(
                        6, 33, "You cannot edit this option.", curses.color_pair(10)
                    )
                    self.edit_mode = MODE_PICK_OPTION
                else:
                    # TODO: Maybe add ConfigOption var for input length.
                    edit_buffer = self.get_text_input(1, 200, 9, 33)
                    last_ini_val = self.mgr_opts.register.to_ini(selected_opt)
                    self.edit_mode = MODE_PICK_OPTION
                    self.edit_error_msg = ""
                    no_error = self.mgr_opts.update_option(selected_opt, edit_buffer)
                    cur_ini_val = self.mgr_opts.register.to_ini(selected_opt)
                    if not no_error or cur_ini_val == last_ini_val:
                        self.edit_error_msg = (
                            f"The option was not updated: {selected_opt.option}"
                        )
                    else:
                        self.edited_opts.add(selected_opt)
                        if selected_opt.option == "Token":
                            self.token_status = self._verify_bot_token()

            self.win.refresh()

            # get this frame's key code input, if we didn't just leave edit mode.
            if not edit_buffer:
                goback = self.do_key_nav(
                    len(sections) - 1,
                    len(options) - 1,
                    save_callback,
                    reload_callback,
                )
                if goback:
                    break

        return bool(self.edited_opts)

    def config_permissions(self) -> bool:
        """Run CATS in Permissions editing mode."""
        if not self.mgr_perms:
            self.mgr_perms = Permissions(write_path(DEFAULT_PERMS_FILE))

        groups = self.mgr_perms.config.sections()

        selected_group: str = ""
        selected_opt: Optional[ConfigOption] = None
        edit_buffer: str = ""

        missing_options: Dict[str, List[str]] = defaultdict(list)
        for mopt in self.mgr_perms.register.ini_missing_options:
            missing_options[mopt.section].append(mopt.option)

        def save_callback() -> None:
            if self.mgr_perms is None:
                return
            saved_groups: Set[str] = set()
            opts = list(self.edited_perms)
            for eopt in opts:
                if eopt.section not in saved_groups:
                    self.mgr_perms.save_group(eopt.section)
                self.edited_perms.discard(eopt)
            reload_callback()

        def reload_callback() -> None:
            nonlocal groups
            self.mgr_perms = Permissions(write_path(DEFAULT_PERMS_FILE))
            groups = self.mgr_perms.config.sections()
            self.edited_perms.clear()
            missing_options.clear()
            for mopt in self.mgr_perms.register.ini_missing_options:
                missing_options[mopt.section].append(mopt.option)
            if self.sct_selno >= len(groups):
                self.sct_selno = 0

        def remove_callback() -> None:
            nonlocal selected_opt  # noqa: F824
            if self.mgr_perms is None or selected_opt is None:
                return
            self.mgr_perms.remove_group(selected_opt.section)
            self.edited_perms.add(selected_opt)

        def add_callback() -> None:
            nonlocal groups  # noqa: F824
            if not self.mgr_perms:
                return
            self.win.clear()
            self.winaddstr(0, 1, "Enter a name for the new group:", curses.A_BOLD)
            self.winaddstr(1, 1, " " * (max_x - 2))
            self.win.refresh()
            new_name = self.get_text_input(1, 40, 4, 1)
            self.mgr_perms.add_group(new_name)
            self.mgr_perms.save_group(new_name)
            reload_callback()
            self.sct_selno = groups.index(new_name)

        while True:
            # setup the window for this frame.
            self._remake_subwindow()
            max_y, max_x = self.win.getmaxyx()
            max_y -= 1
            max_x -= 1
            self.win.clear()

            # update selected section
            selected_group = groups[self.sct_selno]

            # Layout window.
            self.win.hline(min(2, max_y), 0, curses.ACS_HLINE, max_x)
            if max_x > 30:
                self.win.vline(min(2, max_y), min(30, max_x), curses.ACS_VLINE, max_y)
                self.win.addch(min(2, max_y), min(30, max_x), curses.ACS_TTEE)
            if self.edit_error_msg:
                self.winaddstr(0, 1, self.edit_error_msg, curses.color_pair(12))
            else:
                self.winaddstr(0, 1, "Select a group and option to edit.")
            self.winaddstr(1, 1, "Group:", curses.A_BOLD)
            self.winaddstr(1, 10, "[", curses.A_DIM)
            if self.edit_mode == MODE_PICK_SECTION:
                self.winaddstr(1, 11, selected_group, curses.color_pair(1))
            else:
                self.winaddstr(1, 11, selected_group)
            self.winaddstr(1, 11 + len(selected_group), "]", curses.A_DIM)

            # build options from the above selected section
            options = (
                self.mgr_perms.config.options(selected_group)
                + missing_options[selected_group]
            )
            selected_opt = self.mgr_perms.register.get_config_option(
                selected_group, options[self.opt_selno]
            )
            opt_viewno = max(0, (self.opt_selno - (max_y - 2)) + 1)
            visopts = options[opt_viewno : opt_viewno + (max_y - 2)]
            cnf_opt: Optional[ConfigOption] = None
            for i, opt in enumerate(visopts):
                cnf_opt = self.mgr_perms.register.get_config_option(selected_group, opt)
                if (
                    i + opt_viewno == self.opt_selno
                    and self.edit_mode == MODE_PICK_OPTION
                ):
                    flags = curses.color_pair(1)
                    # If register returns None, the option does not exist.
                    if cnf_opt is None:
                        flags = curses.color_pair(11)
                    if cnf_opt in self.edited_perms:
                        flags = curses.color_pair(15)
                    self.winaddstr(i + 3, 0, f" {opt[:28]} ", flags)
                else:
                    flags = 0
                    if cnf_opt is None:
                        flags = curses.color_pair(10)
                    if cnf_opt in self.edited_perms:
                        flags = curses.color_pair(14)
                    self.winaddstr(i + 3, 0, f" {opt[:28]} ", flags)

            # build info for selected option.
            if selected_opt:
                max_desc_x = max_x - 34
                max_opt_x = max_desc_x
                # vals = mgr.register.get_values(selected_opt)
                comment = selected_opt.comment
                if selected_opt.comment_args:
                    comment %= selected_opt.comment_args
                comment_lines = []
                for line in comment.split("\n"):
                    if len(line) > max_desc_x:
                        ls = textwrap.wrap(line, width=max(1, max_desc_x))
                        comment_lines += ls
                    else:
                        comment_lines.append(line)

                lbl_option = "Option:"
                lbl_default = "Default Setting:"
                lbl_current = "Current Setting:"
                lbl_desc = "Description:"

                # option name
                self.winaddstr(3, 31, lbl_option, curses.A_BOLD)
                self.winaddstr(3, 32 + len(lbl_option), selected_opt.option)

                # default value
                dval = self.mgr_perms.register.to_ini(selected_opt, use_default=True)
                self.winaddstr(4, 31, lbl_default, curses.A_BOLD)
                self.winaddstr(4, 32 + len(lbl_default), dval)

                # current setting
                cval = self.mgr_perms.register.to_ini(selected_opt)
                self.winaddstr(5, 31, lbl_current, curses.A_BOLD)
                cflags = 0
                if len(cval) >= 199:
                    cflags = curses.color_pair(12)
                if len(cval) <= max_opt_x:
                    self.winaddstr(6, 33, cval, cflags)
                    last_y = 7
                else:
                    cval_lines = textwrap.wrap(cval, width=max(1, max_opt_x))
                    for i, line in enumerate(cval_lines):
                        y = 6 + i
                        self.winaddstr(y, 33, line, cflags)
                        last_y = y + 1

                # description
                self.winaddstr(last_y + 1, 31, lbl_desc, curses.A_BOLD)
                for i, line in enumerate(comment_lines):
                    self.winaddstr(last_y + 2 + i, 33, line)

            # display a message for non-existing options.
            else:
                self.winaddstr(4, 33, "This option is invalid.", curses.A_BOLD)
                self.winaddstr(5, 33, "It can be removed from your INI file.")

            # Show HUD
            hud = " [F2] Save  [F5] Reload  [F7] Remove Group  [F8] Add Group  [ESC] Go Back"
            pad = max_x - len(hud) - 31
            hud += " " * pad
            self.winaddstr(max_y, 31, hud, curses.color_pair(1) | curses.A_BOLD)

            self.win.refresh()

            # handle getting the edited string.
            edit_buffer = ""
            if self.edit_mode == MODE_EDIT_OPTION:
                if selected_opt is None:
                    self.winaddstr(
                        6, 33, "You cannot edit this option.", curses.color_pair(10)
                    )
                    self.edit_mode = MODE_PICK_OPTION
                else:
                    rawval = self.mgr_perms.register.get_values(selected_opt)[0]
                    if selected_opt.option in [
                        "CommandWhitelist",
                        "CommandBlacklist",
                    ]:
                        edit_buffer = self.select_cmd_perms(rawval)  # type: ignore[arg-type]
                        # Transform empty selection into a "truthy" value.
                        if edit_buffer == "":
                            edit_buffer = " "
                    else:
                        # TODO: Maybe add ConfigOption var for input length.
                        edit_buffer = self.get_text_input(1, 200, 9, 33, cval)

                    last_ini_val = self.mgr_perms.register.to_ini(selected_opt)
                    self.edit_mode = MODE_PICK_OPTION
                    self.edit_error_msg = ""
                    no_error = self.mgr_perms.update_option(selected_opt, edit_buffer)
                    cur_ini_val = self.mgr_perms.register.to_ini(selected_opt)
                    if not no_error or cur_ini_val == last_ini_val:
                        self.edit_error_msg = (
                            f"The option was not updated: {selected_opt.option}"
                        )
                    else:
                        self.edited_perms.add(selected_opt)

            self.win.refresh()

            # get this frame's key code input, if we didn't just leave edit mode.
            if not edit_buffer:
                goback = self.do_key_nav(
                    len(groups) - 1,
                    len(options) - 1,
                    save_callback,
                    reload_callback,
                    remove_callback,
                    add_callback,
                )
                if goback:
                    break

        return bool(self.edited_perms)

    def config_aliases(self) -> bool:
        """Run CATS in Alias editing mode."""
        if not self.mgr_alias:
            self.mgr_alias = Aliases(write_path(DEFAULT_COMMAND_ALIAS_FILE), [])

        # Set up vars and selection list.
        aliases = []
        edit_buffer = ""
        new_alias_name = ""

        def get_alias_list(mgr: Aliases) -> List[str]:
            return ["[New]"] + sorted(mgr.aliases.keys())

        def save_callback() -> None:
            if self.mgr_alias:
                self.mgr_alias.save()
                self.edited_aliases.clear()

        def reload_callback() -> None:
            if self.mgr_alias:
                self.mgr_alias.load()
                self.edited_aliases.clear()

        # run output/update loop.
        while True:
            # setup the window for this frame.
            self._remake_subwindow()
            max_y, max_x = self.win.getmaxyx()
            max_y -= 1
            max_x -= 1
            self.win.clear()
            self.win.vline(0, 14, curses.ACS_VLINE, max_y)
            self.scr.addch(min(2, max_y), 14, curses.ACS_TTEE)

            # Show HUD
            hud = " [F2] Save  [F5] Reload  [ESC] Go Back"
            pad = max_x - len(hud) - 15
            hud += " " * pad
            self.winaddstr(max_y, 15, hud, curses.color_pair(1) | curses.A_BOLD)

            # build the selection for this "frame"
            aliases = get_alias_list(self.mgr_alias)
            alias_viewno = max(0, (self.sct_selno - max_y) + 1)
            visible = aliases[alias_viewno : alias_viewno + max_y]
            selected_alias = ""
            selected_cmd = None
            for i, alias in enumerate(visible):
                flags = 0
                if i + alias_viewno == 0:
                    cmd = None
                    flags |= curses.A_BOLD
                else:
                    cmd = self.mgr_alias.aliases[alias]

                if self.sct_selno == i + alias_viewno:
                    selected_alias = alias
                    selected_cmd = cmd
                    flags = curses.color_pair(1)
                    if alias in self.edited_aliases:
                        flags = curses.color_pair(15)
                    self.winaddstr(i, 0, f" {alias[:11]} ", flags)
                else:
                    if alias in self.edited_aliases:
                        flags = curses.color_pair(14)
                    self.winaddstr(i, 0, f" {alias[:11]} ", flags)

            # build info display for selected alias.
            if selected_cmd or self.edit_mode in [MODE_PICK_FIELD, MODE_EDIT_FIELD]:
                # placeholders for edit mode should be one space when empty.
                p_alias = new_alias_name or selected_alias or " "
                p_cmd = " "
                if selected_cmd and selected_cmd[0]:
                    p_cmd = selected_cmd[0]
                p_args = " "
                if selected_cmd and selected_cmd[1]:
                    p_args = selected_cmd[1]

                # Alias field
                self.winaddstr(0, 15, "Alias:", curses.A_BOLD)
                if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 0:
                    self.winaddstr(1, 17, p_alias, curses.color_pair(1))
                else:
                    self.winaddstr(1, 17, p_alias)

                # Command field
                lbl_cmd = "Command:"
                self.winaddstr(2, 15, lbl_cmd, curses.A_BOLD)
                if p_cmd not in self.top_commands:
                    self.winaddstr(
                        2,
                        16 + len(lbl_cmd),
                        "Invalid command name",
                        curses.color_pair(10),
                    )
                if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 1:
                    self.winaddstr(3, 17, p_cmd, curses.color_pair(1))
                else:
                    self.winaddstr(3, 17, p_cmd)

                # Arguments field.
                if (selected_cmd and selected_cmd[1]) or self.edit_mode in [
                    MODE_PICK_FIELD,
                    MODE_EDIT_FIELD,
                ]:
                    self.winaddstr(4, 15, "Arguments:", curses.A_BOLD)
                    if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 2:
                        self.winaddstr(5, 17, p_args, curses.color_pair(1))
                    else:
                        self.winaddstr(5, 17, p_args)

            # display a simple message before "New" is edited.
            else:
                self.opt_selno = 0
                self.winaddstr(0, 15, "Add a new command alias.")

            self.win.refresh()

            # handle getting the edited string.
            edit_buffer = ""
            if self.edit_mode == MODE_EDIT_FIELD:
                edit_cmd = selected_cmd
                if not edit_cmd:
                    edit_cmd = ("", "")

                # edited alias name
                if self.opt_selno == 0:
                    edit_buffer = self.get_text_input(1, 20, 4, 17)
                    if edit_buffer:
                        self.edited_aliases.add(edit_buffer)
                        # save new alias name to buffer and move to command field.
                        if self.sct_selno == 0:
                            new_alias_name = edit_buffer
                            self.opt_selno = 1
                        else:
                            # update aliases
                            self.mgr_alias.remove_alias(selected_alias)
                            self.mgr_alias.make_alias(
                                edit_buffer, edit_cmd[0], edit_cmd[1]
                            )

                            # get the new index value.
                            aliases = get_alias_list(self.mgr_alias)
                            self.sct_selno = aliases.index(edit_buffer)
                            self.edit_mode = MODE_PICK_FIELD
                    else:
                        self.edit_mode = MODE_PICK_FIELD

                # edited command name
                elif self.opt_selno == 1:
                    edit_buffer = self.get_text_input(1, 20, 6, 17)
                    if edit_buffer:
                        if new_alias_name:
                            self.mgr_alias.make_alias(new_alias_name, edit_buffer, "")
                            # get the new index value.
                            aliases = get_alias_list(self.mgr_alias)
                            self.sct_selno = aliases.index(new_alias_name)
                            new_alias_name = ""
                        else:
                            self.mgr_alias.make_alias(
                                selected_alias, edit_buffer, edit_cmd[1]
                            )
                            self.edited_aliases.add(selected_alias)
                    self.edit_mode = MODE_PICK_FIELD

                # edited arguments field
                elif self.opt_selno == 2:
                    edit_buffer = self.get_text_input(1, 60, 8, 17)
                    self.edited_aliases.add(selected_alias)
                    self.mgr_alias.make_alias(selected_alias, edit_cmd[0], edit_buffer)
                    self.edit_mode = MODE_PICK_FIELD

            self.win.refresh()

            # get this frame's key code input, if we didn't just leave edit mode.
            if not edit_buffer:
                goback = self.do_key_nav(
                    len(aliases) - 1,
                    2,
                    save_callback,
                    reload_callback,
                )
                if goback:
                    break

        return bool(self.edited_aliases)

    def config_servers(self) -> bool:
        """Run CATS in Server Data editing mode."""
        if not self.mgr_srvs:
            self.mgr_srvs = self._get_servers()

        edit_buffer = ""
        selected_srv = self.mgr_srvs[0]
        while True:
            # setup the window for this frame.
            self._remake_subwindow()
            max_y, max_x = self.win.getmaxyx()
            max_y -= 1
            max_x -= 1
            self.win.clear()
            # Layout window.
            self.win.hline(min(1, max_y), 0, curses.ACS_HLINE, max_x)
            self.win.vline(min(1, max_y), 15, curses.ACS_VLINE, max_y)
            self.win.addch(min(1, max_y), 15, curses.ACS_TTEE)

            # Show HUD
            hud = " [F2] Save  [F5] Reload  [ESC] Go Back"
            pad = max_x - len(hud) - 16
            hud += " " * pad
            self.winaddstr(max_y, 16, hud, curses.color_pair(1) | curses.A_BOLD)

            # build the selection for this "frame"
            srv_viewno = max(0, (self.sct_selno - max_y) + 1)
            visible = self.mgr_srvs[srv_viewno : srv_viewno + max_y]
            for i, srv in enumerate(visible):
                flags = 0
                if not srv.has_options:
                    flags = curses.A_DIM
                if i + srv_viewno == self.sct_selno:
                    selected_srv = srv
                    flags = curses.color_pair(1)
                    if srv.edited:
                        flags = curses.color_pair(15)
                    self.winaddstr(i + 2, 0, f" {srv.name[:12]} ", flags)
                else:
                    if srv.edited:
                        flags = curses.color_pair(14)
                    self.winaddstr(i + 2, 0, f" {srv.name[:12]} ", flags)

            self.winaddstr(0, 1, f"Select a server to edit. [ID: {selected_srv.id}]")
            self.win.refresh()

            # build info display for selected alias.
            # Command Prefix field
            prefix = selected_srv.get("command_prefix", " ")
            self.winaddstr(2, 16, "Command Prefix:", curses.A_BOLD)
            if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 0:
                self.winaddstr(3, 18, prefix, curses.color_pair(1))
            else:
                self.winaddstr(3, 18, prefix)

            # Playlist field
            playlist = selected_srv.get("auto_playlist", " ")
            self.winaddstr(4, 16, "Playlist File:", curses.A_BOLD)
            if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 1:
                self.winaddstr(5, 18, playlist, curses.color_pair(1))
            else:
                self.winaddstr(5, 18, playlist)

            # Language field.
            lang = selected_srv.get("language", " ")
            lang = lang or " "
            self.winaddstr(6, 16, "Language:", curses.A_BOLD)
            if self.edit_mode == MODE_PICK_FIELD and self.opt_selno == 2:
                self.winaddstr(7, 18, lang, curses.color_pair(1))
            else:
                self.winaddstr(7, 18, lang)

            self.win.refresh()

            # handle getting the edited string.
            edit_buffer = ""
            if self.edit_mode == MODE_EDIT_FIELD:
                # edited command prefix
                if self.opt_selno == 0:
                    edit_buffer = self.get_text_input(1, 20, 6, 18)
                    selected_srv.set("command_prefix", edit_buffer)
                    self.edit_mode = MODE_PICK_FIELD

                # edited auto playlist
                elif self.opt_selno == 1:
                    edit_buffer = self.get_text_input(1, 60, 8, 18)
                    if edit_buffer:
                        selected_srv.set("auto_playlist", edit_buffer)
                    else:
                        selected_srv.set("auto_playlist", None)
                    self.edit_mode = MODE_PICK_FIELD

                # edited arguments field
                elif self.opt_selno == 2:
                    edit_buffer = self.get_text_input(1, 20, 10, 18)
                    selected_srv.set("language", edit_buffer)
                    self.edit_mode = MODE_PICK_FIELD

            # get this frame's key code input, if we didn't just leave edit mode.
            if not edit_buffer:
                goback = self.do_key_nav(
                    len(self.mgr_srvs) - 1,
                    2,
                    selected_srv.save,
                    selected_srv.load,
                )
                if goback:
                    break

        return any(x.edited for x in self.mgr_srvs)


if __name__ == "__main__":
    # this allows using --write-dir to select a config directory.
    parse_write_base_arg()
    # this makes sure a token exists, so Config doesn't wig out.
    if "MUSICBOT_TOKEN" not in os.environ:
        os.environ["MUSICBOT_TOKEN"] = "Your Token Here"
    # start the CATS tool.
    curses.wrapper(ConfigAssistantTextSystem)
