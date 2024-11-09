#! /usr/bin/env python3
# Written by Martin v. Löwis <loewis@informatik.hu-berlin.de>

"""Generate binary message catalog from textual translation description.

This program converts a textual Uniforum-style message catalog (.po file) into
a binary GNU catalog (.mo file).  This is essentially the same function as the
GNU msgfmt program, however, it is a simpler implementation.  Currently it
does not handle plural forms but it does handle message contexts.

Usage: msgfmt.py [OPTIONS] filename.po

Options:
    -o file
    --output-file=file
        Specify the output file to write to.  If omitted, output will go to a
        file named filename.mo (based off the input file name).

    -h
    --help
        Print this message and exit.

    -V
    --version
        Display version information and exit.
"""

import array
import ast
import getopt
import os
import struct
import sys
from email.parser import HeaderParser

__version__ = "1.2"

MESSAGES = {}


def usage(code, msg=""):
    """
    Display some usage text and exit.
    Shows program usage if no msg text is given.
    """
    print(__doc__, file=sys.stderr)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)


def add(ctxt, msgid, msgstr, fuzzy):
    "Add a non-fuzzy translation to the dictionary."
    global MESSAGES  # pylint: disable=global-variable-not-assigned
    if not fuzzy and msgstr:
        if ctxt is None:
            MESSAGES[msgid] = msgstr
        else:
            MESSAGES[b"%b\x04%b" % (ctxt, msgid)] = msgstr


def generate():
    "Return the generated output."
    global MESSAGES  # pylint: disable=global-variable-not-assigned
    # the keys are sorted in the .mo file
    keys = sorted(MESSAGES.keys())
    offsets = []
    ids = strs = b""
    for msgid in keys:
        # For each string, we need size and file offset.  Each string is NUL
        # terminated; the NUL does not count into the size.
        offsets.append((len(ids), len(msgid), len(strs), len(MESSAGES[msgid])))
        ids += msgid + b"\0"
        strs += MESSAGES[msgid] + b"\0"
    output = ""
    # The header is 7 32-bit unsigned integers.  We don't use hash tables, so
    # the keys start right after the index tables.
    # translated string.
    keystart = 7 * 4 + 16 * len(keys)
    # and the values start after the keys
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    # The string table first has the list of keys, then the list of values.
    # Each entry has first the size of the string, then the file offset.
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    offsets = koffsets + voffsets
    output = struct.pack(
        "Iiiiiii",
        0x950412DE,  # Magic
        0,  # Version
        len(keys),  # # of entries
        7 * 4,  # start of key index
        7 * 4 + len(keys) * 8,  # start of value index
        0,
        0,
    )  # size and offset of hash table
    output += array.array("i", offsets).tobytes()
    output += ids
    output += strs
    return output


def make(filename, outfile):
    """Function to create a .mo from a given .po file."""
    ID = 1  # pylint: disable=invalid-name
    STR = 2  # pylint: disable=invalid-name
    CTXT = 3  # pylint: disable=invalid-name

    # Compute .mo name from .po name and arguments
    if filename.endswith(".po"):
        infile = filename
    else:
        infile = filename + ".po"
    if outfile is None:
        outfile = os.path.splitext(infile)[0] + ".mo"

    try:
        with open(infile, "rb") as f:
            lines = f.readlines()
    except IOError as msg:
        print(msg, file=sys.stderr)
        sys.exit(1)

    section = msgctxt = None
    fuzzy = 0

    # Start off assuming Latin-1, so everything decodes without failure,
    # until we know the exact encoding
    encoding = "latin-1"

    # Parse the catalog
    lno = 0
    for line in lines:
        line = line.decode(encoding)
        lno += 1
        msgid = msgstr = b""
        # If we get a comment line after a msgstr, this is a new entry
        if line[0] == "#" and section == STR:
            add(msgctxt, msgid, msgstr, fuzzy)
            section = msgctxt = None
            fuzzy = 0
        # Record a fuzzy mark
        if line[:2] == "#," and "fuzzy" in line:
            fuzzy = 1
        # Skip comments
        if line[0] == "#":
            continue
        # Now we are in a msgid or msgctxt section, output previous section
        if line.startswith("msgctxt"):
            if section == STR:
                add(msgctxt, msgid, msgstr, fuzzy)
            section = CTXT
            line = line[7:]
            msgctxt = b""
        elif line.startswith("msgid") and not line.startswith("msgid_plural"):
            if section == STR:
                add(msgctxt, msgid, msgstr, fuzzy)
                if not msgid:
                    # See whether there is an encoding declaration
                    p = HeaderParser()
                    charset = p.parsestr(msgstr.decode(encoding)).get_content_charset()
                    if charset:
                        encoding = charset
            section = ID
            line = line[5:]
            msgid = msgstr = b""
            is_plural = False
        # This is a message with plural forms
        elif line.startswith("msgid_plural"):
            if section != ID:
                print(
                    f"msgid_plural not preceded by msgid on {infile}:{lno}",
                    file=sys.stderr,
                )
                sys.exit(1)
            line = line[12:]
            msgid += b"\0"  # separator of singular and plural
            is_plural = True
        # Now we are in a msgstr section
        elif line.startswith("msgstr"):
            section = STR
            if line.startswith("msgstr["):
                if not is_plural:
                    print(
                        f"plural without msgid_plural on {infile}:{lno}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                line = line.split("]", 1)[1]
                if msgstr:
                    msgstr += b"\0"  # Separator of the various plural forms
            else:
                if is_plural:
                    print(
                        f"indexed msgstr required for plural on  {infile}:{lno}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                line = line[6:]
        # Skip empty lines
        line = line.strip()
        if not line:
            continue
        line = ast.literal_eval(line)
        if section == CTXT:
            msgctxt += line.encode(encoding)
        elif section == ID:
            msgid += line.encode(encoding)
        elif section == STR:
            msgstr += line.encode(encoding)
        else:
            print(f"Syntax error on {infile}:{lno} before:", file=sys.stderr)
            print(line, file=sys.stderr)
            sys.exit(1)
    # Add last entry
    if section == STR:
        add(msgctxt, msgid, msgstr, fuzzy)

    # Compute output
    output = generate()

    try:
        with open(outfile, "wb") as f:
            f.write(output)
    except IOError as msg:
        print(msg, file=sys.stderr)


def main():
    """Program entry point."""
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "hVo:", ["help", "version", "output-file="]
        )
    except getopt.error as msg:
        usage(1, msg)

    outfile = None
    # parse options
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(0)
        elif opt in ("-V", "--version"):
            print("msgfmt.py", __version__)
            sys.exit(0)
        elif opt in ("-o", "--output-file"):
            outfile = arg
    # do it
    if not args:
        print("No input file given", file=sys.stderr)
        print("Try `msgfmt --help' for more information.", file=sys.stderr)
        return

    for filename in args:
        make(filename, outfile)


if __name__ == "__main__":
    main()
