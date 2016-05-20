#!/bin/bash

cd "$(dirname "$BASH_SOURCE")" || {
	echo "Python 3.5 doesn't seem to be installed" >&2
exit 1
}

python3.5 -m pip install --upgrade -r requirements.txt
