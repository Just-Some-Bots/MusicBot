#!/usr/bin/env python3

import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
from collections import defaultdict

try:
    import colorama

    # import colorama  # type: ignore[import-untyped]
    colorama.just_fix_windows_console()

    C_RED = colorama.Fore.RED
    C_GREEN = colorama.Fore.GREEN
    C_YELLOW = colorama.Fore.YELLOW
    C_BWHITE = f"{colorama.Style.BRIGHT}{colorama.Fore.WHITE}"
    C_END = colorama.Style.RESET_ALL
except Exception:  # pylint: disable=broad-exception-caught
    C_RED = ""
    C_GREEN = ""
    C_YELLOW = ""
    C_BWHITE = ""
    C_END = ""


class LangTool:
    def __init__(self, args, basedir):
        """
        Container for common i18n related tasks.
        Most tasks depend only on the bundled pygettext and msgfmt scripts.
        """
        self.args = args
        self.basedir = basedir
        self.workdir = basedir.parent

        os.chdir(self.workdir)

        self._logs_pot_path = basedir.joinpath("musicbot_logs.pot")
        self._msgs_pot_path = basedir.joinpath("musicbot_messages.pot")
        self._logs_diff_path = basedir.joinpath("musicbot_logs.diff.pot")
        self._msgs_diff_path = basedir.joinpath("musicbot_messages.diff.pot")
        self._xx_lang_path = basedir.joinpath("xx").joinpath("LC_MESSAGES")
        self._gettext_path = basedir.joinpath("pygettext.py")
        self._msgfmt_path = basedir.joinpath("msgfmt.py")
        self._json_stats_path = self.workdir.joinpath(".github/i18n_stats.json")
        self._stats_badge_path = self.workdir.joinpath(".github/i18n_badges.md")
        self._po_file_pattern = "*/LC_MESSAGES/*.po"
        self._do_diff = False

        try:
            # Get the last release tag, number of commits since, and g{commit_id} as string.
            self.version = (
                subprocess.check_output(["git", "describe", "--tags", "--always"])
                .decode("ascii")
                .strip()
            )
        except Exception:  # pylint: disable=broad-exception-caught
            print("Failed to get version info from git!")
            self.version = "unknown"

    def __del__(self) -> None:
        """Clean up extra bits when we shut down."""
        if self._logs_diff_path.is_file():
            self._logs_diff_path.unlink()
        if self._msgs_diff_path.is_file():
            self._msgs_diff_path.unlink()

    def _check_polib(self):
        """Test-load polib and fail softly."""
        try:
            import polib

            print(f"Loaded polib version {polib.__version__}")
        except Exception:  # pylint: disable=broad-exception-caught
            print("Fatal error, could not load the 'polib' module.")
            print("Install polib with pip or via your system package manager first.")
            sys.exit(2)

    def _mk_badge(self, left: str, right: str, color: str) -> str:
        """
        Generate markdown for a static badge from shields.io
        """

        def quote(s: str) -> str:
            s = s.replace("_", "__")
            s = s.replace("-", "--")
            return urllib.parse.quote(s)

        style = "flat-square"
        placeholder = f"{left}: {right}"
        left = quote(left)
        right = quote(right)
        color = color.strip("#")
        img_url = f"https://img.shields.io/badge/{left}-{right}-{color}?style={style}"
        return f"![{placeholder}]({img_url})"

    def _colorize_percent(self, percent: float, fmt: str = "") -> str:
        """Converts the percentage to a string with colors based on the value."""
        color = C_RED
        if percent > 50:
            color = C_YELLOW
        if percent >= 100:
            color = C_GREEN
        if fmt:
            percent = fmt.format(p=percent)
            return f"{color}{percent}{C_END}"
        return f"{color}{percent}%{C_END}"

    def compile(self):
        """
        Compiles all existing .po files into .mo files.
        """
        self._check_polib()
        import polib

        print("Compiling existing PO files to MO...")
        for po_file in self.basedir.glob(self._po_file_pattern):
            mo_file = po_file.with_suffix(".mo")
            po = polib.pofile(po_file)
            po.save_as_mofile(mo_file)
            locale = po_file.parent.parent.name
            fname = po_file.name
            ptl = self._colorize_percent(po.percent_translated())
            print(f"Compiled:  {C_BWHITE}{locale}{C_END} - {fname} - {ptl} translated")

        print("Done.")
        print(
            "Note:  Translation percent is calculated based on PO file contents only!"
        )
        print("       Use the -s option to compare translations to current source.")
        print("")

    def extract(self):
        """
        Extract strings from source files to create the POT domain files.
        """
        # universal list for shared domain keywords.
        shared_keywords = [
            # Cross domain keywords.
            "--keyword=_X",
            # MusicbotException and children are all shared.
            "--keyword=MusicbotException",
            "--keyword=CommandError",
            "--keyword=ExtractionError",
            "--keyword=InvalidDataError",
            "--keyword=WrongEntryTypeError",
            "--keyword=FFmpegError",
            "--keyword=FFmpegWarning",
            "--keyword=SpotifyError",
            "--keyword=PermissionsError",
            "--keyword=HelpfulError",
            "--keyword=HelpfulWarning",
        ]

        print("Extracting strings for logs domain...")
        if self._do_diff:
            logsout = self._logs_diff_path
        else:
            logsout = self._logs_pot_path
        subprocess.check_output(
            [
                sys.executable,
                self._gettext_path,
                "-v",
                "-K",
                "--add-comments=TRANSLATORS:",
                "--package-name=Just-Some-Bots/MusicBot",
                f"--package-version={self.version}",
                "--keyword=_L",
                "--keyword=_Ln",
                "--keyword=debug",
                "--keyword=info",
                "--keyword=warning",
                "--keyword=error",
                "--keyword=critical",
                "--keyword=exception",
                "--keyword=everything",
                "--keyword=voicedebug",
                "--keyword=ffmpeg",
                "--keyword=noise",
                *shared_keywords,
                f"--output={logsout}",
                "run.py",
                "musicbot/*.py",
            ]
        )
        print("Extracting strings for messages domain...")
        if self._do_diff:
            msgsout = self._msgs_diff_path
        else:
            msgsout = self._msgs_pot_path
        subprocess.check_output(
            [
                sys.executable,
                self._gettext_path,
                "-v",
                "-K",
                "--add-comments=TRANSLATORS:",
                "--package-name=Just-Some-Bots/MusicBot",
                f"--package-version={self.version}",
                "--keyword=_D",
                "--keyword=_Dn",
                "--keyword=_Dd",
                *shared_keywords,
                f"--output={msgsout}",
                "musicbot/*.py",
            ]
        )
        print("Extraction finished.")

    def diff(self, short=False):
        """
        Display a short or long diff of changes in the POT file.
        Short simply excludes the file:line comments from the diff output.
        """
        print("Preparing diff for source strings...")
        short_ignore = ["@@", "+#:", "-#:"]
        self._do_diff = True
        self.extract()

        print("Diff for logs domain:")
        a = self._logs_pot_path.read_text().split("\n")
        b = self._logs_diff_path.read_text().split("\n")
        for line in difflib.unified_diff(
            a, b, fromfile="old", tofile="new", n=0, lineterm=""
        ):
            if short and any(line.startswith(ig) for ig in short_ignore):
                continue

            if line.startswith("-"):
                line = f"{C_RED}{line}{C_END}"
            elif line.startswith("+"):
                line = f"{C_GREEN}{line}{C_END}"

            print(line)
        print("")

        print("Diff for messages domain:")
        a = self._msgs_pot_path.read_text().split("\n")
        b = self._msgs_diff_path.read_text().split("\n")
        for line in difflib.unified_diff(
            a, b, fromfile="old", tofile="new", n=0, lineterm=""
        ):
            if short and any(line.startswith(ig) for ig in short_ignore):
                continue

            if line.startswith("-"):
                line = f"{C_RED}{line}{C_END}"
            elif line.startswith("+"):
                line = f"{C_GREEN}{line}{C_END}"

            print(line)
        print("")
        print("Done.")

    def stats(self, save_json: bool = False, save_badges: bool = False):
        """
        Get statistics on each language completion level and coherence to source.
        """
        self._check_polib()
        import polib

        print("Gathering language statistics...")
        self._do_diff = True
        self.extract()

        data = defaultdict(dict)
        last_locale = ""
        locale_set = set()
        completed = 0
        total = 0
        pot_logs = polib.pofile(self._logs_diff_path)
        pot_msgs = polib.pofile(self._msgs_diff_path)
        for po_file in self.basedir.glob(self._po_file_pattern):
            locale = po_file.parent.parent.name
            locale_set.add(locale)

            if locale != last_locale:
                print(f"\nLanguage:  {locale}")
                last_locale = locale

            po = polib.pofile(po_file)
            if po_file.name.startswith("musicbot_logs"):
                po.merge(pot_logs)
            elif po_file.name.startswith("musicbot_messages"):
                po.merge(pot_msgs)

            completed += po.percent_translated()
            total += 100
            n_o = len(po.obsolete_entries())
            n_u = len(po.untranslated_entries())
            o_color = u_color = C_RED
            if n_o < 5:
                o_color = C_YELLOW
            if n_o == 0:
                o_color = C_GREEN
            if n_u < 5:
                u_color = C_YELLOW
            if n_u == 0:
                u_color = C_GREEN
            obs = f"{o_color}{n_o}{C_END}"
            unt = f"{u_color}{n_u}{C_END}"
            ptl = self._colorize_percent(
                po.percent_translated(),
                fmt="{p: >4}%",
            )
            print(
                f"{ptl} Translated with {obs} obsolete and {unt} untranslated in: {C_BWHITE}{po_file.name}{C_END}"
            )
            data[locale][po_file.name] = {
                "percent_done": po.percent_translated(),
                "obsolete": n_o,
                "untranslated": n_u,
            }

        pct = completed / total * 100
        print(f"\nOverall Completion:  {pct:.1f}%\n")

        if save_json:
            data["MUSICBOT"] = {
                "completion": pct,
                "languages": ",".join(locale_set),
            }
            with open(self._json_stats_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

        if save_badges:
            b_color = "red"
            if pct > 60:
                b_color = "yellow"
            if pct >= 100:
                b_color = "green"
            tl_badge = self._mk_badge("Translations", f"{pct:.1f}%", b_color)
            badges = ""
            for locale, files in data.items():
                p_logs = files["musicbot_logs.po"]["percent_done"]
                p_msgs = files["musicbot_messages.po"]["percent_done"]
                b_color = "red"
                if p_logs > 60 or p_msgs > 60:
                    b_color = "yellow"
                if p_logs == 100 and p_msgs == 100:
                    b_color = "green"
                badges += self._mk_badge(locale, f"{p_logs}% • {p_msgs}%", b_color)
                badges += "  \n"

            badges = f"{tl_badge}  \n{badges}"
            with open(self._stats_badge_path, "w", encoding="utf-8") as fh:
                fh.write(badges)

    def mktestlang(self):
        """
        Reads in an existing POT file and creates the 'xx' test language.
        Directories and the .po / .mo files are updated by this method.
        """
        self._check_polib()
        import polib

        self._xx_lang_path.mkdir(parents=True, exist_ok=True)

        subs = re.compile(r"([a-z]+|f[0-9]+\.)(\)[a-z\._]+\()?%")

        def reverse_msgid_as_msgstr(po):
            for entry in po:
                # reverse the msgid
                newstr = entry.msgid[::-1]
                # un-reverse placeholders.
                matchiter = subs.finditer(newstr)
                for match in matchiter:
                    group = match.group(0)
                    newstr = newstr.replace(group, group[::-1])
                # set translation to the reversed string.
                entry.msgstr = newstr

        if self._logs_pot_path.is_file():
            print("Making lang xx musicbot_logs.po/.mo")
            p1 = polib.pofile(self._logs_pot_path)
            reverse_msgid_as_msgstr(p1)
            p1.metadata["Language"] = "xx"
            p1.metadata["Content-Type"] = "text/plain; charset=UTF-8"
            p1.save(self._xx_lang_path.joinpath("musicbot_logs.po"))
            p1.save_as_mofile(self._xx_lang_path.joinpath("musicbot_logs.mo"))
        else:
            print("Skipped logs domain, no musicbot_logs.pot file found.")

        if self._msgs_pot_path.is_file():
            print("Making lang xx musicbot_messagess.po/.mo")
            p2 = polib.pofile(self._msgs_pot_path)
            reverse_msgid_as_msgstr(p2)
            p2.metadata["Language"] = "xx"
            p2.metadata["Content-Type"] = "text/plain; charset=UTF-8"
            p2.save(self._xx_lang_path.joinpath("musicbot_messages.po"))
            p2.save_as_mofile(self._xx_lang_path.joinpath("musicbot_messages.mo"))
        else:
            print("Skipped messages domain, no musicbot_messages.pot file found.")

    def update(self):
        """Update the POT file then run merge on existing PO files."""
        self._check_polib()
        import polib

        print("Updating POT and PO files from sources...")
        self.extract()

        print("Merging POT updates...")
        pot_logs = polib.pofile(self._logs_pot_path)
        pot_msgs = polib.pofile(self._msgs_pot_path)
        for po_file in self.basedir.glob(self._po_file_pattern):
            locale = po_file.parent.parent.name
            po = polib.pofile(po_file)
            pre_pct = self._colorize_percent(po.percent_translated())

            if po_file.name.startswith("musicbot_logs"):
                po.merge(pot_logs)
            elif po_file.name.startswith("musicbot_messages"):
                po.merge(pot_msgs)

            pct = self._colorize_percent(po.percent_translated())
            po.save()
            print(
                f"Updated: {locale} - {po_file.name} Was {pre_pct} translated, now {pct}"
            )
        print("Done.")


def main():
    """MusicBot i18n tool entry point."""
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("Helper tool for i18n tasks in MusicBot."),
        epilog=(
            "For more help and support with this bot, join our discord:"
            "\n  https://discord.gg/bots\n\n"
            "This software is provided under the MIT License."
            "\n"
            "See the `LICENSE` text file for complete details."
        ),
    )

    ap.add_argument(
        "-c",
        dest="do_compile",
        action="store_true",
        help="Compile existing PO files into MO files.",
    )

    ap.add_argument(
        "-e",
        dest="do_extract",
        action="store_true",
        help="Extract strings to POT files.",
    )

    ap.add_argument(
        "-d",
        dest="do_diff_short",
        action="store_true",
        help="Diff new extractions to the existing POT file.  Ignores location comment changes.",
    )

    ap.add_argument(
        "-D",
        dest="do_diff_long",
        action="store_true",
        help="Same as -d but show all changes.",
    )

    ap.add_argument(
        "-t",
        dest="do_testlang",
        action="store_true",
        help="Create or update the 'xx' test language.",
    )

    ap.add_argument(
        "-s",
        dest="do_stats",
        action="store_true",
        help="Show translation stats for existing PO files, by extracting strings from sources first.",
    )

    ap.add_argument(
        "-J",
        dest="save_json",
        action="store_true",
        help="Save stats to JSON for use in the repository.",
    )

    ap.add_argument(
        "-B",
        dest="save_badges",
        action="store_true",
        help="Save stats will save badges to use in the repository.",
    )

    ap.add_argument(
        "-u",
        dest="do_update",
        action="store_true",
        help="Update existing POT files and then update existing PO files.",
    )

    _args = ap.parse_args()
    _basedir = pathlib.Path(__file__).parent.resolve()

    if _basedir.name != "i18n":
        print("Script not inside the i18n directory.")
        print("This cannot continue!")
        sys.exit(1)

    if not _basedir.parent.joinpath("musicbot").is_dir():
        print("Script cannot locate musicbot source files.")
        print("This cannot continue!")
        sys.exit(1)

    langtool = LangTool(_args, _basedir)

    if _args.do_diff_short or _args.do_diff_long:
        langtool.diff(short=not _args.do_diff_long)
        sys.exit(0)

    if _args.do_stats:
        langtool.stats(save_json=_args.save_json, save_badges=_args.save_badges)
        sys.exit(0)

    if _args.do_testlang:
        langtool.mktestlang()
        sys.exit(0)

    if _args.do_extract:
        langtool.extract()

    if _args.do_update:
        langtool.update()

    if _args.do_compile:
        langtool.compile()


if __name__ == "__main__":
    main()
