# MusicBot Translation Guide  

![Translations: 66.2%](https://img.shields.io/badge/Translations-66.2%25-orange?style=flat-square)  

MusicBot provides some support for translations and customized display text.  
This guide will explain how you can make use of this feature for specific goals.  

<details>
  <summary> Getting Started </summary>  

## Getting started

Before you begin, there are some details you should be aware of.  

MusicBot provides two domains for text:  
- `musicbot_logs` - Text shown primarilly in logs or console.  
- `musicbot_messages` - Text shown primarilly on discord.  

Translation files use the GNU Gettext file formats. Those are:  
- `.pot` - A blank template, with text extracted from source code but no translations.
- `.po` - Similar to POT, with full or partial translations and a specific language code.
- `.mo` - A compiled version of PO file, used at runtime.  MusicBot will compile these automatically.  

The `.po` and `.pot` files are plain-text files.  
You can edit them with a dedicated translation editor, like [Poedit](https://poedit.net/) 
or with a code/text editor application.  
For plain-text editing, please read the [PO-Files](https://www.gnu.org/software/gettext/manual/gettext.html#PO-Files) section of Gettext manual for details on the contents of a PO file and specific meanings.  

Official languages use the Gettext [Locale-Names specification](https://www.gnu.org/savannah-checkouts/gnu/gettext/manual/html_node/Locale-Names.html) for compatibility with system language codes.  
Users should review the above specification when picking language codes for contributing new languages or to avoid conflicts between "custom" codes and official codes.  

Lastly, MusicBot provides four ways to set language:  
- Command line options:  
  - `--lang=` - Set language for logs and discord text.  
  - `--log_lang=` - Set language for only the log text.  
  - `--msg_lang=` - Set language for only discord text.  
- Runtime commands:  
  - `language` - Set or reset a per-server language selection.  
                 This will override command line options or the default language.  

---

</details>



<details>
  <summary> How To Customize Text </summary>

## How to customize text

To customize MusicBot text you have two options:  
- Edit the source code directly.  
- Edit a translation file.  

We recommend copying an existing language and making edits to it.  
This will make it easy to keep your changes when MusicBot updates, if there are changes to language files.  

The basic steps are:  
1. Copy your language folder, for example: `en_US`  
2. Rename it but avoid using existing locale codes. For example: `xx_custom`  
3. Next open the file `xx_custom/LC_MESSAGES/musicbot_messages.po` to make desired changes.
4. Run the bot with `--lang=xx_custom` as a command line option.

---

</details>



<details>
  <summary> Adding a Language </summary>

## Adding a new language

Adding a language is almost as simple as customizing text, you only need the language code for your language of choice.  
Follow these steps to add a new language:  
1. Select a valid language code which conforms to the [Locale-Names specification](https://www.gnu.org/savannah-checkouts/gnu/gettext/manual/html_node/Locale-Names.html)
2. Create the required files and folders using the language tool:  
   `lang.py --new=LOCALE` replace `LOCALE` with your desired language code.
3. Open the new `.po` files and start translating.

---

</details>



<details>
  <summary> Notes for Source Code </summary>

## Notes for Source Code

### Placeholders in Strings:

Regarding "placeholders", MusicBot sometimes needs to include variable data in output text.  
To do this, we use traditional percent or modulo (`%`) formatting placeholders in Python that resembles C-style `sprintf` string formatting.  
For example, the placeholders: `%(user)s` or `%s` get replaced at runtime with potentially non-translatable data.

These placeholders can be removed from translated strings but must not be changed or added without complimentary source code changes.  
Placeholders with no association in the source code will cause errors.  
Placeholders removed from a string will not.  

For details on how this style of formatting works, check out the [printf-style string formatting](https://docs.python.org/3.10/library/stdtypes.html#printf-style-string-formatting) section of the python manual.

> **Note:** Some strings also contain variables in curly-braces (`{` and `}`) These may be used for simple substitutions in user-supplied data, like the bot status message.  
They are not used by Python's format functions and if changed may quietly fail to substitute.  

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
   Developers should make sure to run `lang.py -u` to update the `.pot` and existing `.po` files when they make changes.  

---

</details>



<details>
  <summary> About Bundled Scripts </summary>  

## About bundled scripts  

The scripts contained in the `i18n` directory provide cross-platform tools to aid in translation tasks.  
Each script supports the `-h` or `--help` command line option to display usage documentation.  

A breif summary for each script file:  
- `lang.py`  -  Language tool, the primary script used for most translation tasks.  
- `msgfmt.py`  -  Modified version of python's msgfmt compatible utility.  
- `pygettext.py`  -  Modified version of python's xgettext compatible utility.  

<details>
  <summary> lang.py command line options </summary>

### `lang.py` Command line options:

The script provides these command line flags:

- `-h` or `--help`  
  Shows the help message and exits.  

- `-L [LOCALE]`  
  Select a single language code to run tasks on, instead of all installed languages.

- `-c`  
  Compile existing translation PO files into MO files.
  This requires the `polib` python package.

- `-e`  
  Extract strings from source-code to POT files (blank translation templates.)

- `-d`  
  Show differences between source-code extractions and the existing POT files.  
  Comments and line markers are hidden.  

- `-D`  
  Same as argument -d but shows all changes, including comments and line markers.  

- `-t`  
  Create or update the 'xx' test language.
  This requires the `polib` python package.

- `-s`  
  Show translation stats for existing PO files, by extracting strings from sources first.
  This requires the `polib` python package.

- `-J`  
  Save stats to JSON for use in the repository.  
  Use with -s option.

- `-B`  
  Save stats will save badges to use in the repository.  
  Use with `-s` option.  

- `-u`  
  Update all existing translation files (PO & POT) from source-code.  
  Existing translation files will have new strings to translate.  
  This requires the `polib` python package.

- `-A`  
  Update all missing translations in PO files with Argos-translate machine translations.  
  This requires the `polib` as well as `argostranslate` and `marko` python packages.  

- `--new [LOCALE]`  
  Create a new language with code LOCALE.  
  This creates folders and PO files ready for translation.  

- `--jit-mo`  
  Automatically compile MO files if PO files contain different translations or headers.  
  This requires the `polib` python package.

</details>

---

</details>

