#!/bin/bash

#This file provide a new docker entrypoint which would try to update dependency before run

python3.5 -V > /dev/null 2>&1 || {
    echo >&2 "Python 3.5 doesn't seem to be installed.  Do you have a weird installation?"
    echo >&2 "If you have python 3.5, use it to run run.py instead of this script."
    exit 1; }

cd "$(dirname "$BASH_SOURCE")"

while getopts update: option
do
case "${option}"
in
update) python3.5 update.py -nopull
esac
done

python3.5 run.py