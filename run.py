import sys, os, traceback, subprocess, webbrowser


class GIT(object):

    @classmethod
    def works(cls):
        try:
            return bool(subprocess.check_output('git --version', shell=True))
        except:
            return False


class PIP(object):

    @classmethod
    def run(cls, command, quiet=False, check_output=False):
        if not cls.works():
            raise RuntimeError("Could not import pip.")

        check = subprocess.check_output if check_output else subprocess.check_call
        fullcommand = [sys.executable] + "-m pip {}{}".format('-q ' if quiet else '', command).split()

        try:
            return check(fullcommand, shell=True)

        except:
            traceback.print_exc()
            raise RuntimeError("Failed to run command: %s" % fullcommand)

    @classmethod
    def run_install(cls, cmd, quiet=False, check_output=False):
        return cls.run("install %s" % cmd, quiet, check_output)

    @classmethod
    def run_show(cls, cmd, quiet=False, check_output=False):
        return cls.run("show %s" % cmd, quiet, check_output)

    @classmethod
    def works(cls):
        try:
            import pip
            return True
        except ImportError:
            return False

    @classmethod
    def get_module_version(cls, mod):
        try:
            out = cls.run_show(mod, check_output=True)
            datas = str(out).split('\\r\\n')
            expectedversion = datas[3]

            if expectedversion.startswith('Version: '):
                return expectedversion.split()[1]
            else:
                return [x.split()[1] for x in datas if x.startswith("Version: ")][0]
        except:
            pass


def open_in_wb(text, printanyways=True, indents=4):
    import webbrowser
    # TODO: Figure out console browser stuff
    # also check GenericBrowser
    if isinstance(webbrowser.get(), webbrowser.BackgroundBrowser):
        print('%s%s' % (' ' * indents , text))
    else:
        webbrowser.open_new_tab(text)
        if printanyways:
            print('%s%s' % (' ' * indents , text))


def main():
    if not sys.version_info >= (3, 5):
        print("Python 3.5+ is required. This version is %s" % sys.version.split()[0])
        print("Attempting to locate python 3.5...")

        pycom = None

        # Maybe I should check for if the current dir is the musicbot folder, just in case

        if sys.platform.startswith('win'):
            try:
                subprocess.check_output('py -3.5 -c "exit()"', shell=True)
                pycom = 'py -3.5'
            except:

                try:
                    subprocess.check_output('python3 -c "exit()"', shell=True)
                    pycom = 'python3'
                except:
                    pass

            if pycom:
                print("Python 3 found.  Launching bot...")
                os.system('start cmd /k %s run.py' % pycom)
                sys.exit(0)

        else:
            try:
                pycom = subprocess.check_output(['which', 'python3.5']).strip().decode()
            except:
                pass

            if pycom:
                print("\nPython 3 found.  Re-launching bot using: ")
                print("  %s run.py\n" % pycom)

                os.system("kill -9 %s && %s run.py" % (os.getpid(), pycom))


        print("Please run the bot using python 3.5")
        input("Press enter to continue . . .")

        return


    if '--update' in sys.argv:
        if PIP.works():
            err = PIP.run_install('--upgrade -r requirements.txt', quiet=True)
            print()

            if err:
                if err == 2:
                    print("Upgrade failed, you may need to run it as admin/root")

                else:
                    print("Automatic upgrade failed")

                input("Press enter to continue . . .")
                return

        else:
            print("\n"
                "Could not locate PIP. If you're sure you have it, run this:\n"
                "  your_pip_command install --upgrade -r requirements.txt"
                "\n\n")

            input("Press enter to continue . . .")
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
                tried_requirementstxt = True
                print("Attempting to install dependencies...")
                err = PIP.run_install('-r requirements.txt', quiet=True)

                if err == 2:
                    print("\nIf that said \"Access/Permission is denied\", run it as admin/with sudo.")
                    break

            if e.name in ['discord', 'opus', 'win_unicode_console']:
                tryagain = unfuck(e)
                if not tryagain:
                    input('Press enter to continue . . .')


def unfuck(e):
    try:
        import pip
    except:
        if not PIP.works():
            print("Additionally, pip cannot be imported. Has python been installed properly?")
            print("Bot setup instructions can be found here:")
            print("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

    print()

    if e.name == 'discord':
        if PIP.get_module_version('discord.py'):
            return True

        print("Discord.py is not installed.")

        if not GIT.works():
            print("Additionally, git is also not installed.  Please install git.")
            print("Bot setup instructions can be found here:")
            print("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

        print("Attempting to install discord.py")
        err = PIP.run_install("git+https://github.com/Rapptz/discord.py@async", quiet=True)

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

        print("Attempting to upgrade discord.py")
        err = PIP.run_install("--upgrade git+https://github.com/Rapptz/discord.py@async", quiet=True)

        if err:
            print()
            print("Could not update discord.py for you. Please run:")
            print("    pip install --upgrade git+https://github.com/Rapptz/discord.py@async")
        else:
            print("Ok, maybe we're good?")
            print()
            return True

    elif e.name == 'win_unicode_console':
        if PIP.get_module_version('win-unicode-console'):
            return True

        print("Module 'win_unicode_console' is missing.")

        print("Attempting to install win_unicode_console")
        err = PIP.run_install("win-unicode-console", quiet=True)

        if err:
            print()
            print("Could not install win_unicode_console for you. Please run:")
            print("    pip install win-unicode-console")
        else:
            print("Ok, maybe we're good?")
            print()
            return True


if __name__ == '__main__':
    main()
