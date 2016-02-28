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
    def run(cls, command, check_output=False):
        if not cls.works():
            raise RuntimeError("Could not import pip.")

        try:
            return PIP.run_python_m(*command.split(), check_output=check_output)
        except subprocess.CalledProcessError as e:
            return e.returncode
        except:
            traceback.print_exc()
            print("Error using -m method")

    @classmethod
    def run_python_m(cls, *args, **kwargs):
        check_output = kwargs.pop('check_output', False)
        check = subprocess.check_output if check_output else subprocess.check_call
        return check([sys.executable, '-m', 'pip'] + list(args))

    @classmethod
    def run_pip_main(cls, *args, **kwargs):
        import pip

        args = list(args)
        check_output = kwargs.pop('check_output', False)

        if check_output:
            from io import StringIO

            out = StringIO()
            sys.stdout = out

            try:
                pip.main(args)
            except:
                traceback.print_exc()
            finally:
                sys.stdout = sys.__stdout__

                out.seek(0)
                pipdata = out.read()
                out.close()

                print(pipdata)
                return pipdata
        else:
            return pip.main(args)

    @classmethod
    def run_install(cls, cmd, quiet=False, check_output=False):
        return cls.run("install %s%s" % ('-q ' if quiet else '', cmd), check_output)

    @classmethod
    def run_show(cls, cmd, check_output=False):
        return cls.run("show %s" % cmd, check_output)

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

            if isinstance(out, bytes):
                out = out.decode()

            datas = out.replace('\r\n', '\n').split('\n')
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

                os.execlp(pycom, pycom, 'run.py')


        print("Please run the bot using python 3.5")
        input("Press enter to continue . . .")

        return


    if '--update' in sys.argv:
        if PIP.works():
            try:
                err = PIP.run_install('--upgrade -r requirements.txt')
            except subprocess.CalledProcessError as err:
                print("\nUpgrade failed, you may need to run it as admin/root")
                input("Press enter to continue . . .")
                return

        else:
            # TODO: Make this text less questionable
            print("\n"
                "Could not locate PIP. If you're sure you have it, run this:\n"
                "  your_pip_command install --upgrade -r requirements.txt"
                "\n\n")

            input("Press enter to continue . . .")
            return


    tried_requirementstxt = False
    tryagain = True

    while tryagain:
        try:
            from musicbot import MusicBot
            MusicBot().run()
            break # check if restart? replace process?

        except ImportError as e:
            print(e)

            if not tried_requirementstxt:
                tried_requirementstxt = True
                # TODO: Better output
                print("Attempting to install dependencies...")

                err = PIP.run_install('-r requirements.txt')

                if err:
                    print("\nYou may need to %s to install dependencies." %
                        ['use sudo', 'run as admin'][sys.platform.startswith('win')])
                    break
                else:
                    print("\nOk lets hope it worked\n")


if __name__ == '__main__':
    main()
