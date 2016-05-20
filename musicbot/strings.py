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
        self.play_noplaylists = config.get('Commands', 'Play_NoPlaylists', fallback=StringDefaults.play_noplaylists)
        self.play_pltoomanyentries = config.get('Commands', 'Play_PlTooManyEntries', fallback=StringDefaults.play_pltoomanyentries)


class StringDefaults:
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
    play_noplaylists = "You are not allowed to request playlists"
    play_pltoomanyentries = "Playlist has too many entries ({songs} > {max})"

    strings_file = 'config/strings.ini'
