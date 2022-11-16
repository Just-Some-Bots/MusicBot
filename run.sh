#!/bin/bash

# Ensure we're in the MusicBot directory
cd "$(dirname "$BASH_SOURCE")"

# Set variables for python versions. Could probably be done cleaner, but this works.
declare -A python=(["0"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[0]))' || { echo "no py"; }) ["1"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py"; }) ["2"]=$(python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[2]))' || { echo "no py"; }))
declare -A python3=(["0"]=$(python3 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py3"; }) ["1"]=$(python3 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[2]))' || { echo "no py3"; }))
PYTHON38_VERSION=$(python3.8 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py38"; })
PYTHON39_VERSION=$(python3.9 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))' || { echo "no py39"; })

if [ "${python[0]}" -eq "3" ]; then         # Python = 3
    if [ "${python[1]}" -eq "8" ]; then     # Python = 3.8
        if [ "${python[2]}" -ge "7" ]; then # Python = 3.8.7
            python run.py
            exit
        fi
    elif [ "${python[1]}" -ge "9" ]; then # Python >= 3.9
        python run.py
        exit
    fi
fi

if [ "${python3[0]}" -eq "8" ]; then     # Python3 = 3.8
    if [ "${python3[1]}" -ge "7" ]; then # Python3 >= 3.8.7
        python3 run.py
        exit
    fi
fi

if [ "${python3[0]}" -ge "9" ]; then # Python3 >= 3.9
    python3 run.py
    exit
fi

if [ "$PYTHON38_VERSION" -eq "8" ]; then # Python3.8 = 3.8
    python3.8 run.py
    exit
fi

if [ "$PYTHON39_VERSION" -eq "9" ]; then # Python3.9 = 3.9
    python3.9 run.py
    exit
fi
echo "You are running an unsupported Python version."
echo "Please use a version of Python above 3.8.7."
