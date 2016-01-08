import sys, os, traceback, subprocess, webbrowser

def check_for_git():
    try:
        return bool(subprocess.check_output('git --version'))
    except:
        return False

def check_for_pip():
    try:
        return bool(subprocess.check_output('pip -V'))
    except:
        return False

def check_for_module_pip(mod):
    import pip
    return pip.main(['-q', 'show', mod]) == 0

def get_module_version(mod):
    # if not check_for_pip() blah blah blah
    try:
        out = subprocess.check_output('pip show %s' % mod, )
        datas = str(out).split('\\r\\n')
        expectedversion = datas[3]

        if expectedversion.startswith('Version: '):
            return expectedversion.split()[1]
        else:
            return [x.split()[1] for x in datas if x.startswith("Version: ")][0]
    except:
        pass

def install_module(mod, quiet=False):
    # TODO: Error code checks, I got 2 for permission denied (needs admin to write)
    try:
        import pip
        return pip.main(["-q", "install"] + mod.split() if quiet else ["install"] + mod.split())
    except:
        if check_for_pip():
            return subprocess.check_call("pip %sinstall %s" % ('-q ' if quiet else '', mod))

def open_in_wb(text, printanyways=True, indents=4):
    import webbrowser
    if isinstance(webbrowser.get(), webbrowser.BackgroundBrowser):
        print('%s%s' % (' ' * indents , text))
    else:
        webbrowser.open_new_tab(text)
        if printanyways:
            print('%s%s' % (' ' * indents , text))


def main():
    if not sys.version.startswith("3.5"):
        print("Python 3.5+ is required. This version is %s" % sys.version.split()[0])
        print("Attempting to locate python 3.5...")

        try:
            subprocess.check_output('py -3.5 -c "exit()"')
            print("Python 3.5 found.  Launching bot...")
            os.system('start cmd /k py -3.5 run.py')

            from random import sample
            titlenum = ''.join(map(str, sample(range(50000), 6)))
            titlestuff = str(hex(int(titlenum)))[2:]

            print(titlestuff)
            os.system('title %s' % titlestuff)
            os.system('taskkill /fi "WindowTitle eq %s"' % titlestuff)

        except:
            traceback.print_exc()
            input("Press any key to continue . . .")
            # check other locations or some shit

        return

    tried_requirementstxt = False
    tryagain = True

    while tryagain:
        tryagain = False

        try:
            from musicbot import MusicBot
            MusicBot().run()
            break

        except ImportError as e:
            traceback.print_exc()

            if not tried_requirementstxt:
                err = install_module('-r requirements.txt', True)
                tried_requirementstxt = True

                if err == 2:
                    print("\nIf that said \"Access is denied\", run it as admin.")
                    break

            if e.name in ['discord', 'opus', 'win_unicode_console']:
                tryagain = unfuck(e)

def unfuck(e):
    try:
        import pip
    except:
        if not check_for_pip():
            print("Additionally, pip cannot be imported. Has python been installed properly?")
            print("Bot setup instructions can be found here:")
            open_in_wb("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

    print()

    if e.name == 'discord':
        if check_for_module_pip('discord.py'):
            return True

        print("Discord.py is not installed.")

        if not check_for_git():
            print("Additionally, git is also not installed.  Please install git.")
            print("Bot setup instructions can be found here:")
            open_in_wb("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

        err = install_module("git+https://github.com/Rapptz/discord.py@async")

        if err:
            print()
            print("Could not install discord.py for you. Please run:")
            print("    pip install git+https://github.com/Rapptz/discord.py@async")

        else:
            print("Ok, maybe we're good?")
            print()
            return True

    elif e.name == 'opus':
        print("Discord.py is out of date. Did you install the old version?")

        err = install_module("--upgrade git+https://github.com/Rapptz/discord.py@async")

        if err:
            print()
            print("Could not update discord.py for you. Please run:")
            print("    pip install --upgrade git+https://github.com/Rapptz/discord.py@async")
        else:
            print("Ok, maybe we're good?")
            print()
            return True

    elif e.name == 'win_unicode_console':
        if check_for_module_pip('win_unicode_console'):
            return True

        print("Module 'win_unicode_console' is missing.")

        err = install_module("win_unicode_console")

        if err:
            print()
            print("Could not install win_unicode_console for you. Please run:")
            print("    pip install win_unicode_console")
        else:
            print("Ok, maybe we're good?")
            print()
            return True


if __name__ == '__main__':
    main()
