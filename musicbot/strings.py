import configparser
import os

from .exceptions import HelpfulError


class Strings:
    def __init__(self, strings_file):
        self.strings_file = strings_file
        config = configparser.ConfigParser()

        if not config.read(strings_file, encoding='utf-8'):
            print('[config] Strings file not found, please re-download the bot.')
            os._exit(4)

        config = configparser.ConfigParser(interpolation=None)
        config.read(strings_file, encoding='utf-8')

        self.help_header = config.get('Commands', 'Help_Header', fallback=StringDefaults.help_header)
        self.help_notfound = config.get('Commands', 'Help_NotFound', fallback=StringDefaults.help_notfound)
        self.blacklist_nousers = config.get('Commands', 'Blacklist_NoUsers', fallback=StringDefaults.blacklist_nousers)
        self.blacklist_invalidarg = config.get('Commands', 'Blacklist_InvalidArg', fallback=StringDefaults.blacklist_invalidarg)
        self.blacklist_usersadded = config.get('Commands', 'Blacklist_UsersAdded', fallback=StringDefaults.blacklist_usersadded)
        self.blacklist_notfound = config.get('Commands', 'Blacklist_NotFound', fallback=StringDefaults.blacklist_notfound)
        self.blacklist_usersremoved = config.get('Commands', 'Blacklist_UsersRemoved', fallback=StringDefaults.blacklist_usersremoved)
        self.id_yourid = config.get('Commands', 'Id_YourId', fallback=StringDefaults.id_yourid)
        self.id_otherid = config.get('Commands', 'Id_OtherId', fallback=StringDefaults.id_otherid)
        self.joinserver_bot = config.get('Commands', 'Joinserver_Bot', fallback=StringDefaults.joinserver_bot)
        self.joinserver_done = config.get('Commands', 'Joinserver_Done', fallback=StringDefaults.joinserver_done)
        self.joinserver_invalid = config.get('Commands', 'Joinserver_Invalid', fallback=StringDefaults.joinserver_invalid)
        self.play_pllimitreached = config.get('Commands', 'Play_PlLimitReached', fallback=StringDefaults.play_pllimitreached)
        self.play_cantplay = config.get('Commands', 'Play_CantPlay', fallback=StringDefaults.play_cantplay)
        self.play_cantplayplaylist = config.get('Commands', 'Play_CantPlayPlaylist', fallback=StringDefaults.play_cantplayplaylist)
        self.play_noplaylists = config.get('Commands', 'Play_NoPlaylists', fallback=StringDefaults.play_noplaylists)
        self.play_pltoomanyentries = config.get('Commands', 'Play_PlTooManyEntries', fallback=StringDefaults.play_pltoomanyentries)
        self.play_pltoomanyentriestotal = config.get('Commands', 'Play_PlTooManyEntriesTotal', fallback=StringDefaults.play_pltoomanyentriestotal)
        self.play_plerror = config.get('Commands', 'Play_PlError', fallback=StringDefaults.play_plerror)
        self.play_plinfo = config.get('Commands', 'Play_PlInfo', fallback=StringDefaults.play_plinfo)
        self.play_plexceedduration = config.get('Commands', 'Play_PlExceedDuration', fallback=StringDefaults.play_plexceedduration)
        self.play_enqueuedplaylist = config.get('Commands', 'Play_EnqueuedPlaylist', fallback=StringDefaults.play_enqueuedplaylist)
        self.play_enqueuedplaylistfuture = config.get('Commands', 'Play_EnqueuedPlaylistFuture', fallback=StringDefaults.play_enqueuedplaylistfuture)
        self.play_enqueuedplaylisttime = config.get('Commands', 'Play_EnqueuedPlaylistTime', fallback=StringDefaults.play_enqueuedplaylisttime)
        self.play_playingnext = config.get('Commands', 'Play_PlayingNext', fallback=StringDefaults.play_playingnext)
        self.play_exceedduration = config.get('Commands', 'Play_ExceedDuration', fallback=StringDefaults.play_exceedduration)
        self.play_enqueuedsong = config.get('Commands', 'Play_EnqueuedSong', fallback=StringDefaults.play_enqueuedsong)
        self.play_processing = config.get('Commands', 'Play_Processing', fallback=StringDefaults.play_processing)
        self.play_errorqueuingpl = config.get('Commands', 'Play_ErrorQueuingPl', fallback=StringDefaults.play_errorqueuingpl)
        self.play_currentexceedduration = config.get('Commands', 'Play_CurrentExceedDuration', fallback=StringDefaults.play_currentexceedduration)
        self.search_valueerror = config.get('Commands', 'Search_ValueError', fallback=StringDefaults.search_valueerror)
        self.search_reachedmax = config.get('Commands', 'Search_ReachedMax', fallback=StringDefaults.search_reachedmax)
        self.search_searching = config.get('Commands', 'Search_Searching', fallback=StringDefaults.search_searching)
        self.search_notfound = config.get('Commands', 'Search_NotFound', fallback=StringDefaults.search_notfound)
        self.search_end = config.get('Commands', 'Search_End', fallback=StringDefaults.search_end)
        self.search_success = config.get('Commands', 'Search_Success', fallback=StringDefaults.search_success)
        self.nowplaying_author = config.get('Commands', 'NowPlaying_Author', fallback=StringDefaults.nowplaying_author)
        self.nowplaying_noauthor = config.get('Commands', 'NowPlaying_NoAuthor', fallback=StringDefaults.nowplaying_noauthor)
        self.nowplaying_none = config.get('Commands', 'NowPlaying_None', fallback=StringDefaults.nowplaying_none)
        self.summon_novoice = config.get('Commands', 'Summon_NoVoice', fallback=StringDefaults.summon_novoice)
        self.summon_noperms = config.get('Commands', 'Summon_NoPerms', fallback=StringDefaults.summon_noperms)
        self.summon_nopermsvoice = config.get('Commands', 'Summon_NoPermsVoice', fallback=StringDefaults.summon_nopermsvoice)
        self.pause_failure = config.get('Commands', 'Pause_Failure', fallback=StringDefaults.pause_failure)
        self.resume_failure = config.get('Commands', 'Resume_Failure', fallback=StringDefaults.resume_failure)
        self.shuffle_done = config.get('Commands', 'Shuffle_Done', fallback=StringDefaults.shuffle_done)
        self.clear_done = config.get('Commands', 'Clear_Done', fallback=StringDefaults.clear_done)


class StringDefaults:
    """
        These are the default, English strings for the bot.
        Do not edit strings here. Use strings.ini in the config folder.
    """

    help_header = "Commands"
    help_notfound = "No such command"

    blacklist_nousers = "No users listed"
    blacklist_invalidarg = "Invalid option '{option}' specified, use +, -, add, or remove"
    blacklist_usersadded = "{users} users have been added to the blacklist"
    blacklist_notfound = "None of those users are in the blacklist"
    blacklist_usersremoved = "{users} users have been removed from the blacklist"

    id_yourid = "Your ID is {id}"
    id_otherid = "{name}'s ID is {id}"

    joinserver_bot = "Bot account's can't use invite links! See: {url}"
    joinserver_done = ":+1:"
    joinserver_invalid = "Invalid URL provided:\n{url}\n"

    play_pllimitreached = "You have reached your playlist item limit ({limit})"
    play_cantplay = "That video cannot be played"
    play_cantplayplaylist = "That playlist cannot be played"
    play_noplaylists = "You are not allowed to request playlists"
    play_pltoomanyentries = "Playlist has too many entries ({songs} > {max})"
    play_pltoomanyentriestotal = "Playlist entries + your already queued songs reached limit ({songs} + {queued} > {max})"
    play_plerror = "Error queuing playlist:\n{exception}"
    play_plinfo = "Gathering playlist information for {songs} songs"
    play_plexceedduration = "No songs were added, all songs were over max duration ({max})"
    play_enqueuedplaylist = "Enqueued **{songs}** songs to be played. Position in queue: {position}"
    play_enqueuedplaylisttime = "Enqueued **{songs}** songs to be played in {secs} seconds"
    play_enqueuedplaylistfuture = " - estimated time until playing: {eta}"
    play_playingnext = "Up next!"
    play_exceedduration = "Song duration exceeds limit ({duration} > {max})"
    play_enqueuedsong = "Enqueued **{song}** to be played. Position in queue: {position}"
    play_processing = "Processing {songs} songs..."
    play_errorqueuingpl = "Error handling playlist {link} queuing"
    play_currentexceedduration = "\nAdditionally, the current song was skipped for being too long."

    search_valueerror = "Please quote your search query properly."
    search_searching = "Searching for videos..."
    search_reachedmax = "You cannot search for more than {max} videos"
    search_notfound = "No videos found."
    search_end = "Oh well :frowning:"
    search_success = "Alright, coming right up!"

    nowplaying_author = "Now Playing: **{song}** added by **{author}** {progress}\n"
    nowplaying_noauthor = "Now Playing: **{song}** {progress}\n"
    nowplaying_none = "There are no songs queued! Queue something with {prefix}play."

    summon_novoice = "You are not in a voice channel!"
    summon_noperms = "Cannot join channel {channel}, no permission."
    summon_nopermsvoice = "Will not join channel {channel}, no permission to speak."

    pause_failure = "Player is not playing."
    resume_failure = "Player is not paused."
    shuffle_done = ":ok_hand:"
    clear_done = ":put_litter_in_its_place:"

    strings_file = 'config/strings.ini'
