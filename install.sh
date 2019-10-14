#!/bin/bash
#----------------------------------------------Constants----------------------------------------------#
DEFAULT_URL_BASE="https://discordapp.com/api"
PYEXEC=3
DEBUG=0

USER_OBJ_KEYS="id username discriminator verified bot email avatar"

declare -A BOT

if [ -n "$(command -v lsb_release)" ]; then
    DISTRO_NAME=$(lsb_release -s -d)
elif [ -f "/etc/os-release" ]; then
    DISTRO_NAME=$(grep PRETTY_NAME /etc/os-release | sed 's/PRETTY_NAME=//g' | tr -d '="')
elif [ -f "/etc/debian_version" ]; then
    DISTRO_NAME="Debian $(cat /etc/debian_version)"
elif [ -f "/etc/redhat-release" ]; then
    DISTRO_NAME=$(cat /etc/redhat-release)
else
    DISTRO_NAME="$(uname -s) $(uname -r)"
fi

#----------------------------------------------Functions----------------------------------------------#
function pull_musicbot_git() {
    cd ~
    echo " "
    echo "Do you want to install the review branch?"
    read -p "Installing the review branch means limited support, but newer fixes and features. [N/y] " BRANCH
    case $BRANCH in
        [Yy]*)  echo "Installing branch Review"; git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b review;;
        [Nn]*) echo "Installing branch Master"; git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master;;
        *)  echo "Installing branch Master"; git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master;;
    esac
    cd MusicBot

    python${PYEXEC} -m pip install --upgrade -r requirements.txt

    cp ./config/example_options.ini ./config/options.ini
}

function setup_as_service() {
    local DIR="$( pwd )"
    echo ""
    echo "Do you want to set up the bot as a service?"
    read -p "This would mean the bot is automatically started and kept up by the system to ensure its online as much as possible [N/y] " SERVICE
    case $SERVICE in
        [Yy]*)  echo "Setting up the bot as a service"
                sed -i "s/versionnum/$PYEXEC/g" ./musicbot.service
                sed -i "s,mbdirectory,$DIR,g" ./musicbot.service
                sudo mv ~/MusicBot/musicbot.service /etc/systemd/system/
                sudo chown root:root /etc/systemd/system/musicbot.service
                sudo chmod 644 /etc/systemd/system/musicbot.service
                sudo systemctl enable musicbot
                sudo systemctl start musicbot
                echo "Bot setup as a service and started"
                ask_setup_aliases;;
    esac

}

function ask_setup_aliases() {
    echo " "
    # TODO: ADD LINK TO WIKI
    read -p "Would you like to set up a command to manage the service? [N/y] " SERVICE
    case $SERVICE in
        [Yy]*)  echo "Setting up command..."
                sudo mv ~/MusicBot/musicbotcmd /usr/bin/musicbot
                sudo chown root:root /usr/bin/musicbot
                sudo chmod 644 /usr/bin/musicbot
                sudo chmod +x /usr/bin/musicbot
                echo ""
                echo "Command created!"
                echo "The bot can now be managed with the following:"
                echo "musicbot stop"
                echo "musicbot restart"
                echo "musicbot start"
                echo "musicbot logs"
                ;;
    esac
}

function debug() {
    local msg=$1
    if [[ $DEBUG == '1' ]]; then
        echo "[DEBUG] $msg" 1>&2
    fi
}

function strip() {
    local char=$1
    result="${2%\"}"
    result="${result#\"}"
    echo $result
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
        -X $method \
        $DEFAULT_URL_BASE/$route | tr -d '\n')
    echo $res
}

function get_token_and_create_bot() {
    # Set bot token
    echo ""
    echo "Please enter your bot token. This can be found in your discordapp developer page." 
    read -p "Enter Token:" -s token
    create_bot $token
}

function create_bot() {
    local bot_token=$1

    local me="$(r $bot_token "GET" "users/@me")"
    local me_code=$(r_code "$me")
    local me_data=$(r_data "$me")

    if ! [[ $me_code == "200" ]]; then
        echo ""
        echo "Error getting user profile, is the token correct? ($me_code $me_data)"
        exit 1
    else
        debug "Got user profile: $me_data"
    fi

    for k in $USER_OBJ_KEYS; do
        BOT[$k]=`strip '"' $(key "$me_data" "$k")`
    done
    BOT["token"]=$bot_token

    # We're logged on!
    echo "Logged on with ${BOT["username"]}#${BOT["discriminator"]}"
    sed -i "s/bot_token/$bot_token/g" ./config/options.ini
}

function get_and_verify_owner() {
    if [ -z ${BOT+x} ]; then
        debug "BOT is unset"
        exit 1
    fi

    local app_info="$(r ${BOT["token"]} "GET" "users/@me")"
    local app_info_code=$(r_code "$me")
    local app_info_data=$(r_data "$me")

    if ! [[ $app_info_code == "200" ]]; then
        debug "Error getting app info, is the token correct? ($app_info_code $app_info_data)"
        exit 1
    else
        debug "Got app info: $app_info_data"
    fi

    bot_owner_obj = `strip '"' $(key "$app_info_data" "owner")`
    OWNER_ID = key "$bot_owner_obj" "id"
    echo "$(key "$bot_owner_obj" "name")#$(key "$bot_owner_obj" "discriminator") ($OWNER_ID)"
}

function configure_bot() {
    get_token_and_create_bot

    # Set prefix, if user wants
    read -p "Would you like to change the command prefix? [N/y] " chngprefix
    case $chngprefix in
        [Yy]*) echo "Please enter the prefix you'd like for your bot.";
            read -p "This is what comes before all commands. The default is [!] " prefix;
            sed -i "s/CommandPrefix = !/CommandPrefix = $prefix/g" ./config/options.ini;;
        [Nn]*) echo "Using default prefix [!]";;
        * )  echo "Using default prefix [!]";;
    esac

    # Set owner ID, if user wants
    read -p "Would you like to automatically get the owner ID from the OAuth application? [Y/n] " accountcheck
    case $accountcheck in
        [Yy]*) echo "Getting owner ID from OAuth application...";;
        [Nn]*) read -p "Please enter the owner ID. " ownerid;
            sed -i "s/OwnerID = auto/OwnerID = $ownerid/g" ./config/options.ini;;
        *)  echo "Getting owner ID from OAuth application...";;
    esac
    # Enable/Disable AutoPlaylist
    read -p "Would you like to enable the autoplaylist? [Y/n] " autoplaylist
    case $autoplaylist in
        [Yy]*) echo "Autoplaylist enabled.";;
        [Nn]*) echo "Autoplaylist disabled";
            sed -i "s/UseAutoPlaylist = yes/UseAutoPlaylist = no/g" ./config/options.ini;;
        *)  echo "Autoplaylist enabled.";;
    esac
}

#------------------------------------------------Logic------------------------------------------------#
echo "You are running: ${DISTRO_NAME}"

case $DISTRO_NAME in
    *"Arch Linux"*)
        sudo pacman -Syu
        sudo pacman -S git python python-pip opus libffi libsodium ncurses gdbm glibc zlib sqlite tk openssl ffmpeg curl jq
        pull_musicbot_git;;
    *"Ubuntu"*)
        sudo apt-get install build-essential unzip curl -y
        sudo apt-get install software-properties-common -y
        sudo add-apt-repository ppa:mc3man/xerus-media -y
        case $DISTRO_NAME in
            *"Ubuntu 16.04"*)
                sudo add-apt-repository ppa:deadsnakes/ppa -y
                sudo apt-get update -y
                sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3.6 jq -y
                sudo apt-get upgrade -y
                python3.6 <(curl -s https://bootstrap.pypa.io/get-pip.py)
                PYEXEC="3.6"
                pull_musicbot_git;;
            *"Ubuntu 18.04"*)
                sudo apt-get update -y
                sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip python3-dev jq -y
                sudo apt-get upgrade -y
                pull_musicbot_git;;
            *)
                echo Unsupported version of Ubuntu, please upgrade to a newer version,
                echo or use a different distribution of linux.
                exit 1;;
            esac;;
    *"Debian"*)
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt-get install git libopus-dev libffi-dev libsodium-dev ffmpeg build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl python3 python3-pip curl jq -y
        pull_musicbot_git;;
    *"Raspbian"*)
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt install python3-pip git libopus-dev ffmpeg curl
        cd /tmp
        curl -o jq.tar.gz https://github.com/stedolan/jq/releases/download/jq-1.5/jq-1.5.tar.gz
        tar -zxvf jq.tar.gz && cd jq-1.5
        ./configure && make && sudo make install
        pull_musicbot_git;;
    *"CentOS"*)
        sudo yum -y update
        sudo yum -y groupinstall "Development Tools"
        case $DISTRO_NAME in
            *"CentOS Linux 6"*)
                sudo yum -y install https://centos6.iuscommunity.org/ius-release.rpm
                sudo yum -y install yum-utils opus-devel libffi-devel libsodium-devel python35u python35u-devel python35u-pip curl jq
                sudo rpm --import http://li.nux.ro/download/nux/RPM-GPG-KEY-nux.ro
                sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el6/x86_64/nux-dextop-release-0-2.el6.nux.noarch.rpm
                sudo yum -y install ffmpeg ffmpeg-devel -y
                mkdir libsodium && cd libsodium
                curl -o libsodium.tar.gz https://download.libsodium.org/libsodium/releases/LATEST.tar.gz
                tar -zxvf libsodium.tar.gz && cd libsodium-stable
                ./configure
                make && make check
                sudo make install
                cd ../.. && rm -rf libsodium
                pull_musicbot_git;;
            *"CentOS Linux 7"*)
                sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
                sudo yum -y install curl opus-devel libffi-devel libsodium-devel python35u python35u-devel jq
                sudo rpm --import http://li.nux.ro/download/nux/RPM-GPG-KEY-nux.ro
                sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el7/x86_64/nux-dextop-release-0-5.el7.nux.noarch.rpm
                sudo yum -y install ffmpeg ffmpeg-devel -y
                pull_musicbot_git;;
            *"CentOS Linux 8"*)
                echo "CentOS 8 is currently unsupported, we suggest you downgrade to CentOS 7 or swap to a different OS"
                exit 1;;
            esac;;
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
        pull_musicbot_git;;
    *)
        echo "Unsupported OS, you will have to install the bot manually."
        exit 1;;
esac
if ! [[ $DISTRO_NAME == *"Darwin"* ]]; then
    configure_bot
    setup_as_service
else
    echo "The bot has been successfully installed to your user directory"
    echo "You can configure the bot by navigating to the config folder, and modifying the contents of the options.ini and permissions.ini files"
    echo "Once configured, you can start the bot by running the run.sh file"
fi
