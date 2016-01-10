import sys, os, traceback, subprocess, webbrowser


class GIT(object):

    @classmethod
    def works(cls):
        try:
            return bool(subprocess.check_output('git --version', shell=True))
        except:
            return False

# TODO: Maybe I should only check for if you can import pip.  It seems like more if an issue if you can't

class PIP(object):

    looked_for = False
    pip_command = None
    use_import = False

    @classmethod
    def run(cls, command, use_import=False, quiet=False, check_output=False):
        if not cls.works():
            raise RuntimeError("Unable to locate pip")

        check = subprocess.check_output if check_output else subprocess.check_call

        if cls.use_import or use_import:
            try:
                import pip
                return pip.main(["-q"] + command.split() if quiet else command.split())
            except:
                traceback.print_exc()
                print("Error using pip import")
        else:
            try:
                return check("{} {}{}".format(
                    cls.pip_command,
                    '-q ' if quiet else '',
                    command), shell=True)
            except subprocess.CalledProcessError as e:
                return e.returncode

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

        return cls.pip_command or cls.use_import

    @classmethod
    def find_pip3(cls):
        cls.looked_for = True

        if cls._check_command_exists('pip3.5 -V'):
            cls.pip_command = 'pip3.5'

        elif cls._check_command_exists('pip3 -V'):
            if subprocess.check_output('pip3 -V', shell=True).strip().endswith('(python 3.5)'):
                cls.pip_command = 'pip3'

        elif cls._check_command_exists('pip -V'):
            if subprocess.check_output('pip -V', shell=True).strip().endswith('(python 3.5)'):
                cls.pip_command = 'pip'
        else:
            try:
                import pip
                cls.use_import = True
            except:
                pass

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
    if isinstance(webbrowser.get(), webbrowser.BackgroundBrowser):
        print('%s%s' % (' ' * indents , text))
    else:
        webbrowser.open_new_tab(text)
        if printanyways:
            print('%s%s' % (' ' * indents , text))


def main():
    if not sys.version.startswith("3.5"):
        print("Python 3.5+ is required. This version is %s" % sys.version.split()[0])

        if sys.platform.startswith('win'):
            print("Attempting to locate python 3.5...")

            pycom = None

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

        print("Please run the bot using python 3.5")
        input("Press enter to continue . . .")

        return

    if '--upgrade' in sys.argv:
        # MOAR CHECKS?
        err = PIP.run_install('--upgrade -r requirements.txt', quiet=True)
        if err == 2:
            print("Upgrade failed, you may need to run it as admin")
        elif err:
            print("Automatic upgrade failed")

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
                err = PIP.run_install('-r requirements.txt', quiet=True)

                if err == 2:
                    print("\nIf that said \"Access is denied\", run it as admin.")
                    break

            if e.name in ['discord', 'opus', 'win_unicode_console']:
                tryagain = unfuck(e)

def unfuck(e):
    try:
        import pip
    except:
        if not PIP.works():
            print("Additionally, pip cannot be imported. Has python been installed properly?")
            print("Bot setup instructions can be found here:")
            open_in_wb("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

    print()

    # TODO: Clean up redundant code from before I added the requirements.txt install code

    if e.name == 'discord':
        if check_for_module_pip('discord.py'):
            return True

        print("Discord.py is not installed.")

        if not GIT.works():
            print("Additionally, git is also not installed.  Please install git.")
            print("Bot setup instructions can be found here:")
            open_in_wb("https://github.com/SexualRhinoceros/MusicBot/blob/develop/README.md")
            return

        err = PIP.run_install("git+https://github.com/Rapptz/discord.py@async")

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

        err = PIP.run_install("--upgrade git+https://github.com/Rapptz/discord.py@async")

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

        err = PIP.run_install("win_unicode_console")

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
