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
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-U', '-r', 'requirements.txt'])

subprocess.run([sys.executable, 'run.py'])
