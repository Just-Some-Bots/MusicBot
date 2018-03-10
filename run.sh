#!/bin/bash

(command -v python3 >/dev/null 2>&1 &&
python3 -c 'import sys; sys.exit(sys.hexversion < 0x03050000)') || {
	echo >&2 "Python 3.5 or later not found."
	echo >&2 "If you have python, use it to run run.py."
	exit 1; }

cd "$(dirname "$BASH_SOURCE")"
python3 run.py
