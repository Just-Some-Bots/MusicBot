# MusicBot Translation Guide  

![Translations: 66.2%](https://img.shields.io/badge/Translations-66.2%25-orange?style=flat-square)  

MusicBot makes use of GNU Gettext for translation of display text.  
We use the typical `.po`/`.mo` file format to enable translations and bundle a few 
tools to aid contributors and users with aspects of gettext translation. 
This readme details how we use Gettext in our code and how you can update or add translations.  

The language directories you'll find or add in `./i18n/` should be named using language codes which mostly conform to the [Locale-Names specification](https://www.gnu.org/savannah-checkouts/gnu/gettext/manual/html_node/Locale-Names.html) by gettext.  

By default, MusicBot will detect and use your system language, if translations are available.  
To set a specific language, MusicBot provides these launch options:  

- `--log_lang=xx`  
  To set log language only.  
- `--msg_lang=xx`  
  To set discord default language only.  
- `--lang=xx`  
  To set both log and discord language at once.  

Replace `xx` above with the locale code of your choice. Only one language code can be set using these options.  
For more info on these, use the `--help` launch option.  

> **Note:**  Translations can also be used to customize the output of MusicBot without editing code!  

## How MusicBot loads translations  

At start-up, MusicBot looks for language files based on a longest-match first.  
For example, assume your system language is `en_GB`.  
When MusicBot starts, it will scan `./i18n/en_GB/LC_MESSAGES/` for translation files with the `.mo` extension. If that fails, bot will look for a shorter version of the language code, in this case just `./i18n/en/...` instead.  

Note that the locale codes are case-sensitive, and MusicBot will look for a directory with the exact code you provide.

> **Note:** On unix-like (Linux / Mac) systems, MusicBot makes use of the Environment Variables: `LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG` in that order.  
The first variable with a non-empty value is selected, and multiple languages may be specified in order of preference by separating them with a colon `:` character.  

## How to add a new Language  

Adding a new language to MusicBot is easy, and requires only a few tools.  Namely, an editor for the translations and an extra python package called `polib` to compile them. We will cover both later.  

MusicBot provides some `.pot` files which contain texts extracted from the source code.  You can use these to create `.po` files containing translations for the language of your choice, which are use to compile the `.mo` translation files used by MusicBot.

Here is a step by step break down of the process:  

1. Pick a language code. For example: `es_ES` as in Spanish of Spain.  
2. Create the new language directories.  
   With the example code, the path is: `./i18n/es_ES/LC_MESSAGES/`  
3. Copy the `.pot` files to the folder above, and rename them with `.po` extensions.  
4. Update the `Language:` header with the language code.  
5. Translate the strings and save the `.po` files.  
6. Use an editor or the `lang.py` script to create `.mo` files.  
7. Test your translations by launching with `run.sh --lang=es_ES`  

### What editor to use

To edit translations you'll need an editor.  Specific to Gettext, you might try [Poedit](https://poedit.net/), which is available for free on most desktop OS.  
Of course, the `.pot` and `.po` files are just plain text.  So you can edit them with any text editor if you understand the PO file format. (Visit the Gettext manual to [understand the PO format](https://www.gnu.org/software/gettext/manual/gettext.html#PO-Files))

### How to compile `.mo` files.

To compile the `.mo` files, you generally have two options.  
If you used Poedit for translations, you can also use it to compile the `.po` into a `.mo` file.  

If you edited on Crowdin and downloaded the changes or are using another editor, MusicBot provides the `lang.py` script to enable compiling on any system.  
Follow these steps to compile manually:  

1. First, make sure you've downloaded the PO files into their respective language directories.  
2. Make sure you have `polib` python package installed.  
   You can use `pip install polib` or use your system's package manager to find and install the appropriate package.  
3. Run the lang tool with `python3 lang.py -c` to compile all existing PO files.

MusicBot should now be able to use the new translations!

---

## Notes for Developers  

If you've never heard of Gettext before, getting started might be a little confusing.  For developers and users alike, you may find many answers to your questions about Gettext within the [GNU Gettext manual](https://www.gnu.org/software/gettext/manual/index.html)  

### Basics of Gettext:

- Files ending with `.pot` are templates, containing all the source strings but no translations.  
  Plain text files that you edit to make `.po` files.  
- Files ending with `.po` are fully or partially translated templates with a specific language code and meta data set.  
  Also plain-text, multiple speakers of the selected language may collaborate with this file.
- Files ending with `.mo` are compiled binary versions of the `.po` file, that make translation at runtime possible.  
  MusicBot only looks for these when loading translations.
- All changes to translations must be compiled into a `.mo` file before you can see them.
- Translations must not change/rename or add placeholders, but may remove them entirely if needed.

### Placeholders in Strings:

Regarding "placeholders", MusicBot sometimes needs to include variable data in output text.  
To do this, we use traditional percent or modulo (`%`) formatting placeholders in Python that resembles C-style `sprintf` string formatting.  
For example, the placeholders: `%(user)s` or `%s` get replaced at runtime.

These placeholders can be removed from translated strings but must not be changed or added without complimentary source code changes.  
Placeholders with no association in the source code will cause errors.  

For details on how this style of formatting works, check out the [printf-style string formatting](https://docs.python.org/3.10/library/stdtypes.html#printf-style-string-formatting) section of the python manual.

> **Note:** Some strings also contain variables in curly-braces (`{` and `}`) These may be used for simple substitutions in user-supplied data, like the bot status message.  
They are not used by Python's format functions and if changed will quietly fail to substitute.  

### Updating Source Strings

While working on MusicBot you might want to change some text in the source or add new strings for translation.  
There are some important things to remember when changing strings in source code:  

1. The string in the source code is the `msgid` in the PO files.  
  If the source string changes, the `msgid` is invalid and new translation is needed for each language.

2. MusicBot has two different message domains. One for text in the logs and the other for text sent to discord.  
   That is `musicbot_logs` and `musicbot_messages` respectively.  

3. Certain objects or function calls will mark strings as translatable but do not immediately translate them:  

   1. All `log.*()` methods mark strings as translatable in the log domain.  
      Translation is deferred until output time in the logger itself.
   2. Functions `_L` and `_Ln` mark and immediately translate in the log domain.
   3. Exceptions based on `MusicbotException` provide marking in both domains, but translation in a specific domain must be explicitly called when the exception is handled.  
   4. Function `_X` only marks in both domains, similar to Exceptions above.
   5. Functions `_D` and `_Dn` mark and immediately translate in the discord domain. While `_Dd` will only mark for deferred translation.
   6. The `_D` and `_Dn` functions require an optional `GuildSpecificData` to enable per-server language selection.

4. Finally, all changes and additional strings need to be extracted before they can be translated.  
   Developers should make sure the POT files are up-to-date when submitting source code changes.

### Using the `lang.py` script:

MusicBot provides a bundled script named `lang.py` which can accomplish a number of translation related tasks.  
Some options require the `polib` python package in order to be used.  

The script provides these command line flags:

- `-h` or `--help`  
  Shows the help message and exits.

- `-c`  
  Compile existing PO files into MO files.  
  This requires the `polib` python package.  

- `-e`  
  Extract strings into POT files.

- `-d`  
  Shows new changes to POT files without updating them.  
  This ignores gettext location comment changes.

- `-D`  
  Same as -d flat but show all changes, including comments.

- `-t`  
  Create or update the 'xx' test language.  
  The translations are reversed source strings, used to test code changes.  
  This requires the `polib` python package.

- `-s`  
  Show translation stats for existing PO files, such as completion and number of missing translations.

- `-u`  
  Extracts strings to POT files, then updates existing PO files with new strings.  

