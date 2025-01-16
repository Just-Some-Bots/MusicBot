import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Callable, Dict, Generator, List
from urllib.parse import parse_qs, urlparse

import discord

from .constructs import Response
from .exceptions import CommandError
from .utils import _func_

if TYPE_CHECKING:
    from .bot import MusicBot

log = logging.getLogger(__name__)

# Mask these to prevent these strings from being extracted by gettext.
TestCommandError = CommandError


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
    # short playlist (38 minutes)
    "https://open.spotify.com/playlist/4MtB6u1iXkFSnFELB8OPGU",
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
    # live stream public radio station.
    "https://playerservices.streamtheworld.com/api/livestream-redirect/KUPDFM.mp3?dist=hubbard&source=hubbard-web&ttag=web&gdpr=0",
    # Youtube live streams
    "https://www.youtube.com/watch?v=jfKfPfyJRdk",
    # TODO: insert some live streams from youtube and twitch here.
]


def classify_link_multi(link: str) -> List[str]:
    """Build a list of classifications for the given link."""
    classifications = []

    if not link.strip():
        return ["empty"]

    # Parse the URL
    parsed = urlparse(link)
    query_params = parse_qs(parsed.query)
    path = parsed.path.lower()
    domain = parsed.netloc.lower()

    # Check for playlist
    if "playlist" in query_params or "playlist" in link or "playlist" in path:
        classifications.append("playlist")

    # Check for video links
    if "youtu.be" in domain or "youtube.com" in domain:
        classifications.append("video")

    # Check for Spotify track or album
    if "spotify.com" in domain:
        if "track" in path:
            classifications.append("track")
        if "album" in path:
            classifications.append("playlist")
        if "playlist" in path:
            classifications.append("playlist")

    # Check for SoundCloud
    if "soundcloud.com" in domain:
        if "sets" in path:
            classifications.append("playlist")
        classifications.append("track")

    # Check for Bandcamp
    if "bandcamp.com" in domain:
        if "album" in path:
            classifications.append("album")

    # Check for static files
    if any(path.endswith(ext) for ext in [".mp4", ".mp3", ".wav"]):
        classifications.append("static_file")

    # Check for live streams
    if "stream" in link or "livestream" in link:
        classifications.append("live_stream")

    # Search queries
    if link.startswith("ytsearch") or link.isalpha():
        classifications.append("search_query")

    # Default to unknown if no other classifications
    if not classifications:
        classifications.append("unknown")

    return classifications


def classify_links(links: List[str]) -> Dict[str, List[str]]:
    """
    Classifies a list of links or strings into multiple categories.

    Args:
        links (List[str]): A list of links or strings to classify.

    Returns:
        Dict[str, List[str]]: A dictionary where keys are classes and values are lists of URLs/strings.
    """

    # Initialize a defaultdict for grouping
    classified_dict = defaultdict(list)

    # Classify each link and group into the dict
    for link in links:
        classes = classify_link_multi(link)
        for cls in classes:
            classified_dict[cls].append(link)

    return dict(classified_dict)


# Example usage
# CLASSIFIED_PLAYABLE_STRING_ARRAY = classify_links(PLAYABLE_STRING_ARRAY)


def exclude_class_filter_func(cls: str) -> Callable[..., bool]:
    """Filter to exclude links in the given class."""
    return lambda x: cls not in classify_link_multi(x)


def contain_class_filter_func(cls: str) -> Callable[..., bool]:
    """Filter to include only links from the given class."""
    return lambda x: cls in classify_link_multi(x)


TESTRIG_TEST_CASES: List[CmdTest] = [
    # Help command is added to this list at test-start.
    CmdTest("summon", [""]),
    CmdTest("play", PLAYABLE_STRING_ARRAY),
    CmdTest("playnext", PLAYABLE_STRING_ARRAY),
    CmdTest("shuffleplay", PLAYABLE_STRING_ARRAY),
    CmdTest("playnow", PLAYABLE_STRING_ARRAY),
    CmdTest(
        "stream",
        list(filter(exclude_class_filter_func("playlist"), PLAYABLE_STRING_ARRAY)),
    ),
    CmdTest(
        "pldump",
        list(filter(contain_class_filter_func("playlist"), PLAYABLE_STRING_ARRAY)),
    ),
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
    # Play adjustable media before testing seek
    CmdTest("playnow", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]),
    CmdTest("seek", ["", "+30", "-20", "1:01", "61", "nein"]),
    # Play adjustable media before testing speed
    CmdTest("playnow", ["https://www.youtube.com/watch?v=bm48ncbhU10"]),
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
            "on",
            "off",
            "off",
        ],
    ),
    # Set the limitation before testing clearing cache
    CmdTest(
        "config",
        [
            "show StorageLimitBytes",
            "help StorageLimitBytes",
            "set StorageLimitBytes 1",
            "save MusicBot StorageLimitBytes",
        ],
    ),
    CmdTest(
        "cache",
        [
            "",
            "update",
            "info",
            "clear",
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
    # Deprecated command
    # CmdTest("option", [""]),
    CmdTest("follow", ["", ""]),
    CmdTest("uptime", [""]),
    CmdTest("latency", [""]),
    CmdTest("botversion", [""]),
    #
    # Commands that need owner / perms
    CmdTest("botlatency", [""]),
    CmdTest("checkupdates", [""]),
    # Ensure prefix ccan be change before testing setprefix
    CmdTest(
        "config",
        [
            "show EnablePrefixPerGuild",
            "help EnablePrefixPerGuild",
            "set EnablePrefixPerGuild yes",
            "save ChatCommands EnablePrefixPerGuild",
        ],
    ),
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
            "help Playback DefaultVolume",
            "help DefaultVolume",
            "show",
            "show Playback DefaultVolume",
            "show DefaultVolume",
            "set Playback DefaultVolume 0",
            "set DefaultVolume 100",
            "set Playback DefaultVolume 1",
            "diff",
            "save Playback DefaultVolume",
            "save DefaultVolume",
            "set Playback DefaultVolume .25",
            "set Playback DefaultVolume 0.25",
            "reset Playback DefaultVolume",
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
        log.info("Starting Command Tests...")
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

        # Initialize queue for buffering commands
        cmd_queue: asyncio.Queue[str] = asyncio.Queue()

        async def enqueue_commands() -> None:
            """Load commands into the queue."""
            for test in test_cases:
                for cmd in test.command_cases(""):
                    await cmd_queue.put(cmd)
                    log.info("Buffered command: %(cmd)s", {"cmd": cmd})

        async def process_commands() -> None:
            """Process commands from the queue."""
            counter = 0
            while not cmd_queue.empty():
                cmd = await cmd_queue.get()
                counter += 1

                if message.channel.guild:
                    prefix = bot.server_data[message.channel.guild.id].command_prefix
                else:
                    prefix = bot.config.command_prefix

                full_cmd = f"{prefix}{cmd}"
                message.content = full_cmd
                log.info(
                    "- Processing CMD %(n)s of %(t)s: %(cmd)s",
                    {"n": counter, "t": cmd_total, "cmd": full_cmd},
                )

                await bot.on_message(message)
                await asyncio.sleep(sleep_time)

        # Run both enqueueing and processing concurrently
        await asyncio.gather(enqueue_commands(), process_commands())

        print("Done. Finally....")
        t = time.time() - start_time
        print(f"Took {t:.3f} seconds.")
