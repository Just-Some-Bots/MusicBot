#!/usr/bin/env python3
#This file provide a new docker entrypoint which would try to update dependency before run

import os
import subprocess
import sys

update = False
    for arg in sys.argv[1:]:
        if arg == "-update":
            update = True

if update:
    subprocess.run('python3.5 update.py -nopull')

subprocess.run('python3.5 run.py')
