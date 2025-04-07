#!/bin/bash
#
# MusicBot and this file are provided under an MIT license. 
# Please see the LICENSE file for details.
#
# This file attempts to provide automatic install of MusicBot and dependencies on
# a variety of different Linux distros.
# 

#-----------------------------------------------------------------------------------------------------#
# Check if this script is being run on windows and redirect the user.  
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] ; then
    echo "install.sh is not for Windows.  Use the install.bat file instead."
    read -rp "Press any key to exit."
    exit 2
fi


#-----------------------------------------------Configs-----------------------------------------------#
MusicBotGitURL="https://github.com/Just-Some-Bots/MusicBot.git"
CloneDir="MusicBot"
VenvDir="MusicBotVenv"
InstallDir=""
ServiceName="musicbot"

EnableUnlistedBranches=0
DEBUG=0


#----------------------------------------------Constants----------------------------------------------#
# Suported versions of python using only major.minor format
PySupported=("3.13" "3.12" "3.11" "3.10" "3.9")
PyBin="python3"
# Path updated by find_python
PyBinPath="$(command -v "$PyBin")"

# Status indicator for post-install notice about python venv based install.
InstalledViaVenv=0

# Get some notion of the current OS / distro name.
# This will not exhaust options, or ensure a correct name is returned. 
# A good example is Raspberry Pi OS 11 which returns Debian.
if [ -n "$(command -v lsb_release)" ] ; then
    # Most debian-based distros might have this installed, but not always.
    # Redhat-based distros usually need to install it via redhat-lsb-core package.
    DISTRO_NAME=$(lsb_release -s -d)
elif [ -f "/etc/os-release" ]; then
    # Many distros have this file, but not all of them are version complete.
    # For example, CentOS 7 will return "CentOS Linux 7 (Core)"
    # If we need to know the minor version, we need /etc/redhat-release instead.
    # Same for Debian, which uses /etc/debian_version file instead.
    DISTRO_NAME=$(grep PRETTY_NAME /etc/os-release | sed 's/PRETTY_NAME=//g' | tr -d '="')
elif [ -f "/etc/debian_version" ]; then
    DISTRO_NAME="Debian $(cat /etc/debian_version)"
elif [ -f "/etc/redhat-release" ]; then
    DISTRO_NAME=$(cat /etc/redhat-release)
else
    # In case everything fails, use Kernel name and release.
    DISTRO_NAME="$(uname -s) $(uname -r)"
fi

#----------------------------------------------Functions----------------------------------------------#
function get_supported() {
    # Search this file and extract names from the supported cases below.
    # We control which cases we grab based on the space at the end of each 
    # case pattern, before ) or | characters.
    # This allows adding complex cases which will be excluded from the list.
    Avail=$(grep -oh '\*"[[:alnum:] _!\./]*"\*[|)]' "$0" )
    Avail="${Avail//\*\"/}"
    Avail="${Avail//\"\*/}"
    Avail="${Avail//[|)]/}"
    echo "$Avail"
}

function distro_supported() {
    # Loops over "supported" distros and color-codes the current distro.
    OIFS=$IFS
    IFS=$'\n'
    for dist in $(get_supported) ; do
        debug "Testing '$dist' in '$DISTRO_NAME'"
        if [[ "$DISTRO_NAME" == *"$dist"* ]] ; then
            echo -e "\e[1;32m${DISTRO_NAME}\e[0m"
            IFS=$OIFS
            return 0
        fi
    done
    IFS=$OIFS
    echo -e "\e[1;33m${DISTRO_NAME}\e[0m"
    return 1
}

function list_supported() {
    # List off "supported" linux distro/versions if asked to and exit.
    echo "We detected your OS is:  $(distro_supported)"
    echo ""
    echo "The MusicBot installer might have support for these flavors of Linux:"
    get_supported
    echo ""
    exit 0
}

function show_help() {
    # provide help text for the installer and exit.
    echo "MusicBot Installer script usage:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "By default, the installer script installs as the user who runs the script."
    echo "The user should have permission to install system packages using sudo."
    echo "Do NOT run this script with sudo, you will be prompted when it is needed!"
    echo "To bypass steps that use sudo, use --no-sudo or --no-sys as desired."
    echo " Note: Your system admin must install the packages before hand, by using:"
    echo "   $0 --sys-only"
    echo ""
    echo "Available Options:"
    echo ""
    echo "  --list      List potentially supported versions and exits."
    echo "  --help      Show this help text and exit."
    echo "  --sys-only  Install only system packages, no bot or pip libraries."
    echo "  --service   Install only the system service for MusicBot."
    echo "  --no-sys    Bypass system packages, install bot and pip libraries."
    echo "  --no-sudo   Skip all steps that use sudo. This implies --no-sys."
    echo "  --debug     Enter debug mode, with extra output. (for developers)"
    echo "  --any-branch    Allow any existing branch to be given at the branch prompt. (for developers)"
    echo "  --dir [PATH]    Directory into which MusicBot will be installed. Default is user Home directory."
    echo ""
    exit 0
}

function exit_err() {
    echo "$@"
    exit 1
}

function build_python() {
    # check if python already built
    if in_venv ; then
        if find_python_venv ; then
            echo ""
            echo "Python already built/installed @ ${PyBinPath}"
            echo "Skipping build steps."
            return 0
        fi
    else
        if find_python ; then
            echo ""
            echo "Python already built/installed @ ${PyBinPath}"
            echo "Skipping build steps."
            return 0
        fi
    fi

    # actually build python
    PyBuildVer="3.10.14"
    PySrcDir="Python-${PyBuildVer}"
    PySrcFile="${PySrcDir}.tgz"
    PySrcUrl="https://www.python.org/ftp/python/${PyBuildVer}/${PySrcFile}"
    
    # Ask if we should build python
    echo "We need to build python from source for your system."
    echo "It will be installed using the altinstall target to avoid conflicts."
    echo "This process can take several minutes!"
    echo " Building Python ${PyBuildVer}  from: ${PySrcUrl}"
    read -rp "Would you like to continue ? [N/y]" BuildPython
    if [ "${BuildPython,,}" == "y" ] || [ "${BuildPython,,}" == "yes" ] ; then
        # Build python.
        curl -o "$PySrcFile" "$PySrcUrl"
        tar -xzf "$PySrcFile"
        cd "${PySrcDir}" || exit_err "Fatal:  Could not change to python source directory."

        ./configure --enable-optimizations
        $SUDO_BIN make altinstall

        # make sure to leave the build dir.
        cd .. || exit_err "Fatal:  Could not change directory to parent of python source directory."
        # TODO: maybe we should clean up the build/source/download but I cba.

        # Ensure python bin is updated with altinstall name.
        find_python
        RetVal=$?
        if [ "$RetVal" == "0" ] ; then
            # check if pip is available
            $PyBin -m pip --version >/dev/null 2>&1
            if [ "$?" == "1" ] ; then
                # manually install pip package for current user.
                $PyBin <(curl -s https://bootstrap.pypa.io/get-pip.py)
            fi
        else
            echo "Error:  Could not find python on the PATH after installing it."
            exit 1
        fi
    else
        echo ""
        echo "To build Python ${PyBuildVer} manually, use these commands:"
        echo "  curl -o '${PySrcFile}' '${PySrcUrl}'"
        echo "  tar -xzf '${PySrcFile}'"
        echo "  cd '${PWD}/${PySrcDir}'"
        echo "  ./configure --enable-optimizations"
        echo "  sudo make altinstall"
        echo ""
        echo ""
        find_python
    fi
}

function find_python() {
    # compile a list of bin names to try for.
    PyBins=("python3")  # We hope that python3 maps to a good version.
    for Ver in "${PySupported[@]}" ; do
        # Typical of source builds and many packages to include the version dot.
        PyBins+=("python${Ver}")
        # Some distros remove the dot.
        PyBins+=("python${Ver//./}")
    done
    PyBins+=("python")  # Fat chance, but might as well try versionless too.

    # Test each possible PyBin until the first supported version is found.
    for PyBinTest in "${PyBins[@]}" ; do
        if ! command -v "$PyBinTest" > /dev/null 2>&1 ; then
            continue
        fi

        # Get version data from python, assume python exists in PATH somewhere.
        # shellcheck disable=SC2207
        PY_VER=($($PyBinTest -c "import sys; print('%s %s %s' % sys.version_info[:3])" || { echo "0 0 0"; }))
        if [[ "${PY_VER[0]}" == "0" ]]; then
            continue
        fi
        PY_VER_MAJOR=$((PY_VER[0]))
        PY_VER_MINOR=$((PY_VER[1]))
        # PY_VER_PATCH=$((PY_VER[2]))
        # echo "run.sh detected $PY_BIN version: $PY_VER_MAJOR.$PY_VER_MINOR.$PY_VER_PATCH"

        # Major version must be 3+
        if [[ $PY_VER_MAJOR -ge 3 ]]; then
            # if 3.9+ it should work.
            if [[ $PY_VER_MINOR -ge 9 ]]; then
                PyBinPath="$(which "$PyBinTest")"
                PyBin="$PyBinTest"
                debug "Selected: $PyBinTest  @  $PyBinPath"
                return 0
            fi
        fi
    done

    PyBinPath="$(which "python3")"
    PyBin="python3"
    debug "Default: python3  @  $PyBinPath"
    return 1
}

function find_python_venv() {
    # activates venv, locates python bin, deactivates venv.
    # shellcheck disable=SC1091
    source "../bin/activate"
    find_python
    PyFound=$?
    deactivate
    return $PyFound
}

function in_existing_repo() {
    # check the current working directory is a MusicBot repo clone.
    GitDir="${PWD}/.git"
    BotDir="${PWD}/musicbot"
    ReqFile="${PWD}/requirements.txt"
    RunFile="${PWD}/run.py"
    if [ -d "$GitDir" ] && [ -d "$BotDir" ] && [ -f "$ReqFile" ] && [ -f "$RunFile" ]; then
        return 0
    fi
    return 1
}

function in_venv() {
    # Check if the current directory is inside a Venv, does not activate.
    # Assumes the current directory is a MusicBot clone.
    if [ -f "../bin/activate" ] ; then
        return 0
    fi
    return 1
}

function pull_musicbot_git() {
    echo ""
    # Check if we're running inside a previously pulled repo.
    # ignore this if InstallDir is set.
    if in_existing_repo && [ "$InstallDir" == "" ]; then
        echo "Existing MusicBot repo detected."
        read -rp "Would you like to install using the current repo? [Y/n]" UsePwd
        if [ "${UsePwd,,}" == "y" ] || [ "${UsePwd,,}" == "yes" ] ; then
            echo ""
            CloneDir="${PWD}"
            
            # find python before using it.
            find_python

            # install / upgrade pip packages
            $PyBin -m pip install --upgrade pip
            $PyBin -m pip install --upgrade -r requirements.txt
            echo ""

            # copy an empty options file if one does not exist.
            if [ ! -f "./config/options.ini" ] ; then
                echo "Creating default options.ini file from example_options.ini file."
                echo ""
                cp ./config/example_options.ini ./config/options.ini
            fi
            return 0
        fi
        echo "Installer will attempt to create a new directory for MusicBot."
    fi

    # test if we install at home-directory or a specified path.
    if [ "$InstallDir" == "" ] && [ "$InstalledViaVenv" == "0" ] ; then
        cd ~ || exit_err "Fatal:  Could not change into home directory."
        if [ -d "${CloneDir}" ] ; then
            echo "Error: A directory named ${CloneDir} already exists in your home directory."
            exit_err "Delete the ${CloneDir} directory and try again, or complete the install manually."
        fi
    else
        cd "$InstallDir" || exit_err "Fatal:  Could not change into install directory:  ${InstallDir}"
        if [ "$InstalledViaVenv" != "1" ] ; then
            CloneDir="${InstallDir}"
        fi
    fi

    echo ""
    echo "MusicBot currently has three branches available."
    echo "  master - An older MusicBot, for older discord.py. May not work without tweaks!"
    echo "  review - Newer MusicBot, usually stable with less updates than the dev branch."
    echo "  dev    - The newest MusicBot, latest features and changes which may need testing."
    if [ "$EnableUnlistedBranches" == "1" ] ; then
    echo "  *      - WARNING: Any branch name is allowed, if it exists on github."
    fi
    echo ""
    read -rp "Enter the branch name you want to install:  " BRANCH
    case ${BRANCH,,} in
    "dev")
        echo "Installing from 'dev' branch..."
        git clone "${MusicBotGitURL}" "${CloneDir}" -b dev
        ;;
    "review")
        echo "Installing from 'review' branch..."
        git clone "${MusicBotGitURL}" "${CloneDir}" -b review
        ;;
    "master")
        echo "Installing from 'master' branch..."
        git clone "${MusicBotGitURL}" "${CloneDir}" -b master
        ;;
    *)
        if [ "$EnableUnlistedBranches" == "1" ] ; then
            echo "Installing from '${BRANCH}' branch..."
            git clone "${MusicBotGitURL}" "${CloneDir}" -b "$BRANCH"
        else
            exit_err "Unknown branch name given, install cannot continue."
        fi
        ;;
    esac
    cd "${CloneDir}" || exit_err "Fatal:  Could not change to MusicBot directory."

    # find python before using it
    find_python

    # update pip first
    $PyBin -m pip install --upgrade pip
    # install / upgrade pip packages
    $PyBin -m pip install --upgrade -r requirements.txt
    echo ""

    # copy the options file if none exists.
    if ! [ -f ./config/options.ini ] ; then
        echo "Creating default options.ini file from example_options.ini file."
        echo ""
        cp ./config/example_options.ini ./config/options.ini
    fi
}

function install_as_venv() {
    # Create and activate a venv using python that is installed.
    find_python

    # adjust the VenvDir and move our clone if needed.
    if ! in_venv ; then
        if in_existing_repo && [ "$InstallDir" == "" ] ; then
            CloneDir="${PWD}"
            CloneDirName="$(basename "$PWD")"
            cd .. || exit_err "Failed to leave cloned directory."

            $PyBin -m venv "${VenvDir}"

            echo "Installer needs to move your clone inside the Venv."
            echo " - moving $CloneDirName into $VenvDir"
            mv "$CloneDir" "${VenvDir}/$CloneDirName"
            cd "${VenvDir}/$CloneDirName" || exit_err "Failed to enter clone directory."
        else
            if [ "$InstallDir" != "" ] && [ -d "$InstallDir" ] ; then
                cd "$InstallDir" || exit_err "Fatal:  could not change into install directory."
            else
                cd ~ || exit_err "Fatal:  Could not change into home directory."
            fi
            $PyBin -m venv "${VenvDir}"
            cd "${VenvDir}" || exit_err "Failed to enter Venv directory."
            # shellcheck disable=SC1091
            source "./bin/activate"
        fi
    else
        echo "Python Venv already exits."
    fi

    InstalledViaVenv=1
    if [ -f ../bin/activate ] ; then
        # shellcheck disable=SC1091
        source "../bin/activate"
    fi
    find_python

    pull_musicbot_git

    # exit venv
    deactivate
}

function issue_root_warning() {
    echo "Just like my opinion, but root and MusicBot shouldn't mix."
    echo "The installer will prevent this for the benefit of us all."
}

function ask_for_user() {
    # ask the user to supply a valid username. It must exist already.
    while :; do
        echo ""
        read -rp "Please enter an existing User name:  " Inst_User
        if id -u "$Inst_User" >/dev/null 2>&1; then
            if [ "${Inst_User,,}" == "root" ] ; then
                issue_root_warning
                echo "Try again."
                Inst_User=""
            else
                return 0
            fi
        else
            echo "Username does not exist!  Try again."
            Inst_User="$(id -un)"
        fi
    done
}

function ask_for_group() {
    # ask the user to supply a valid group name. It must exist already.
    while :; do
        echo ""
        read -rp "Please enter an existing Group name:  " Inst_Group
        if id -g "$Inst_Group" >/dev/null 2>&1 ; then
            if [ "${Inst_Group,,}" == "root" ] ; then
                issue_root_warning
                echo "Try again."
                Inst_Group=""
            else
                return 0
            fi
        else
            echo "Group does not exist!  Try again."
            Inst_Group="$(id -gn)"
        fi
    done
}

function ask_change_user_group() {
    User_Group="${Inst_User} / ${Inst_Group}"
    echo ""
    echo "The installer is currently running as:  ${User_Group}"
    read -rp "Set a different User / Group to run the service? [N/y]: " MakeChange
    case $MakeChange in
    [Yy]*)
        ask_for_user
        ask_for_group
    ;;
    esac
}

function ask_change_service_name() {
    echo ""
    echo "The service will be installed as:  $ServiceName"
    read -rp "Would you like to change the name? [N/y]: " ChangeSrvName
    case $ChangeSrvName in
    [Yy]*)
        while :; do
            # ASCII letters, digits, ":", "-", "_", ".", and "\"
            # but I know \ will complicate shit. so no thanks, sysD.
            echo ""
            echo "Service names may use only letters, numbers, and the listed special characters."
            echo "Spaces are not allowed. Special characters:  -_.:"
            read -rp "Provide a name for the service:  " ServiceName
            # validate service name is allowed.
            if [[ "$ServiceName" =~ ^[a-zA-Z0-9:-_\.]+$ ]] ; then
                # attempt to avoid conflicting service names...
                if ! systemctl list-unit-files "$ServiceName" &>/dev/null ; then
                    return 0
                else
                    echo "A service by this name already exists, try another."
                fi
            else
                echo "Invalid service name, try again."
            fi
        done
    ;;
    esac
}

function generate_service_file() {
    # generate a .service file in the current directory.
    cat << EOSF > "$1"
[Unit]
Description=Just-Some-Bots/MusicBot a discord.py bot that plays music.

# Only start this service after networking is ready.
After=network.target


[Service]
# If you do not set these, MusicBot may run as root!  You've been warned!
User=${Inst_User}
Group=${Inst_Group}

# Replace with a path where MusicBot was cloned into.
WorkingDirectory=${PWD}

# Here you need to use both the correct python path and a path to run.py
ExecStart=${PyBinPath} ${PWD}/run.py --no-checks

# Set the condition under which the service should be restarted.
# Using on-failure allows the bot's shutdown command to actually stop the service.
# Using always will require you to stop the service via the service manager.
Restart=on-failure

# Time to wait between restarts.  Useful to avoid rate limits.
RestartSec=8


[Install]
WantedBy=default.target

EOSF

}

function setup_as_service() {
    # Provide steps to generate and install a .service file

    # check for existing repo or install --dir option.
    if ! in_existing_repo ; then
        if [ "$InstallDir" != "" ]; then
            cd "$InstallDir" || { exit_err "Could not cd to the supplied install directory."; }

            # if we still aren't in a valid repo, warn the user but continue on.
            if ! in_existing_repo ; then
                echo "WARNING:"
                echo "  Installer is generating a service file without a valid install!"
                echo "  The generated file may not contain the correct paths to python or run.py"
                echo "  Manually edit the service file or re-run using a valid install directory."
                echo ""
            fi
        else
            echo "The installer cannot generate a service file without an existing installation."
            echo "Please add the --dir option or install the MusicBot first."
            echo ""
            return 1
        fi
    fi

    # check if we're in a venv install.
    if in_venv ; then
        debug "Detected a Venv install"
        find_python_venv
    else
        find_python
    fi

    # TODO: should we assume systemd is all?  perhaps check for it first...

    Inst_User="$(id -un)"
    Inst_Group="$(id -gn)"
    echo ""
    echo "The installer can also install MusicBot as a system service."
    echo "This starts the MusicBot at boot and restarts after failures."
    read -rp "Install the musicbot system service? [N/y] " SERVICE
    case $SERVICE in
    [Yy]*)
        ask_change_service_name
        ask_change_user_group

        if [ "$Inst_User" == "" ] ; then
            echo "Cannot set up the service with a blank User name."
            return 1
        fi
        if [ "$Inst_Group" == "" ] ; then
            echo "Cannot set up the service with a blank Group name."
            return 1
        fi

        SrvCpyFile="./${ServiceName}.service"
        SrvInstFile="/etc/systemd/system/${ServiceName}.service"
        
        echo ""
        echo "Setting up MusicBot as a service named:  ${ServiceName}"
        echo "Generated File:  ${SrvCpyFile}"

        generate_service_file "${SrvCpyFile}"
        
        if [ "$SKIP_ALL_SUDO" == "0" ] ; then
            # Copy the service file into place and enable it.
            $SUDO_BIN cp "${SrvCpyFile}" "${SrvInstFile}"
            $SUDO_BIN chown root:root "$SrvInstFile"
            $SUDO_BIN chmod 644 "$SrvInstFile"
            $SUDO_BIN systemctl daemon-reload
            $SUDO_BIN systemctl enable "$ServiceName"

            echo "Installed File:  ${SrvInstFile}"

            echo ""
            echo "MusicBot will start automatically after the next reboot."
            read -rp "Would you like to start MusicBot now? [N/y]" StartService
            case $StartService in
            [Yy]*)
                echo "Running:  sudo systemctl start $ServiceName"
                $SUDO_BIN systemctl start "$ServiceName"
            ;;
            esac
        else
            echo "Installing of generated service skipped, sudo is required to install it."
            echo "The file was left on disk so you can manually install it."
        fi
        echo ""
        ;;
    esac
    return 0
}

function debug() {
    local msg=$1
    if [[ $DEBUG == '1' ]]; then
        echo -e "\e[1;36m[DEBUG]\e[0m $msg" 1>&2
    fi
}

function configure_bot() {
    if in_venv ; then
        if [ -f "../bin/activate" ] ; then
            # shellcheck disable=SC1091
            source "../bin/activate"
        fi
        if [ -f "./bin/activate" ] ; then
            # shellcheck disable=SC1091
            source "./bin/activate"
        fi
    fi
    find_python

    echo "You can now configure MusicBot!"
    read -rp "Would you like to launch the 'configure.py' tool? [N/y]" YesConfig
    if [[ "${YesConfig,,}" != "y" && "${YesConfig,,}" != "yes" ]] ; then
        echo ""
        echo "Open the 'config' directory, then copy and rename the example files to get started."
        echo "Make sure to add your Bot token to the options.ini 'Token' option before starting."
        return
    fi

    $PyBin "configure.py"
    
    if in_venv ; then
        deactivate
    fi
}

#------------------------------------------CLI Arguments----------------------------------------------#
INSTALL_SYS_PKGS="1"
INSTALL_BOT_BITS="1"
SERVICE_ONLY="0"
SKIP_ALL_SUDO="0"

while [[ $# -gt 0 ]]; do
  case ${1,,} in
    --list )
        shift
        list_supported
    ;;
    --help )
        shift
        show_help
    ;;

    --no-sys )
        INSTALL_SYS_PKGS="0"
        shift
    ;;
    
    --no-sudo )
        INSTALL_SYS_PKGS="0"
        SKIP_ALL_SUDO="1"
        shift
    ;;

    --sys-only )
        INSTALL_BOT_BITS="0"
        shift
    ;;
    
    --service )
        SERVICE_ONLY="1"
        shift
    ;;

    --any-branch )
        EnableUnlistedBranches=1
        shift
    ;;

    --debug )
        DEBUG=1
        shift
        echo "DEBUG MODE IS ENABLED!"
    ;;

    "--dir" )
        InstallDir="$2"
        shift
        shift
        if [ "${InstallDir:0-1}" != "/" ] ; then
            InstallDir="${InstallDir}/"
        fi
        if ! [ -d "$InstallDir" ] ; then
            exit_err "The install directory given does not exist:   '$InstallDir'"
        fi
        VenvDir="${InstallDir}${VenvDir}"
    ;;

    * )
        exit_err "Unknown option $1"
    ;;
  esac
done

if [ "${INSTALL_SYS_PKGS}${INSTALL_BOT_BITS}" == "00" ] ; then
    exit_err "The options --no-sys and --sys-only cannot be used together."
fi

#------------------------------------------------Logic------------------------------------------------#
if [ "$SERVICE_ONLY" = "1" ] ; then
    setup_as_service
    exit 0
fi

# display preamble
cat << EOF
MusicBot Installer

MusicBot and this installer are provided under an MIT license.
This software is provided "as is" and may not be fit for any particular use, stated or otherwise.
Please read the LICENSE file for full details.

This installer attempts to provide automatic install for MusicBot and dependency packages.
It may use methods which are out-of-date on older OS versions, or fail on newer versions.
It is recommended that you personally check the installer script before running it,
and verify the steps for your OS and distro version are correct.

Please consider contributing corrections or new steps if you find issues with this installer.
You may also find installation guides on the wiki or community help on our discord server.
Wiki:
    https://just-some-bots.github.io/MusicBot/
Discord:
    https://discord.gg/bots

For a list of potentially supported OS, run the command:
  $0 --list


EOF

echo "We detected your OS is:  $(distro_supported)"

read -rp "Would you like to continue with the installer? [Y/n]:  " iagree
if [[ "${iagree,,}" != "y" && "${iagree,,}" != "yes" ]] ; then
    exit 2
fi

# check if we are running as root, and if so make a more informed choice.
if [ "$(id -u)" -eq "0" ] && [ "$INSTALL_BOT_BITS" == "1" ] ;  then
    # in theory, we could prompt for a user and do all the setup.
    # better that folks learn to admin their own systems though.
    echo ""
    echo -e "\e[1;37m\e[41m  Warning  \e[0m  You are using root and installing MusicBot."
    echo "        This can break python permissions and will create MusicBot files as root."
    echo "        Meaning, little or no support and you have to fix stuff manually."
    echo "        Running MuiscBot as root is not recommended. You have been warned."
    echo ""
    read -rp "Type 'I understand' (without quotes) to continue installing:" iunderstand
    if [[ "${iunderstand,,}" != "i understand" ]] ; then
        echo ""
        exit_err "Try again with --sys-only or change to a non-root user and use --no-sys and/or --no-sudo"
    fi
fi

# check if we can sudo or not
SUDO_BIN="$(command -v sudo)"
if [ "$SKIP_ALL_SUDO" == "0" ] && [ "$(id -u)" -ne "0" ] ; then
    echo "Checking if user can sudo..."
    if ! sudo -v ; then
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            echo -e "\e[1;31mThe current user cannot run sudo to install system packages.\e[0m"
            echo "If you have already installed system dependencies, try again with:"
            echo "  $0 --no-sys"
            echo ""
            echo "To install system dependencies, switch to root and run:"
            echo "  $0 --sys-only"
            exit 1
        fi
        echo "Will skip all sudo steps."
        SKIP_ALL_SUDO="1"
    fi
fi

# attempt to change the working directory to where this installer is. 
# if nothing is moved this location might be a clone repo...
if [ "$InstallDir" == "" ] ; then
    cd "$(dirname "${BASH_SOURCE[0]}")" || { exit_err "Could not change directory for MusicBot installer."; }
fi

echo ""
if [ "${INSTALL_SYS_PKGS}${INSTALL_BOT_BITS}" == "11" ] ; then
    echo "Attempting to install required system packages & MusicBot software..."
else
    if [ "${INSTALL_SYS_PKGS}${INSTALL_BOT_BITS}" == "10" ] ; then
        echo "Attempting to install only required system packages..."
    else
        echo "Attempting to install only MusicBot and pip libraries..."
    fi
fi
echo ""

case $DISTRO_NAME in
*"Arch Linux"*)  # Tested working 2024.03.01  @  2024/03/31
    if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
        # NOTE: Arch now uses system managed python packages, so venv is required.
        $SUDO_BIN pacman -Syu
        $SUDO_BIN pacman -S curl ffmpeg git jq python python-pip
    fi

    if [ "$INSTALL_BOT_BITS" == "1" ] ; then
        install_as_venv
    fi
    ;;

*"Pop!_OS"* )
    case $DISTRO_NAME in

    # Tested working 22.04  @  2024/03/29
    *"Pop!_OS 22.04"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install build-essential software-properties-common \
                unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
                python3-pip python3-dev jq -y
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    *"Pop!_OS 24.04"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install build-essential software-properties-common \
                unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
                python3-full python3-pip python3-venv python3-dev jq -y
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            install_as_venv
        fi
        ;;

    *)
        echo "Unsupported version of Pop! OS."
        exit 1
        ;;
    esac
    ;;

*"Ubuntu"* )
    # Some cases only use major version number to allow for both .04 and .10 minor versions.
    case $DISTRO_NAME in
    *"Ubuntu 18.04"*)  #  Tested working 18.04 @ 2024/03/29
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            # 18.04 needs to build a newer version from source.
            $SUDO_BIN apt-get install build-essential software-properties-common \
                libopus-dev libffi-dev libsodium-dev libssl-dev \
                zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
                libreadline-dev libsqlite3-dev libbz2-dev \
                unzip curl git jq ffmpeg -y
            
            build_python
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    # Tested working:
    # 20.04  @  2024/03/28
    # 22.04  @  2024/03/30
    *"Ubuntu 20"*|*"Ubuntu 22"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install build-essential software-properties-common \
                unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
                python3-pip python3-dev jq -y
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    # Tested working:
    # 24.04  @  2024/09/04
    *"Ubuntu 24"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install build-essential software-properties-common \
                unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
                python3-full python3-pip python3-venv python3-dev jq -y
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            install_as_venv
        fi
        ;;

    # Ubuntu version 17 and under is not supported.
    *)
        echo "Unsupported version of Ubuntu."
        echo "If your version is newer than Ubuntu 22, please consider contributing install steps."
        exit 1
        ;;
    esac
    ;;

# NOTE: Raspberry Pi OS 11, i386 arch, returns Debian as distro name.
*"Debian"* )
    case $DISTRO_NAME in
    *"Debian GNU/Linux 10"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y

            $SUDO_BIN apt-get install -y build-essential \
                libopus-dev libffi-dev libsodium-dev libssl-dev \
                zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
                libreadline-dev libsqlite3-dev libbz2-dev \
                unzip curl git jq ffmpeg

            build_python
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;
    
    # Tested working:
    # R-Pi OS 11  @  2024/03/29
    # Debian 11.3  @  2024/03/29
    *"Debian GNU/Linux 11"*)
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install -y jq git curl ffmpeg python3 python3-pip
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    # Tested working 12.5  @  2024/03/31
    # Tested working 12.7  @  2024/09/05
    # Tested working trixie  @  2024/09/05
    *"Debian GNU/Linux 12"*|*"Debian GNU/Linux trixie"*|*"Debian GNU/Linux sid"*)
        # Debian 12 uses system controlled python packages.
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            $SUDO_BIN apt-get update -y
            $SUDO_BIN apt-get upgrade -y
            $SUDO_BIN apt-get install -y build-essential libopus-dev libffi-dev libsodium-dev \
                python3-full python3-dev python3-venv python3-pip git ffmpeg curl
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            install_as_venv
        fi
        ;;

    *)
        exit_err "This version of Debian is not currently supported."
        ;;
    esac
    ;;

# Legacy install, needs testing.
# Modern Raspberry Pi OS does not return "Raspbian"
*"Raspbian"*)
    if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
        $SUDO_BIN apt-get update -y
        $SUDO_BIN apt-get upgrade -y

        $SUDO_BIN apt-get install -y build-essential libopus-dev libffi-dev \
            libsodium-dev libssl-dev zlib1g-dev libncurses5-dev \
            libgdbm-dev libnss3-dev libreadline-dev libsqlite3-dev \
            libbz2-dev liblzma-dev lzma-dev uuid-dev \
            unzip curl git ffmpeg

        build_python

        curl -o jq.tar.gz https://github.com/stedolan/jq/releases/download/jq-1.5/jq-1.5.tar.gz
        tar -zxvf jq.tar.gz
        cd jq-1.5 || exit_err "Fatal:  Could not change directory to jq-1.5"
        ./configure && make && $SUDO_BIN make install
        cd .. && rm -rf ./jq-1.5
    fi
    if [ "$INSTALL_BOT_BITS" == "1" ] ; then
        pull_musicbot_git
    fi
    ;;

*"CentOS"* )
    # Get the full release name and version for CentOS
    if [ -f "/etc/redhat-release" ]; then
        DISTRO_NAME=$(cat /etc/redhat-release)
    fi
    # Simplify the distro name for easier checking.
    DISTRO_NAME="${DISTRO_NAME//Linux /}"
    DISTRO_NAME="${DISTRO_NAME//release /}"

    case $DISTRO_NAME in
    # Handle the versions which are EOL.
    *"CentOS "[2-6]* |*"CentOS 8."[0-5]* )
        echo "Unfortunately, this version of CentOS has reached End-of-Life, and will not be supported."
        echo "You should consider upgrading to the latest version to make installing MusicBot easier."
        exit 1
        ;;

    # Supported versions.
    *"CentOS 7"*)  # Tested 7.9 @ 2024/03/28
        # TODO:  CentOS 7 reaches EOL June 2024.
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            # Enable extra repos, as required for ffmpeg
            # We DO NOT use the -y flag here.
            $SUDO_BIN yum install epel-release
            $SUDO_BIN yum localinstall --nogpgcheck https://download1.rpmfusion.org/free/el/rpmfusion-free-release-7.noarch.rpm

            # Install available packages and libraries for building python 3.8+
            $SUDO_BIN yum -y groupinstall "Development Tools"
            $SUDO_BIN yum -y install opus-devel libffi-devel openssl-devel bzip2-devel \
                git curl jq ffmpeg

            # Ask if we should build python
            echo "We need to build python from source for your system. It will be installed using altinstall target."
            read -rp "Would you like to continue ? [N/y]" BuildPython
            if [ "${BuildPython,,}" == "y" ] || [ "${BuildPython,,}" == "yes" ] ; then
                # Build python.
                PyBuildVer="3.10.14"
                PySrcDir="Python-${PyBuildVer}"
                PySrcFile="${PySrcDir}.tgz"

                curl -o "$PySrcFile" "https://www.python.org/ftp/python/${PyBuildVer}/${PySrcFile}"
                tar -xzf "$PySrcFile"
                cd "${PySrcDir}" || exit_err "Fatal:  Could not change to python source directory."

                ./configure --enable-optimizations
                $SUDO_BIN make altinstall

                # Ensure python bin is updated with altinstall name.
                find_python
                RetVal=$?
                if [ "$RetVal" == "0" ] ; then
                    # manually install pip package for the current user.
                    $PyBin <(curl -s https://bootstrap.pypa.io/get-pip.py)
                else
                    echo "Error:  Could not find python on the PATH after installing it."
                    exit 1
                fi
            fi
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    *"CentOS Stream 8"*)  # Tested 2024/03/28
        if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
            # Install extra repos, needed for ffmpeg.
            # Do not use -y flag here.
            $SUDO_BIN dnf install epel-release
            $SUDO_BIN dnf install --nogpgcheck https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-8.noarch.rpm
            $SUDO_BIN dnf config-manager --enable powertools

            # Install available packages.
            $SUDO_BIN yum -y install opus-devel libffi-devel git curl jq ffmpeg python39 python39-devel
        fi

        if [ "$INSTALL_BOT_BITS" == "1" ] ; then
            pull_musicbot_git
        fi
        ;;

    # Currently unsupported.
    *)
        echo "This version of CentOS is not currently supported."
        exit 1
        ;;
    esac
    ;;

# Legacy installer, needs testing.
*"Darwin"*)
    if [ "$INSTALL_SYS_PKGS" == "1" ] ; then
        /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
        brew update
        xcode-select --install
        brew install python
        brew install git
        brew install ffmpeg
        brew install opus
        brew install libffi
        brew install libsodium
        brew install curl
        brew install jq
    fi

    if [ "$INSTALL_BOT_BITS" == "1" ] ; then
        pull_musicbot_git
    fi
    ;;

*)
    echo "Unsupported OS, you will have to install the bot manually."
    exit 1
    ;;
esac

if ! [[ $DISTRO_NAME == *"Darwin"* ]]; then
    if [ "$INSTALL_BOT_BITS" == "1" ] ; then
        configure_bot
        setup_as_service
    fi
else
    echo "The bot has been successfully installed to your user directory"
    echo "You can configure the bot by navigating to the config folder, and modifying the contents of the options.ini and permissions.ini files"
    echo "Once configured, you can start the bot by running the run.sh file"
fi

if [ "$InstalledViaVenv" == "1" ] ; then
    echo ""
    echo "Notice:"
    echo "  This system required MusicBot to be installed inside a Python venv."
    echo "  Shell scripts included with MusicBot should detect and use the venv automatically."
    echo "  If you do not use the included scripts, you must manually activate instead."
    echo "  To manually activate the venv, run the following command: "
    echo "    source ${VenvDir}/bin/activate"
    echo ""
    echo "  The venv module is bundled with python 3.3+, for more info about venv, see here:"
    echo "    https://docs.python.org/3/library/venv.html"
    echo ""
fi
