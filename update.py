#!/usr/bin/env python3

import os
import subprocess
import sys

async def _input(prompt = ''):
    return input(prompt)

async def _print(*values, sep = ' ', end = '\n', file = sys.stdout, flush = False):
    print(*values, sep = sep, end = end, file = file, flush = flush)

async def y_n(q, read = _input):
    while True:
        ri = await read('{} (y/n): '.format(q))
        if ri.lower() in ['yes', 'y']: return True
        elif ri.lower() in ['no', 'n']: return False

async def update_deps(write = _print):
    await write("Attempting to update dependencies...")

    try:
        subprocess.check_call('"{}" -m pip install --no-warn-script-location --user -U -r requirements.txt'.format(sys.executable), shell=True)
    except subprocess.CalledProcessError:
        raise OSError("Could not update dependencies. You will need to run '\"{0}\" -m pip install -U -r requirements.txt' yourself.".format(sys.executable))

async def finalize(write = _print):
    try:
        from musicbot.constants import VERSION
        await write('The current MusicBot version is {0}.'.format(VERSION))
    except Exception:
        await write('There was a problem fetching your current bot version. The installation may not have completed correctly.')

    await write("Done!")

async def _main(read = _input, write = _print):
    await write('Starting...')

    # Make sure that we're in a Git repository
    if not os.path.isdir('.git'):
        raise EnvironmentError("This isn't a Git repository.")

    # Make sure that we can actually use Git on the command line
    # because some people install Git Bash without allowing access to Windows CMD
    try:
        subprocess.check_call('git --version', shell=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise EnvironmentError("Couldn't use Git on the CLI. You will need to run 'git pull' yourself.")

    await write("Passed Git checks...")

    # Check that the current working directory is clean
    sp = subprocess.check_output('git status --porcelain', shell=True, universal_newlines=True)
    if sp:
        oshit = await y_n('You have modified files that are tracked by Git (e.g the bot\'s source files).\n'
                          'Should we try resetting the repo? You will lose local modifications.',
                          read = read)
        if oshit:
            try:
                subprocess.check_call('git reset --hard', shell=True)
            except subprocess.CalledProcessError:
                raise OSError("Could not reset the directory to a clean state.")
        else:
            wowee = await y_n('OK, skipping bot update. Do you still want to update dependencies?',
                              read = read)
            if wowee:
                await update_deps(write = write)
            else:
                await finalize(write = write)
            return

    print("Checking if we need to update the bot...")

    
    try:
        subprocess.check_call('git pull', shell=True)
    except subprocess.CalledProcessError:
        raise OSError("Could not update the bot. You will need to run 'git pull' yourself.")

    await update_deps(write = write)
    await finalize(write = write)

def main():
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_main())

if __name__ == '__main__':
    main()
