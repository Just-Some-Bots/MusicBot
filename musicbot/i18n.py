import argparse
import builtins
import ctypes
import gettext
import locale
import logging
import os
import pathlib
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict, List, NoReturn, Optional, Union

from .constants import (
    DEFAULT_I18N_DIR,
    DEFAULT_I18N_LANG,
    I18N_DISCORD_TEXT_DOMAIN,
    I18N_LOGFILE_TEXT_DOMAIN,
)

if TYPE_CHECKING:
    from .constructs import GuildSpecificData

log = logging.getLogger(__name__)

Translations = Union[gettext.GNUTranslations, gettext.NullTranslations]


def _X(msg: str) -> str:  # pylint: disable=invalid-name
    """
    Mark a string for translation in all message domains.
    Strings marked are extractable but must be translated explicitly at runtime.
    """
    return msg


def _L(msg: str) -> str:  # pylint: disable=invalid-name
    """
    Marks strings for translation as part of logs domain.
    Is a shorthand for gettext() in the log domain.
    Overloaded by I18n.install() for translations.
    """
    if builtins.__dict__["_L"]:
        return str(builtins.__dict__["_L"](msg))
    return msg


def _Ln(msg: str, plural: str, n: int) -> str:  # pylint: disable=invalid-name
    """
    Marks plurals for translation as part of logs domain.
    Is a shorthand for ngettext() in the logs domain.
    Overloaded by I18n.install() for translations.
    """
    if builtins.__dict__["_Ln"]:
        return str(builtins.__dict__["_Ln"](msg, plural, n))
    return msg


def _D(  # pylint: disable=invalid-name
    msg: str, ssd: Optional["GuildSpecificData"]
) -> str:
    """
    Marks strings for translation as part of discord domain.
    Is a shorthand for I18n.sgettext() in the discord domain.
    Overloaded by I18n.install() for translations.
    """
    if builtins.__dict__["_D"]:
        return str(builtins.__dict__["_D"](msg, ssd))
    return msg


def _Dn(  # pylint: disable=invalid-name
    msg: str, plural: str, n: int, ssd: Optional["GuildSpecificData"]
) -> str:
    """
    Marks strings for translation as part of discord domain.
    Is a shorthand for I18n.sngettext() in the discord domain.
    Overloaded by I18n.install() for translations.
    """
    if builtins.__dict__["_Dn"]:
        return str(builtins.__dict__["_Dn"](msg, plural, n, ssd))
    return msg


def _Dd(msg: str) -> str:  # pylint: disable=invalid-name
    """
    Marks strings for translation as part of discord domain.
    Translation is deferred until later in runtime.
    """
    return msg


class I18n:
    """
    This class provides a utility to set up i18n via GNU gettext with automatic
    discovery of system language options as well as optional language overrides.
    Importantly, this class allows for per-guild language selection at runtime.

    The class will return gettext.GNUTranslation objects for language files
    contained within the following directory and file structure:
      [localedir] / [lang_code] / LC_MESSAGES / [domain].mo

    All [lang_code] portions are case sensitive!

    If a file cannot be found with the desired or a default language, a warning
    will be issued and strings will simply not be translated.

    By default, I18n.install() is called by init, and will make several functions
    available in global space to enable translations.
    These enable marking translations in different domains as well as providing
    for language selection in server-specific cases.
    See I18n.install() for details on global functions.
    """

    _i18n_compiled: bool = False

    def __init__(
        self,
        localedir: Optional[pathlib.Path] = None,
        log_lang: str = "",
        msg_lang: str = "",
        auto_install: bool = True,
    ) -> None:
        """
        Initialize the i18n system, detecting system language immediately.

        :param: `localedir` An optional base path, if omitted DEFAULT_I18N_DIR constant will be used instead.
        :param: `log_lang` An optional language selection for log text that takes preference over defaults.
        :param: `msg_lang` An optional language selection for discord text that is prefered over defaults.
        :param: `auto_install` Automaticlly add global functions for translations.
        """
        # Make sure all po changes are compiled to mo files.
        # This is an Ouroboros. It's fine...
        try:
            if not I18n._i18n_compiled:
                subprocess.check_call([sys.executable, "./i18n/lang.py", "--jit-mo"])
                I18n._i18n_compiled = True
        except (OSError, ValueError, subprocess.CalledProcessError):
            I18n._i18n_compiled = True
            print("Auto-compile MO files failed.")

        # set the path where translations are stored.
        if localedir:
            self._locale_dir: pathlib.Path = localedir
        else:
            self._locale_dir = pathlib.Path(DEFAULT_I18N_DIR)
        self._locale_dir = self._locale_dir.absolute()
        self._show_sys_lang: bool = False

        # system default lanaguage code(s) if any.
        self._sys_langs: List[str] = []
        self._log_lang: str = ""
        self._msg_lang: str = ""

        # check for command line args "--lang" etc.
        self._get_lang_args()

        # selected language for logs.
        if log_lang:
            self._log_lang = log_lang

        # selected language for discord messages.
        if msg_lang:
            self._msg_lang = msg_lang

        # lang-code map to avoid the lookup overhead.
        self._discord_langs: Dict[int, Translations] = {}

        self._get_sys_langs()

        if auto_install:
            self.install()

    @property
    def default_langs(self) -> List[str]:
        """
        A list containing only the system and default language codes.
        This will always contain at least the MusicBot default language constant.
        """
        langs = self._sys_langs.copy()
        langs.append(DEFAULT_I18N_LANG)
        return langs

    @property
    def log_langs(self) -> List[str]:
        """A list of language codes used for discord messages, ordered by preference."""
        if self._log_lang:
            langs = self.default_langs
            langs.insert(0, self._log_lang)
            return langs
        return self.default_langs

    @property
    def msg_langs(self) -> List[str]:
        """A list of language codes used for discord messages, ordered by preference."""
        if self._msg_lang:
            langs = self.default_langs
            langs.insert(0, self._msg_lang)
            return langs
        return self.default_langs

    def _get_sys_langs(self) -> None:
        """
        Checks the system environment for language codes.
        """
        if os.name == "nt":
            # Windows yet again needs cytpes here, the gettext lib does not do this for us.
            windll = ctypes.windll.kernel32  # type: ignore[attr-defined]
            lang = locale.windows_locale[windll.GetUserDefaultUILanguage()]
            if lang:
                self._sys_langs = [lang]
        else:
            # check for language environment variables, but only use the first one.
            for envar in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
                val = os.environ.get(envar)
                if val:
                    self._sys_langs = val.split(":")
                    break
        if self._show_sys_lang:
            print(f"System language code(s):  {self._sys_langs}")

    def _get_lang_args(self) -> None:
        """
        Creates a stand alone, mostly silent, ArgumentParser to find command line
        args related to i18n as early as possible.
        """
        args39plus: Dict[str, Any] = {}
        if sys.version_info >= (3, 9):
            args39plus = {"exit_on_error": False}

        ap = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            usage="",
            description="",
            epilog="",
            allow_abbrev=False,
            add_help=False,
            **args39plus,
        )

        # Make sure argparser does not exit or print.
        def _error(message: str) -> NoReturn:  # type: ignore[misc]
            log.debug("Lang Argument Error:  %s", message)

        ap.error = _error  # type: ignore[method-assign]

        ap.add_argument(
            "--log_lang",
            dest="lang_logs",
            type=str,
            help="",
            default=DEFAULT_I18N_LANG,
        )
        ap.add_argument(
            "--msg_lang",
            dest="lang_msgs",
            type=str,
            help="",
            default=DEFAULT_I18N_LANG,
        )
        ap.add_argument(
            "--lang",
            dest="lang_both",
            type=str,
            help="",
            default=DEFAULT_I18N_LANG,
        )
        ap.add_argument(
            "--show_sys_lang",
            dest="show_sys_lang",
            action="store_true",
            help="",
        )

        # parse the lang args.
        args, _ = ap.parse_known_args()
        if args.show_sys_lang:
            self._show_sys_lang = True
        if args.lang_both and args.lang_both != DEFAULT_I18N_LANG:
            self._log_lang = args.lang_both
            self._msg_lang = args.lang_both
            # print(f"Lang Both:  {args.lang_both}")
        if args.lang_logs and args.lang_logs != DEFAULT_I18N_LANG:
            self._log_lang = args.lang_logs
            # print(f"Lang Logs:  {args.lang_logs}")
        if args.lang_msgs and args.lang_msgs != DEFAULT_I18N_LANG:
            self._msg_lang = args.lang_msgs
            # print(f"Lang Msgs:  {args.lang_msgs}")

    def get_log_translations(self) -> Translations:
        """
        Attempts to fetch and return a translation object for one of the languages
        contained within `I18n.log_langs` list.
        """
        t = gettext.translation(
            I18N_LOGFILE_TEXT_DOMAIN,
            localedir=self._locale_dir,
            languages=self.log_langs,
            fallback=True,
        )

        if not isinstance(t, gettext.GNUTranslations):
            log.warning(
                "Failed to load log translations for any of:  [%s]  in:  %s",
                ", ".join(self.log_langs),
                self._locale_dir,
            )

        # print(f"Logs using lanaguage: {t.info()['language']}")

        return t

    def get_discord_translation(
        self, ssd: Optional["GuildSpecificData"]
    ) -> Translations:
        """
        Get a translation object for the given `lang` in the discord message domain.
        If the language is not available a fallback from msg_langs will be used.
        """
        # Guild 0 is a fall-back used by non-guild messages.
        guild_id = 0
        if ssd:
            guild_id = ssd.guild_id

        # return mapped translations, to avoid lookups.
        if guild_id in self._discord_langs:
            tl = self._discord_langs[guild_id]
            lang_loaded = tl.info().get("language", "")
            if ssd and lang_loaded == ssd.lang_code:
                return tl
            if not guild_id:
                return tl

        # add selected lang as first option.
        msg_langs = list(self.msg_langs)
        if ssd and ssd.lang_code:
            msg_langs.insert(0, ssd.lang_code)

        # get the translations object.
        tl = gettext.translation(
            I18N_DISCORD_TEXT_DOMAIN,
            localedir=self._locale_dir,
            languages=msg_langs,
            fallback=True,
        )
        # add object to the mapping.
        self._discord_langs[guild_id] = tl

        # warn for missing translations.
        if not isinstance(tl, gettext.GNUTranslations):
            log.warning(
                "Failed to load discord translations for any of:  [%s]  guild:  %s  in:  %s",
                ", ".join(msg_langs),
                guild_id,
                self._locale_dir,
            )

        return tl

    def reset_guild_language(self, guild_id: int) -> None:
        """
        Clear the translation object mapping for the given guild ID.
        """
        if guild_id in self._discord_langs:
            del self._discord_langs[guild_id]

    def sgettext(self, msg: str, ssd: Optional["GuildSpecificData"]) -> str:
        """
        Fetch the translation object using server specific data and provide
        gettext() call for the guild's language.
        """
        t = self.get_discord_translation(ssd)
        return t.gettext(msg)

    def sngettext(
        self, signular: str, plural: str, n: int, ssd: "GuildSpecificData"
    ) -> str:
        """
        Fetch the translation object using server specific data and provide
        ngettext() call for the guild's language.
        """
        t = self.get_discord_translation(ssd)
        return t.ngettext(signular, plural, n)

    def install(self) -> None:
        """
        Registers global functions for translation domains used by MusicBot.
        It will map the following names as global functions:

         _L()  = gettext.gettext()  in log text domain.
         _Ln() = gettext.ngettext() in log text domain.
         _D()  = gettext.gettext()  in discord text domain.
         _Dn() = gettext.ngettext() in discord text domain.
        """
        log_tl = self.get_log_translations()
        builtins.__dict__["_L"] = log_tl.gettext
        builtins.__dict__["_Ln"] = log_tl.ngettext
        builtins.__dict__["_D"] = self.sgettext
        builtins.__dict__["_Dn"] = self.sngettext
