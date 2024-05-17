#!/bin/bash

# Assuming no files have been moved, 
# make sure we're in MusicBot directory...
cd "$(dirname "${BASH_SOURCE[0]}")" || { echo "Could not change directory to MusicBot."; exit 1; }

# Suported versions of python using only major.minor format
PySupported=("3.8" "3.9" "3.10" "3.11" "3.12")

# compile a list of bin names to try for.
PyBins=("python3")  # We hope that python3 maps to a good version.
for Ver in "${PySupported[@]}" ; do
    # Typical of source builds and many packages to include the dot.
    PyBins+=("python${Ver}")
    # Some distros remove the dot.
    PyBins+=("python${Ver//./}")
done
PyBins+=("python")  # Fat chance, but might as well try versionless too.

# defaults changed by the loop.
Python_Bin="python"
VerGood=0
for PyBin in "${PyBins[@]}" ; do
    if ! command -v "$PyBin" > /dev/null 2>&1 ; then
        continue
    fi

    # Get version data from python, assume python exists in PATH somewhere.
    # shellcheck disable=SC2207
    PY_VER=($($PyBin -c "import sys; print('%s %s %s' % sys.version_info[:3])" || { echo "0 0 0"; }))
    if [[ "${PY_VER[0]}" == "0" ]]; then
        echo "Error: Could not get version info from $PyBin"
        continue
    fi
    PY_VER_MAJOR=$((PY_VER[0]))
    PY_VER_MINOR=$((PY_VER[1]))
    PY_VER_PATCH=$((PY_VER[2]))
    # echo "run.sh detected $PY_BIN version: $PY_VER_MAJOR.$PY_VER_MINOR.$PY_VER_PATCH"

    # Major version must be 3+
    if [[ $PY_VER_MAJOR -ge 3 ]]; then
        # If 3, minor version minimum is 3.8
        if [[ $PY_VER_MINOR -eq 8 ]]; then
            # if 3.8, patch version minimum is 3.8.7
            if [[ $PY_VER_PATCH -ge 7 ]]; then
                VerGood=1
                Python_Bin="$PyBin"
                break
            fi
        fi
        # if 3.9+ it should work.
        if [[ $PY_VER_MINOR -ge 9 ]]; then
            VerGood=1
            Python_Bin="$PyBin"
            break
        fi
    fi
done

# if we don't have a good version for python, bail.
if [[ "$VerGood" == "0" ]]; then
    echo "Python 3.8.7 or higher is required to run MusicBot."
    exit 1
fi

echo "Using '${Python_Bin}' to launch MusicBot..."
# Run python using the bin name we determined via version fetch.
# We also pass all arguments from this script into python.
$Python_Bin run.py "$@"

# exit using the code that python exited with.
exit $?
