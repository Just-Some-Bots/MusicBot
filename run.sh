#!/bin/bash

# Assuming no files have been moved, 
# make sure we're in MusicBot directory...
cd "$(dirname "$BASH_SOURCE")"

# get python version as an array, check first for python3 bin.
PY_BIN="python3"
PY_VER=($(python3 -c "import sys; print('%s %s %s' % sys.version_info[:3])" || { echo "0 0 0"; }))
if [[ "${PY_VER[0]}" == "0" ]]; then
    PY_VER=($(python -c "import sys; print('%s %s %s' % sys.version_info[:3])" || { echo "0 0 0"; }))
    PY_BIN="python"
fi
PY_VER_MAJOR=$((${PY_VER[0]}))
PY_VER_MINOR=$((${PY_VER[1]}))
PY_VER_PATCH=$((${PY_VER[2]}))
VER_GOOD=0

# echo "run.sh detected $PY_BIN version: $PY_VER_MAJOR.$PY_VER_MINOR.$PY_VER_PATCH"

# Major version must be 3+
if [[ $PY_VER_MAJOR -ge 3 ]]; then
    # If 3, minor version minimum is 3.8
    if [[ $PY_VER_MINOR -eq 8 ]]; then
        # if 3.8, patch version minimum is 3.8.7
        if [[ $PY_VER_PATCH -ge 7 ]]; then
            VER_GOOD=1
        fi
    fi
    # if 3.9+ it should work.
    if [[ $PY_VER_MINOR -ge 9 ]]; then
        VER_GOOD=1
    fi
fi

# if we don't have a good version for python, bail.
if [[ "$VER_GOOD" == "0" ]]; then
    echo "Python 3.8.7 or higher is required to run MusicBot."
    exit 1
fi

# Run python using the bin name we determined via version fetch.
# We also pass all arguments from this script into python.
$PY_BIN run.py "$@"

# exit using the code that python exited with.
exit $?
