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

        self.done = config.get('General', 'Done', fallback=StringDefaults.done).replace('\\n', '\n')
        self.pm_sent = config.get('General', 'PM_Sent', fallback=StringDefaults.pm_sent).replace('\\n', '\n')
        self.no_pm = config.get('General', 'No_PM', fallback=StringDefaults.no_pm).replace('\\n', '\n')

        self.help_header = config.get('Commands', 'Help_Header', fallback=StringDefaults.help_header).replace('\\n', '\n')
        self.help_notfound = config.get('Commands', 'Help_NotFound', fallback=StringDefaults.help_notfound).replace('\\n', '\n')
        self.blacklist_nousers = config.get('Commands', 'Blacklist_NoUsers', fallback=StringDefaults.blacklist_nousers).replace('\\n', '\n')
        self.blacklist_invalidarg = config.get('Commands', 'Blacklist_InvalidArg', fallback=StringDefaults.blacklist_invalidarg).replace('\\n', '\n')
        self.blacklist_usersadded = config.get('Commands', 'Blacklist_UsersAdded', fallback=StringDefaults.blacklist_usersadded).replace('\\n', '\n')
        self.blacklist_notfound = config.get('Commands', 'Blacklist_NotFound', fallback=StringDefaults.blacklist_notfound).replace('\\n', '\n')
        self.blacklist_usersremoved = config.get('Commands', 'Blacklist_UsersRemoved', fallback=StringDefaults.blacklist_usersremoved).replace('\\n', '\n')
        self.id_yourid = config.get('Commands', 'Id_YourId', fallback=StringDefaults.id_yourid).replace('\\n', '\n')
        self.id_otherid = config.get('Commands', 'Id_OtherId', fallback=StringDefaults.id_otherid).replace('\\n', '\n')
        self.joinserver_bot = config.get('Commands', 'Joinserver_Bot', fallback=StringDefaults.joinserver_bot).replace('\\n', '\n')
        self.joinserver_done = config.get('Commands', 'Joinserver_Done', fallback=StringDefaults.joinserver_done).replace('\\n', '\n')
        self.joinserver_invalid = config.get('Commands', 'Joinserver_Invalid', fallback=StringDefaults.joinserver_invalid).replace('\\n', '\n')
        self.play_pllimitreached = config.get('Commands', 'Play_PlLimitReached', fallback=StringDefaults.play_pllimitreached).replace('\\n', '\n')
        self.play_cantplay = config.get('Commands', 'Play_CantPlay', fallback=StringDefaults.play_cantplay).replace('\\n', '\n')
        self.play_cantplayplaylist = config.get('Commands', 'Play_CantPlayPlaylist', fallback=StringDefaults.play_cantplayplaylist).replace('\\n', '\n')
        self.play_noplaylists = config.get('Commands', 'Play_NoPlaylists', fallback=StringDefaults.play_noplaylists).replace('\\n', '\n')
        self.play_pltoomanyentries = config.get('Commands', 'Play_PlTooManyEntries', fallback=StringDefaults.play_pltoomanyentries).replace('\\n', '\n')
        self.play_pltoomanyentriestotal = config.get('Commands', 'Play_PlTooManyEntriesTotal', fallback=StringDefaults.play_pltoomanyentriestotal).replace('\\n', '\n')
        self.play_plerror = config.get('Commands', 'Play_PlError', fallback=StringDefaults.play_plerror).replace('\\n', '\n')
        self.play_plinfo = config.get('Commands', 'Play_PlInfo', fallback=StringDefaults.play_plinfo).replace('\\n', '\n')
        self.play_plexceedduration = config.get('Commands', 'Play_PlExceedDuration', fallback=StringDefaults.play_plexceedduration).replace('\\n', '\n')
        self.play_enqueuedplaylist = config.get('Commands', 'Play_EnqueuedPlaylist', fallback=StringDefaults.play_enqueuedplaylist).replace('\\n', '\n')
        self.play_enqueuedplaylistfuture = config.get('Commands', 'Play_EnqueuedPlaylistFuture', fallback=StringDefaults.play_enqueuedplaylistfuture).replace('\\n', '\n')
        self.play_enqueuedplaylisttime = config.get('Commands', 'Play_EnqueuedPlaylistTime', fallback=StringDefaults.play_enqueuedplaylisttime).replace('\\n', '\n')
        self.play_playingnext = config.get('Commands', 'Play_PlayingNext', fallback=StringDefaults.play_playingnext).replace('\\n', '\n')
        self.play_exceedduration = config.get('Commands', 'Play_ExceedDuration', fallback=StringDefaults.play_exceedduration).replace('\\n', '\n')
        self.play_enqueuedsong = config.get('Commands', 'Play_EnqueuedSong', fallback=StringDefaults.play_enqueuedsong).replace('\\n', '\n')
        self.play_processing = config.get('Commands', 'Play_Processing', fallback=StringDefaults.play_processing).replace('\\n', '\n')
        self.play_errorqueuingpl = config.get('Commands', 'Play_ErrorQueuingPl', fallback=StringDefaults.play_errorqueuingpl).replace('\\n', '\n')
        self.play_currentexceedduration = config.get('Commands', 'Play_CurrentExceedDuration', fallback=StringDefaults.play_currentexceedduration).replace('\\n', '\n')
        self.search_valueerror = config.get('Commands', 'Search_ValueError', fallback=StringDefaults.search_valueerror).replace('\\n', '\n')
        self.search_reachedmax = config.get('Commands', 'Search_ReachedMax', fallback=StringDefaults.search_reachedmax).replace('\\n', '\n')
        self.search_searching = config.get('Commands', 'Search_Searching', fallback=StringDefaults.search_searching).replace('\\n', '\n')
        self.search_notfound = config.get('Commands', 'Search_NotFound', fallback=StringDefaults.search_notfound).replace('\\n', '\n')
        self.search_end = config.get('Commands', 'Search_End', fallback=StringDefaults.search_end).replace('\\n', '\n')
        self.search_success = config.get('Commands', 'Search_Success', fallback=StringDefaults.search_success).replace('\\n', '\n')
        self.search_noquery = config.get('Commands', 'Search_NoQuery', fallback=StringDefaults.search_noquery).replace('\\n', '\n')
        self.search_result = config.get('Commands', 'Search_Result', fallback=StringDefaults.search_result).replace('\\n', '\n')
        self.search_resultend = config.get('Commands', 'Search_ResultEnd', fallback=StringDefaults.search_resultend).replace('\\n', '\n')
        self.search_yes = config.get('Commands', 'Search_Yes', fallback=StringDefaults.search_yes).replace('\\n', '\n')
        self.search_no = config.get('Commands', 'Search_No', fallback=StringDefaults.search_no).replace('\\n', '\n')
        self.search_exit = config.get('Commands', 'Search_Exit', fallback=StringDefaults.search_exit).replace('\\n', '\n')
        self.nowplaying_author = config.get('Commands', 'NowPlaying_Author', fallback=StringDefaults.nowplaying_author).replace('\\n', '\n')
        self.nowplaying_noauthor = config.get('Commands', 'NowPlaying_NoAuthor', fallback=StringDefaults.nowplaying_noauthor).replace('\\n', '\n')
        self.nowplaying_none = config.get('Commands', 'NowPlaying_None', fallback=StringDefaults.nowplaying_none).replace('\\n', '\n')
        self.summon_novoice = config.get('Commands', 'Summon_NoVoice', fallback=StringDefaults.summon_novoice).replace('\\n', '\n')
        self.summon_noperms = config.get('Commands', 'Summon_NoPerms', fallback=StringDefaults.summon_noperms).replace('\\n', '\n')
        self.summon_nopermsvoice = config.get('Commands', 'Summon_NoPermsVoice', fallback=StringDefaults.summon_nopermsvoice).replace('\\n', '\n')
        self.pause_failure = config.get('Commands', 'Pause_Failure', fallback=StringDefaults.pause_failure).replace('\\n', '\n')
        self.resume_failure = config.get('Commands', 'Resume_Failure', fallback=StringDefaults.resume_failure).replace('\\n', '\n')
        self.shuffle_done = config.get('Commands', 'Shuffle_Done', fallback=StringDefaults.shuffle_done).replace('\\n', '\n')
        self.clear_done = config.get('Commands', 'Clear_Done', fallback=StringDefaults.clear_done).replace('\\n', '\n')
        self.skip_failure = config.get('Commands', 'Skip_Failure', fallback=StringDefaults.skip_failure).replace('\\n', '\n')
        self.skip_wait = config.get('Commands', 'Skip_Wait', fallback=StringDefaults.skip_wait).replace('\\n', '\n')
        self.skip_acknowledge = config.get('Commands', 'Skip_Acknowledge', fallback=StringDefaults.skip_acknowledge).replace('\\n', '\n')
        self.skip_acknowledgemore = config.get('Commands', 'Skip_AcknowledgeMore', fallback=StringDefaults.skip_acknowledgemore).replace('\\n', '\n')
        self.skip_comingup = config.get('Commands', 'Skip_ComingUp', fallback=StringDefaults.skip_comingup).replace('\\n', '\n')
        self.skip_single = config.get('Commands', 'Skip_Single', fallback=StringDefaults.skip_single).replace('\\n', '\n')
        self.skip_multiple = config.get('Commands', 'Skip_Multiple', fallback=StringDefaults.skip_multiple).replace('\\n', '\n')
        self.volume_current = config.get('Commands', 'Volume_Current', fallback=StringDefaults.volume_current).replace('\\n', '\n')
        self.volume_valueerror = config.get('Commands', 'Volume_ValueError', fallback=StringDefaults.volume_valueerror).replace('\\n', '\n')
        self.volume_updated = config.get('Commands', 'Volume_Updated', fallback=StringDefaults.volume_updated).replace('\\n', '\n')
        self.queue_andmore = config.get('Commands', 'Queue_AndMore', fallback=StringDefaults.queue_andmore).replace('\\n', '\n')
        self.queue_author = config.get('Commands', 'Queue_Author', fallback=StringDefaults.queue_author).replace('\\n', '\n')
        self.queue_noauthor = config.get('Commands', 'Queue_NoAuthor', fallback=StringDefaults.queue_noauthor).replace('\\n', '\n')
        self.clean_valueerror = config.get('Commands', 'Clean_ValueError', fallback=StringDefaults.clean_valueerror).replace('\\n', '\n')
        self.clean_success = config.get('Commands', 'Clean_Success', fallback=StringDefaults.clean_success).replace('\\n', '\n')
        self.pldump_nodata = config.get('Commands', 'Pldump_NoData', fallback=StringDefaults.pldump_nodata).replace('\\n', '\n')
        self.pldump_noplaylist = config.get('Commands', 'Pldump_NoPlaylist', fallback=StringDefaults.pldump_noplaylist).replace('\\n', '\n')
        self.pldump_unsupported = config.get('Commands', 'Pldump_Unsupported', fallback=StringDefaults.pldump_unsupported).replace('\\n', '\n')
        self.pldump_exception = config.get('Commands', 'Pldump_Exception', fallback=StringDefaults.pldump_exception).replace('\\n', '\n')
        self.nick_noperms = config.get('Commands', 'Nick_NoPerms', fallback=StringDefaults.nick_noperms).replace('\\n', '\n')
        self.avatar_error = config.get('Commands', 'Avatar_Error', fallback=StringDefaults.avatar_error).replace('\\n', '\n')
        self.notenabled = config.get('Permissions', 'NotEnabled', fallback=StringDefaults.notenabled).replace('\\n', '\n')
        self.disabled = config.get('Permissions', 'Disabled', fallback=StringDefaults.disabled).replace('\\n', '\n')

        self.expiry_success = config.getint('Expiry', 'Success', fallback=StringDefaults.expiry_success)
        self.expiry_error = config.getint('Expiry', 'Error', fallback=StringDefaults.expiry_error)
        self.expiry_help = config.getint('Expiry', 'Help', fallback=StringDefaults.expiry_help)


class StringDefaults:
    """
        These are the default, English strings for the bot.
        Do not edit strings here. Use strings.ini in the config folder.
    """
    done = ":ok_hand:"
    pm_sent = ":mailbox_with_mail:"
    no_pm = "You cannot use this bot in private messages."

    expiry_success = 30
    expiry_error = 15
    expiry_help = 60

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
    search_noquery = "Please specify a search query.\n{doc}"
    search_result = "Result {current}/{max}: {url}"
    search_resultend = "Is this ok? Type `{yes}`, `{no}` or `{exit}`"
    search_yes = "y"
    search_no = "n"
    search_exit = "exit"

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

    skip_failure = "Can't skip! The player is not playing!"
    skip_wait = "The next song ({song}) is downloading, please wait."
    skip_acknowledge = "your skip for **{song}** was acknowledged.\nThe vote to skip has been passed."
    skip_acknowledgemore = "your skip for **{song}** was acknowledged.\n**{number}** more {people} required to vote to skip this song."
    skip_comingup = " Next song coming up!"
    skip_single = "person is"
    skip_multiple = "people are"

    volume_current = "Current volume: `{volume}`"
    volume_valueerror = "{volume} is not a valid number"
    volume_updated = "updated volume from {old} to {new}"

    queue_andmore = "* ... and {num} more*"
    queue_author = "`{num}.` **{song}** added by **{author}**"
    queue_noauthor = "`{num}.` **{author}**"

    clean_valueerror = "enter a number.  NUMBER.  That means digits.  `15`.  Etc."
    clean_success = "Cleaned up {num} message{s}."

    pldump_nodata = "Could not extract info from input url, no data."
    pldump_noplaylist = "This does not seem to be a playlist."
    pldump_unsupported = "Could not extract info from input url, unsupported playlist type."
    pldump_exception = "Could not extract info from input url\n{exception}\n"

    nick_noperms = "Unable to change nickname: no permission."
    avatar_error = "Unable to change avatar: {exception}"

    notenabled = "This command is not enabled for your group ({group})."
    disabled = "This command is disabled for your group ({group})."

    strings_file = 'config/strings.ini'
