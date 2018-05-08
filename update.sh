#!/bin/bash

# Set variables for python versions. Could probably be done cleaner, but this works.
PYTHON_VERSION_1=`python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[0]))'`
PYTHON_VERSION_2=`python -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))'`
PYTHON3_VERSION=`python3 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))'`
PYTHON35_VERSION=`python3.5 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))'`
PYTHON36_VERSION=`python3.6 -c 'import sys; version=sys.version_info[:3]; print("{0}".format(version[1]))'`

# Check if the python command is python 3.5 or greater
if [ "$PYTHON_VERSION_1" -eq "3" ]; then
    if [ "$PYTHON_VERSION_2" -ge "5" ]; then
        python update.py
    else
        echo "Your version of Python is lower than 3.5, please install a more recent version."
    fi
elif [ "$PYTHON3_VERSION" -ge "5" ]; then
    python3 update.py
# python3.5 check is to ensure that if the above two fail, the script
# doesn't attempt to run something that doesn't exist
elif [ "$PYTHON35_VERSION" -eq "5" ]; then
    python3.5 update.py
elif [ "$PYTHON36_VERSION" -eq "6" ]; then
    python3.6 update.py
else
    echo "Your version of Python is lower than 3.5, please install a more recent version."
fi