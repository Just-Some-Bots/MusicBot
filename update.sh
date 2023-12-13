#!/bin/bash

# Ensure we're in the MusicBot directory
cd "$(dirname "$BASH_SOURCE")"

# Set variables for python versions. Could probably be done cleaner, but this works.
declare -A python=(["0"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[0]))' || { echo "no py"; }) ["1"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py"; }) ["2"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[2]))' || { echo "no py"; }))
declare -A python3=(["0"]=$(python3 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py3"; }) ["1"]=$(python3 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[2]))' || { echo "no py3"; }))
PYTHON39_VERSION=$(python3.9 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py39"; })
PYTHON310_VERSION=$(python3.10 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py310"; })
PYTHON311_VERSION=$(python3.11 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py311"; })
PYTHON312_VERSION=$(python3.12 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py312"; })

if [ "${python[0]}" -eq "3" ]; then         # Python = 3
    if [ "${python[1]}" -eq "9" ]; then     # Python = 3.9
        if [ "${python[2]}" -ge "18" ]; then # Python = 3.9.18
            python update.py
            exit
        fi
    elif [ "${python[1]}" -gt "10" ]; then # Python >= 3.10
        python update.py
        exit
    fi
fi

if [ "${python3[0]}" -eq "9" ]; then     # Python3 = 3.9
    if [ "${python3[1]}" -ge "18" ]; then # Python3 >= 3.9.18
        python3 update.py
        exit
    fi
fi

if [ "${python3[0]}" -ge "10" ]; then # Python3 >= 3.10
    python3 update.py
    exit
fi

if [ "$PYTHON39_VERSION" -eq "9" ]; then # Python3.9 = 3.9
    python3.9 update.py
    exit
fi

if [ "$PYTHON310_VERSION" -eq "10" ]; then # Python3.10 = 3.10
    python3.10 update.py
    exit
fi

if [ "$PYTHON311_VERSION" -eq "11" ]; then # Python3.11 = 3.11
    python3.11 update.py
    exit
fi

if [ "$PYTHON312_VERSION" -eq "12" ]; then # Python3.12 = 3.12
    python3.12 update.py
    exit
fi

echo "You are running an unsupported Python version."
echo "Please use a version of Python above 3.9.18."
