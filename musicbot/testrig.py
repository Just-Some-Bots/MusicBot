import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, Generator, List

import discord

from .constructs import Response
from .exceptions import CommandError
from .utils import _func_

if TYPE_CHECKING:
    from .bot import MusicBot

log = logging.getLogger(__name__)

# Mask these to prevent these strings from being extracted by gettext.
TestCommandError = CommandError
loginfo = log.info


class CmdTest:
    def __init__(self, cmd: str, cases: List[str]) -> None:
        """Represents command test cases."""
        self.cmd = cmd
        self.cases = cases

    def __len__(self) -> int:
        return len(self.cases)

    def __str__(self) -> str:
        return self.cmd

    def command_cases(self, prefix: str) -> Generator[str, str, None]:
        """Yields complete command strings which can be sent as a message."""
        for case in self.cases:
            cmd = f"{prefix}{self.cmd} {case}"
            yield cmd


PLAYABLE_STRING_ARRAY = [
    # pointedly empty, do not remove.
    "",
    # HUGE playlist with big files and streams.
    # "https://www.youtube.com/playlist?list=PLBcHt8htZXKVCzW_Mkn4NrByBxn53o3cA",
    # playlist with several tracks.
    # "https://www.youtube.com/playlist?list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
    # playlist with few tracks
    "https://www.youtube.com/playlist?list=PL42rXizBzbC25pvGACvkUQ8EtZcm30BlF",
    # Video link, with playlist ID in URL.
    "https://www.youtube.com/watch?v=bm48ncbhU10&list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
    # Video link
    "https://www.youtube.com/watch?v=bm48ncbhU10",
    # Shorthand video link
    "https://youtu.be/L5uV3gmOH9g",
    # Shorthand with playlist ID
    "https://youtu.be/E3xbLcTj_bs?list=PLTxsp5i8fQO51pAymuKRfkmL4GnPRa6iC",
    # Spotify links
    # TODO: find smaller playlist on spotify
    # "https://open.spotify.com/playlist/37i9dQZF1DXaImRpG7HXqp",
    "https://open.spotify.com/track/0YupMLYOYz6lZDbN3kRt7A?si=5b0eeb51b04c4af9",
    # one item and multi-item albums
    "https://open.spotify.com/album/1y8Yw0NDcP2qxbZufIXt7u",
    "https://open.spotify.com/album/5LbHbwejgZXRZAgzVAjkhj",
    # soundcloud track and set/playlist
    "https://soundcloud.com/neilcic/cabinet-man",
    "https://soundcloud.com/grweston/sets/mashups",
    # bandcamp album
    "https://lemondemon.bandcamp.com/album/spirit-phone",
    # naked search query.
    "slippery people talking heads live 84",
    # search handler format in query.
    "ytsearch4:talking heads stop making sense",
    # generic extractor, static file with no service/meta data
    "https://cdn.discordapp.com/attachments/741945274901200897/875075008723046410/cheesed.mp4",
    # live stream public radio station.
    "https://playerservices.streamtheworld.com/api/livestream-redirect/KUPDFM.mp3?dist=hubbard&source=hubbard-web&ttag=web&gdpr=0",
    # TODO: insert some live streams from youtube and twitch here.
]


TESTRIG_TEST_CASES: List[CmdTest] = [
    # Help command is added to this list at test-start.
    CmdTest("summon", [""]),
    CmdTest("play", PLAYABLE_STRING_ARRAY),
    CmdTest("playnext", PLAYABLE_STRING_ARRAY),
    CmdTest("shuffleplay", PLAYABLE_STRING_ARRAY),
    CmdTest("playnow", PLAYABLE_STRING_ARRAY),
    CmdTest("stream", PLAYABLE_STRING_ARRAY),
    CmdTest("pldump", PLAYABLE_STRING_ARRAY),
    CmdTest(
        "search",
        [
            "",
            "yt 1 test",
            "yt 4 test",
            "yt 10 test",
            "yh 2 test",
            "sc 2 test",
            "'quoted text for reasons'",
            "Who's line is it anyway?",
            "ytsearch4: something about this feels wrong.",
        ],
    ),
    CmdTest("seek", ["", "+30", "-20", "1:01", "61", "nein"]),
    CmdTest("speed", ["", "1", "1.", "1.1", "six", "-0.3", "40"]),
    CmdTest("move", ["", "2 4", "-1 -2", "x y"]),
    CmdTest("remove", ["", "5", "a"]),
    CmdTest("skip", [""]),
    CmdTest("pause", [""]),
    CmdTest("resume", [""]),
    CmdTest("id", [""]),
    CmdTest("queue", [""]),
    CmdTest("np", [""]),
    CmdTest(
        "repeat",
        [
            "",
            "all",
            "playlist",
            "song",
            "on",
            "off",
            "off",
            "off",
        ],
    ),
    CmdTest(
        "cache",
        [
            "",
            "info",
            "clear",
            "update",
        ],
    ),
    CmdTest(
        "volume",
        [
            "",
            "15",
            "15",
            "40",
            "15",
            "x",
            "-1",
            "+4",
        ],
    ),
    CmdTest("shuffle", [""]),
    CmdTest("perms", [""]),
    CmdTest("listids", [""]),
    CmdTest("clear", [""]),
    CmdTest(
        "clean",
        [
            "",
            "4",
            "50",
            "100",
            "1000",
            "-3",
        ],
    ),
    CmdTest("disconnect", [""]),
    CmdTest("id", ["", "TheFae"]),
    CmdTest("joinserver", [""]),
    CmdTest("karaoke", [""]),
    CmdTest("play", ["life during wartime live 84"]),
    CmdTest("karaoke", [""]),
    CmdTest(
        "autoplaylist",
        [
            "",
            "+",  # add current playing
            "-",  # remove current playing
            "+ https://www.youtube.com/playlist?list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
            "+ https://www.youtube.com/watch?v=bm48ncbhU10&list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
            "+ https://www.youtube.com/watch?v=bm48ncbhU10",
            "- https://www.youtube.com/playlist?list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
            "- https://www.youtube.com/watch?v=bm48ncbhU10&list=PL80gRr4GwcsznLYH-G_FXnzkP5_cHl-KR",
            "- https://www.youtube.com/watch?v=bm48ncbhU10",
            "- https://www.youtube.com/watch?v=bm48ncbhU10",
            "https://www.youtube.com/watch?v=bm48ncbhU10",
            "show",
            "set test.txt",
            "+ https://test.url/",
            "- https://test.url/",
            "set default",
        ],
    ),
    CmdTest(
        "blockuser",
        [
            "",
            "+ @MovieBotTest#5179",
            "- @MovieBotTest#5179",
            "- @MovieBotTest#5179",
            "add @MovieBotTest#5179",
            "add @MovieBotTest#5179",
            "remove @MovieBotTest#5179",
        ],
    ),
    CmdTest(
        "blocksong",
        [
            "",
            "+ test text",
            "- test text",
            "- test text",
            "add test text",
            "add test text",
            "remove test text",
        ],
    ),
    CmdTest("resetplaylist", [""]),
    CmdTest("option", ["", "autoplaylist on"]),
    CmdTest("follow", ["", ""]),
    CmdTest("uptime", [""]),
    CmdTest("latency", [""]),
    CmdTest("botversion", [""]),
    #
    # Commands that need owner / perms
    CmdTest("botlatency", [""]),
    CmdTest("checkupdates", [""]),
    CmdTest("setprefix", ["", "**", "**", "?"]),
    CmdTest("setavatar", ["", "https://cdn.imgchest.com/files/6yxkcjrkqg7.png"]),
    CmdTest("setname", ["", f"TB-name-{uuid.uuid4().hex[0:7]}"]),
    CmdTest("setnick", ["", f"TB-nick-{uuid.uuid4().hex[0:7]}"]),
    CmdTest("language", ["", "show", "set", "set xx", "reset"]),
    CmdTest(
        "setalias",
        [
            "",
            "load",
            "add",
            "remove",
            "remove testalias1",
            "add testalias1 help setalias",
            "add testalias1 help setalias",
            "add testalias1 help setprefix",
            "save",
            "remove testalias1",
            "load",
            "remove testalias1",
            "save",
        ],
    ),
    # TODO: need to come up with something to create attachments...
    CmdTest("setcookies", ["", "on", "off"]),
    CmdTest(
        "setperms",
        [
            "",
            "list",
            "reload",
            "help",
            "help CommandWhitelist",
            "show Default CommandWhitelist",
            "add TestGroup1",
            "add TestGroup1",
            "save TestGroup1",
            "remove TestGroup1",
            "remove TestGroup1",
            "reload",
            "set TestGroup1 MaxSongs 200",
            "show TestGroup1 MaxSongs",
            "remove TestGroup1",
            "save",
        ],
    ),
    
    CmdTest(
        "config",
        [
            "",
            "missing",
            "list",
            "reload",
            "help",
            "help Credentials Token",
            "help MusicBot DefaultVolume",
            "help DefaultVolume",
            "show",
            "show MusicBot DefaultVolume",
            "show DefaultVolume",
            "set MusicBot DefaultVolume 0",
            "set DefaultVolume 100",
            "set MusicBot DefaultVolume 1",
            "diff",
            "save MusicBot DefaultVolume",
            "save DefaultVolume",
            "set MusicBot DefaultVolume .25",
            "set MusicBot DefaultVolume 0.25",
            "reset MusicBot DefaultVolume",
            "reset DefaultVolume",
            "save DefaultVolume",
        ],
    ),
]

"""
Cannot test:
  leaveserver, restart, shutdown
"""


async def run_cmd_tests(
    bot: "MusicBot",
    message: discord.Message,
    command_list: List[str],
    dry: bool = False,
) -> None:
    """
    Handles actually running the command test cases, or reporting data about them.

    :param: bot:  A reference to MusicBot.

    :param: message:  A message, typically the message sent to !testready.

    :param: command_list:  List of existing commands, generated by MusicBot for detecting missing command tests.
                            Note that dev_only commands are excluded.

    :param: dry:  A flag to simply report data about test cases but run no tests.

    :raises:  CommandError if tests are already running.
    """
    # use lock to prevent parallel testing.
    if bot.aiolocks[_func_()].locked():
        raise TestCommandError("Command Tests are already running!")

    async with bot.aiolocks[_func_()]:
        loginfo("Starting Command Tests...")
        start_time = time.time()
        # create a list of help commands to run using input command list and custom tests.
        help_cmd_list = ["", "-missing-", "all"] + command_list
        test_cases = [CmdTest("help", help_cmd_list)] + TESTRIG_TEST_CASES
        test_cmds = [x.cmd for x in test_cases]

        # check for missing tests.
        cmds_missing = []
        for cmd in command_list:
            if cmd not in test_cmds:
                cmds_missing.append(cmd)

        if cmds_missing:
            await bot.safe_send_message(
                message.channel,
                Response(
                    f"\n**Missing Command Cases:**\n```\n{', '.join(cmds_missing)}```",
                    delete_after=120,
                ),
            )

        # a better idea would be buffering messages into a queue to inspect them.
        # but i'm just gonna do this manually for now.
        sleep_time = 2
        cmd_total = 0
        for tc in test_cases:
            cmd_total += len(tc)

        est_time = (sleep_time + 1) * cmd_total

        await bot.safe_send_message(
            message.channel,
            Response(
                f"Total Test Cases:  {cmd_total}\nEstimated Run Time:  {est_time}",
                delete_after=60,
            ),
        )

        if dry:
            return None

        counter = 0
        for test in test_cases:
            for cmd in test.command_cases(""):

                counter += 1
                if message.channel.guild:
                    prefix = bot.server_data[message.channel.guild.id].command_prefix
                else:
                    prefix = bot.config.command_prefix

                cmd = f"{prefix}{cmd}"

                loginfo(
                    "- Sending CMD %(n)s of %(t)s:  %(cmd)s",
                    {"n": counter, "t": cmd_total, "cmd": cmd},
                )

                message.content = cmd
                await bot.on_message(message)
                await asyncio.sleep(sleep_time)

        print("Done. Finally....")
        t = time.time() - start_time
        print(f"Took {t:.3f} seconds.")
