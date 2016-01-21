import sys, os, traceback, subprocess, webbrowser


class GIT(object):

    @classmethod
    def works(cls):
        try:
            return bool(subprocess.check_output('git --version', shell=True))
        except:
            return False


# TODO: Try "sys.argv[0] -m pip ..." variant, and use import as backup
class PIP(object):

    looked_for = False
    use_import = True
    pip_command = None

    @classmethod
    def run(cls, command, use_command=False, quiet=False, check_output=False):
        if not cls.works():
            raise RuntimeError("PIP could not be located or imported.")

        check = subprocess.check_output if check_output else subprocess.check_call

        if cls.use_import:
            try:
                return check("{} -m pip {}{}".format(
                    sys.executable,
                    '-q ' if quiet else '',
                    command).split(), shell=True)

            except:
                traceback.print_exc()
                print("Error using pip import")
                # Using fallback...?
                # rerun this commanmd with use_command if pip_command is not none

        elif use_command and cls.pip_command is not None:
            try:
                return check("{} {}{}".format(
                    cls.pip_command,
                    '-q ' if quiet else '',
                    command).split(), shell=True)
            except subprocess.CalledProcessError as e:
                return e.returncode
        else:
            raise RuntimeError("PIP was not located, cannot run commands.")

    @classmethod
    def run_install(cls, cmd, use_import=False, quiet=False, check_output=False):
        return cls.run("install %s" % cmd, use_import, quiet, check_output)

    @classmethod
    def run_show(cls, cmd, use_import=False, quiet=False, check_output=False):
        return cls.run("show %s" % cmd, use_import, quiet, check_output)

    @classmethod
    def works(cls):
        if not cls.looked_for:
            cls.find_pip3()

        return cls.use_import or cls.pip_command

    @classmethod
    def find_pip3(cls):
        cls.looked_for = True

        try:
            import pip
            cls.use_import = True
        except:
            print("Tried to import pip but it failed. This does not bode well.")

        if cls._check_command_exists('pip3.5 -V'):
            cls.pip_command = 'pip3.5'

        elif cls._check_command_exists('pip3 -V'):
            if subprocess.check_output('pip3 -V', shell=True).strip().endswith('(python 3.5)'):
                cls.pip_command = 'pip3'

        elif cls._check_command_exists('pip -V'):
            if subprocess.check_output('pip -V', shell=True).strip().endswith('(python 3.5)'):
                cls.pip_command = 'pip'

        return cls.works()

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

    @staticmethod
    def _check_command_exists(cmd):
        try:
            subprocess.check_output(cmd, shell=True)
            return True
        except subprocess.CalledProcessError:
            return True
        except:
            traceback.print_exc()
            return False


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
                pycom = subprocess.check_output(['which', 'python3.5'])
            except:
                pass

            if pycom:
                print("\nPython 3 found.  Re-launching bot using: ")
                print("  %s run.py\n" % pycom)
                os.system("kill -9 %s && %s run.py" % (os.getpid(), pycom))
                # If the process isn't killed by now then bugger it
                # sys.exit(0)


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
                print("Attempting to install dependencies...")
                tried_requirementstxt = True
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

    # TODO: Clean up redundant code from before I added the requirements.txt install code

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
