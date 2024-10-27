#!/bin/bash
#
# MusicBot and this file are provided under an MIT license. 
# Please see the LICENSE file for details.
#
# This file attempts to provide automatic install of MusicBot and dependencies on
# a variety of different Linux distros.
# 

#-----------------------------------------------Configs-----------------------------------------------#
MusicBotGitURL="https://github.com/Just-Some-Bots/MusicBot.git"
CloneDir="MusicBot"
VenvDir="${CloneDir}Venv"

EnableUnlistedBranches=0
DEBUG=0


#----------------------------------------------Constants----------------------------------------------#
DEFAULT_URL_BASE="https://discordapp.com/api"
# Suported versions of python using only major.minor format
PySupported=("3.8" "3.9" "3.10" "3.11" "3.12")
PyBin="python3"
# Path updated by find_python
PyBinPath="$(command -v "$PyBin")"

USER_OBJ_KEYS="id username discriminator verified bot email avatar"

# Status indicator for post-install notice about python venv based install.
InstalledViaVenv=0

declare -A BOT

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
function exit_err() {
    echo "$@"
    exit 1
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
        PY_VER_PATCH=$((PY_VER[2]))
        # echo "run.sh detected $PY_BIN version: $PY_VER_MAJOR.$PY_VER_MINOR.$PY_VER_PATCH"

        # Major version must be 3+
        if [[ $PY_VER_MAJOR -ge 3 ]]; then
            # If 3, minor version minimum is 3.8
            if [[ $PY_VER_MINOR -eq 8 ]]; then
                # if 3.8, patch version minimum is 3.8.7
                if [[ $PY_VER_PATCH -ge 7 ]]; then
                    PyBinPath="$(command -v "$PyBinTest")"
                    PyBin="$PyBinTest"
                    debug "Selected: $PyBinTest  @  $PyBinPath"
                    return 0
                fi
            fi
            # if 3.9+ it should work.
            if [[ $PY_VER_MINOR -ge 9 ]]; then
                PyBinPath="$(command -v "$PyBinTest")"
                PyBin="$PyBinTest"
                debug "Selected: $PyBinTest  @  $PyBinPath"
                return 0
            fi
        fi
    done

    PyBinPath="$(command -v "python3")"
    PyBin="python3"
    debug "Default: python3  @  $PyBinPath"
    return 1
}

function pull_musicbot_git() {
    echo ""
    # Check if we're running inside a previously pulled repo.
    GitDir="${PWD}/.git"
    BotDir="${PWD}/musicbot"
    ReqFile="${PWD}/requirements.txt"
    if [ -d "$GitDir" ] && [ -d "$BotDir" ] && [ -f "$ReqFile" ] ; then
        echo "Existing MusicBot repo detected."
        read -rp "Would you like to install using the current repo? [Y/n]" UsePwd
        if [ "${UsePwd,,}" == "y" ] || [ "${UsePwd,,}" == "yes" ] ; then
            echo ""
            CloneDir="${PWD}"
            VenvDir="${CloneDir}/Venv"

            $PyBin -m pip install --upgrade -r requirements.txt
            echo ""

            cp ./config/example_options.ini ./config/options.ini
            return 0
        fi
        echo "Installer will attempt to create a new directory for MusicBot."
    fi

    cd ~ || exit_err "Fatal:  Could not change to home directory."

    if [ -d "${CloneDir}" ] ; then
        echo "Error: A directory named ${CloneDir} already exists in your home directory."
        exit_err "Delete the ${CloneDir} directory and try again, or complete the install manually."
    fi

    echo ""
    echo "MusicBot currently has three branches available."
    echo "  master - An older MusicBot, for older discord.py. May not work without tweaks!"
    echo "  review - Newer MusicBot, usually stable with less updates than the dev branch."
    echo "  dev    - The newest MusicBot, latest features and changes which may need testing."
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

    $PyBin -m pip install --upgrade -r requirements.txt
    echo ""

    cp ./config/example_options.ini ./config/options.ini
}

function setup_as_service() {
    echo ""
    echo "The installer can also install MusicBot as a system service file."
    echo "This starts the MusicBot at boot and after failures."
    echo "You must specify a User and Group which the service will run as."
    read -rp "Install the musicbot system service? [N/y] " SERVICE
    case $SERVICE in
    [Yy]*)
        # Because running this service as root is really not a good idea,
        # a user and group is required here.
        echo "Please provide an existing User name and Group name for the service to use."
        read -rp "Enter an existing User name: " BotSysUserName
        echo ""
        read -rp "Enter an existing Group name: " BotSysGroupName
        echo ""
        # TODO: maybe check if the given values are valid, or create the user/group...

        if [ "$BotSysUserName" == "" ] ; then
            echo "Cannot set up the service with a blank User name."
            return
        fi
        if [ "$BotSysGroupName" == "" ] ; then
            echo "Cannot set up the service with a blank Group name."
            return
        fi

        echo "Setting up the bot as a service"
        # Replace parts of musicbot.service with proper values.
        sed -i "s,#User=mbuser,User=${BotSysUserName},g" ./musicbot.service
        sed -i "s,#Group=mbusergroup,Group=${BotSysGroupName},g" ./musicbot.service
        sed -i "s,/usr/bin/pythonversionnum,${PyBinPath},g" ./musicbot.service
        sed -i "s,mbdirectory,${PWD},g" ./musicbot.service

        # Copy the service file into place and enable it.
        sudo cp ~/${CloneDir}/musicbot.service /etc/systemd/system/
        sudo chown root:root /etc/systemd/system/musicbot.service
        sudo chmod 644 /etc/systemd/system/musicbot.service
        sudo systemctl enable musicbot
        sudo systemctl start musicbot

        echo "Bot setup as a service and started"
        ask_setup_aliases
        ;;
    esac

}

function ask_setup_aliases() {
    echo " "
    # TODO: ADD LINK TO WIKI
    read -rp "Would you like to set up a command to manage the service? [N/y] " SERVICE
    case $SERVICE in
    [Yy]*)
        echo "Setting up command..."
        sudo cp ~/${CloneDir}/musicbotcmd /usr/bin/musicbot
        sudo chown root:root /usr/bin/musicbot
        sudo chmod 644 /usr/bin/musicbot
        sudo chmod +x /usr/bin/musicbot
        echo ""
        echo "Command created!"
        echo "Information regarding how the bot can now be managed found by running:"
        echo "musicbot --help"
        ;;
    esac
}

function debug() {
    local msg=$1
    if [[ $DEBUG == '1' ]]; then
        echo "[DEBUG] $msg" 1>&2
    fi
}

function strip_dquote() {
    result="${1%\"}"
    result="${result#\"}"
    echo "$result"
}

function r_data() {
    local data=$1
    echo "$data" | sed -rn 's/(\{.+)\} ([0-9]+)$/\1}/p'
}

function r_code() {
    local data=$1
    echo "$data" | sed -rn 's/(\{.+)\} ([0-9]+)$/\2/p'
}

function key() {
    local data=$1
    local key=$2
    echo "$data" | jq ".$key"
}

function r() {
    local token=$1
    local method=$2
    local route=$3

    local url="$DEFAULT_URL_BASE/$route"
    debug "Attempting to load url $url with token $token"

    res=$(curl -k -s \
        -w " %{http_code}" \
        -H "Authorization: Bot $token" \
        -H "Content-Type: application/json" \
        -X "$method" \
        "$url" | tr -d '\n')
    echo "$res"
}

function get_token_and_create_bot() {
    # Set bot token
    echo ""
    echo "Please enter your bot token. This can be found in your discordapp developer page."
    read -rp "Enter Token:" -s token
    create_bot "$token"
}

function create_bot() {
    local bot_token=$1

    local me
    local me_code
    local me_data
    me=$(r "$bot_token" "GET" "users/@me")
    me_code=$(r_code "$me")
    me_data=$(r_data "$me")

    if ! [[ $me_code == "200" ]]; then
        echo ""
        echo "Error getting user profile, is the token correct? ($me_code $me_data)"
        exit 1
    else
        debug "Got user profile: $me_data"
    fi

    for k in $USER_OBJ_KEYS; do
        BOT[$k]=strip_dquote "$(key "$me_data" "$k")"
    done
    BOT["token"]=$bot_token

    # We're logged on!
    echo "Logged on with ${BOT["username"]}#${BOT["discriminator"]}"
    sed -i "s/bot_token/$bot_token/g" ./config/options.ini
}

function configure_bot() {
    read -rp "Would like to configure the bot for basic use? [N/y]" YesConfig
    if [ "${YesConfig,,}" != "y" ] && [ "${YesConfig,,}" != "yes" ] ; then
        return
    fi

    get_token_and_create_bot

    # Set prefix, if user wants
    read -rp "Would you like to change the command prefix? [N/y] " chngprefix
    case $chngprefix in
    [Yy]*)
        echo "Please enter the prefix you'd like for your bot."
        read -rp "This is what comes before all commands. The default is [!] " prefix
        sed -i "s/CommandPrefix = !/CommandPrefix = $prefix/g" ./config/options.ini
        ;;
    [Nn]*) echo "Using default prefix [!]" ;;
    *) echo "Using default prefix [!]" ;;
    esac

    # Set owner ID, if user wants
    read -rp "Would you like to automatically get the owner ID from the OAuth application? [Y/n] " accountcheck
    case $accountcheck in
    [Yy]*) echo "Getting owner ID from OAuth application..." ;;
    [Nn]*)
        read -rp "Please enter the owner ID. " ownerid
        sed -i "s/OwnerID = auto/OwnerID = $ownerid/g" ./config/options.ini
        ;;
    *) echo "Getting owner ID from OAuth application..." ;;
    esac
    # Enable/Disable AutoPlaylist
    read -rp "Would you like to enable the autoplaylist? [Y/n] " autoplaylist
    case $autoplaylist in
    [Yy]*) echo "Autoplaylist enabled." ;;
    [Nn]*)
        echo "Autoplaylist disabled"
        sed -i "s/UseAutoPlaylist = yes/UseAutoPlaylist = no/g" ./config/options.ini
        ;;
    *) echo "Autoplaylist enabled." ;;
    esac
}

#------------------------------------------------Logic------------------------------------------------#
# list off "supported" linux distro/versions if asked to and exit.
if [[ "${1,,}" == "--list" ]] ; then
    # We search this file and extract names from the supported cases below.
    # We control which cases we grab based on the space at the end of each 
    # case pattern, before ) or | characters.
    # This allows adding complex cases which will be excluded from the list.
    Avail=$(grep -oh '\*"[[:alnum:] _!\.]*"\*[|)]' "$0" )
    Avail="${Avail//\*\"/}"
    Avail="${Avail//\"\*/}"
    Avail="${Avail//[|)]/}"

    echo "The MusicBot installer might have support for these flavors of Linux:"
    echo "$Avail"
    echo ""
    exit 0
fi

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

echo "We detected your OS is:  ${DISTRO_NAME}"

read -rp "Would you like to continue with the installer? [Y/n]:  " iagree
if [[ "${iagree,,}" != "y" && "${iagree,,}" != "yes" ]] ; then
    exit 2
fi

echo ""
echo "Attempting to install required system packages..."
echo ""

case $DISTRO_NAME in
*"Arch Linux"*)  # Tested working 2024.03.01  @  2024/03/31
    # NOTE: Arch now uses system managed python packages, so venv is required.
    sudo pacman -Syu
    sudo pacman -S curl ffmpeg git jq python python-pip

    # Make sure newly install python is used.
    find_python

    # create a venv to install MusicBot into and activate it.
    $PyBin -m venv "${VenvDir}"
    InstalledViaVenv=1
    CloneDir="${VenvDir}/${CloneDir}"
    # shellcheck disable=SC1091
    source "${VenvDir}/bin/activate"

    # Update python to use venv path.
    find_python

    pull_musicbot_git

    deactivate
    ;;

*"Pop!_OS"*)  # Tested working 22.04  @  2024/03/29
    sudo apt-get update -y
    sudo apt-get upgrade -y
    sudo apt-get install build-essential software-properties-common \
        unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
        python3-pip python3-dev jq -y

    pull_musicbot_git
    ;;

*"Ubuntu"* )
    # Some cases only use major version number to allow for both .04 and .10 minor versions.
    case $DISTRO_NAME in
    *"Ubuntu 18.04"*)  #  Tested working 18.04 @ 2024/03/29
        sudo apt-get update -y
        sudo apt-get upgrade -y
        # 18.04 needs to build a newer version from source.
        sudo apt-get install build-essential software-properties-common \
            libopus-dev libffi-dev libsodium-dev libssl-dev \
            zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
            libreadline-dev libsqlite3-dev libbz2-dev \
            unzip curl git jq ffmpeg -y

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
            sudo make altinstall

            # Ensure python bin is updated with altinstall name.
            find_python
            RetVal=$?
            if [ "$RetVal" == "0" ] ; then
                # manually install pip package for current user.
                $PyBin <(curl -s https://bootstrap.pypa.io/get-pip.py)
            else
                echo "Error:  Could not find python on the PATH after installing it."
                exit 1
            fi
        fi

        pull_musicbot_git
        ;;

    # Tested working:
    # 20.04  @  2024/03/28
    # 22.04  @  2024/03/30
    *"Ubuntu 20"*|*"Ubuntu 22"*)
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt-get install build-essential software-properties-common \
            unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
            python3-pip python3-dev jq -y

        pull_musicbot_git
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
*"Debian"*)
    case $DISTRO_NAME in
    # Tested working:
    # R-Pi OS 11  @  2024/03/29
    # Debian 11.3  @  2024/03/29
    *"Debian GNU/Linux 11"*)
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt-get install git libopus-dev libffi-dev libsodium-dev ffmpeg \
            build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev \
            libsqlite3-dev tk-dev libssl-dev openssl python3 python3-pip curl jq -y

        pull_musicbot_git
        ;;

    *"Debian GNU/Linux 12"*)  # Tested working 12.5  @  2024/03/31
        # Debian 12 uses system controlled python packages.
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt-get install build-essential libopus-dev libffi-dev libsodium-dev \
            python3-full python3-dev python3-pip git ffmpeg curl

        # Create and activate a venv using python that was just installed.
        find_python
        $PyBin -m venv "${VenvDir}"
        InstalledViaVenv=1
        CloneDir="${VenvDir}/${CloneDir}"
        # shellcheck disable=SC1091
        source "${VenvDir}/bin/activate"
        find_python

        pull_musicbot_git
        
        # exit venv
        deactiveate
        ;;

    *)
        exit_err "This version of Debian is not currently supported."
        ;;
    esac
    ;;

# Legacy install, needs testing.
# Modern Raspberry Pi OS does not return "Raspbian"
*"Raspbian"*)
    sudo apt-get update -y
    sudo apt-get upgrade -y
    sudo apt install python3-pip git libopus-dev ffmpeg curl
    curl -o jq.tar.gz https://github.com/stedolan/jq/releases/download/jq-1.5/jq-1.5.tar.gz
    tar -zxvf jq.tar.gz
    cd jq-1.5 || exit_err "Fatal:  Could not change directory to jq-1.5"
    ./configure && make && sudo make install
    cd .. && rm -rf ./jq-1.5
    pull_musicbot_git
    ;;

*"CentOS"* )
    # Get the full release name and version
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

        # Enable extra repos, as required for ffmpeg
        # We DO NOT use the -y flag here.
        sudo yum install epel-release
        sudo yum localinstall --nogpgcheck https://download1.rpmfusion.org/free/el/rpmfusion-free-release-7.noarch.rpm

        # Install available packages and libraries for building python 3.8+
        sudo yum -y groupinstall "Development Tools"
        sudo yum -y install opus-devel libffi-devel openssl-devel bzip2-devel \
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
            sudo make altinstall

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

        pull_musicbot_git
        ;;

    *"CentOS Stream 8"*)  # Tested 2024/03/28
        # Install extra repos, needed for ffmpeg.
        # Do not use -y flag here.
        sudo dnf install epel-release
        sudo dnf install --nogpgcheck https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-8.noarch.rpm
        sudo dnf config-manager --enable powertools

        # Install available packages.
        sudo yum -y install opus-devel libffi-devel git curl jq ffmpeg python39 python39-devel

        pull_musicbot_git
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
    pull_musicbot_git
    ;;

*)
    echo "Unsupported OS, you will have to install the bot manually."
    exit 1
    ;;
esac

if ! [[ $DISTRO_NAME == *"Darwin"* ]]; then
    configure_bot
    setup_as_service
else
    echo "The bot has been successfully installed to your user directory"
    echo "You can configure the bot by navigating to the config folder, and modifying the contents of the options.ini and permissions.ini files"
    echo "Once configured, you can start the bot by running the run.sh file"
fi

if [ "$InstalledViaVenv" == "1" ] ; then
    echo ""
    echo "Notice:"
    echo "This system required MusicBot to be installed inside a Python venv."
    echo "In order to run or update MusicBot, you must use the venv or binaries stored within it."
    echo "To activate the venv, run the following command: "
    echo "  source ${VenvDir}/bin/activate"
    echo ""
    echo "The venv module is bundled with python 3.3+, for more info about venv, see here:"
    echo "  https://docs.python.org/3/library/venv.html"
    echo ""
fi
