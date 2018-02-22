#!/bin/bash

python3.5 -V /dev/null 2>&1 ||{
	echo >&2 "Python 3.5 doesn't seem to be installed."
}

cd "$(dirname "$BASH_SOURCE")"
python3.5 run.py
