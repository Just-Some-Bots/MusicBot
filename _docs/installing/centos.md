---
title: CentOS
category: Installing the bot
order: 6
---

<img class="doc-img" src="{{ site.baseurl }}/images/centos.png" alt="centos" style="width: 75px; float: right;"/>
Installation on CentOS is **majorly untested and is not officially supported** due to issues. Please keep this in mind when seeking support.

The installation steps for CentOS vary depending on your version of the OS.

## CentOS 6.9

~~~sh
# Install dependencies
sudo yum -y update
sudo yum -y groupinstall "Development Tools"
sudo yum -y install https://centos6.iuscommunity.org/ius-release.rpm
sudo yum -y install yum-utils opus-devel libffi-devel libsodium-devel python35u python35u-devel python35u-pip

# Install FFmpeg
sudo rpm --import http://li.nux.ro/download/nux/RPM-GPG-KEY-nux.ro
sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el6/x86_64/nux-dextop-release-0-2.el6.nux.noarch.rpm
sudo yum -y install ffmpeg ffmpeg-devel -y

# Install libsodium from source
mkdir libsodium && cd libsodium
curl -o libsodium.tar.gz https://download.libsodium.org/libsodium/releases/LATEST.tar.gz
tar -zxvf libsodium.tar.gz && cd libsodium-stable
./configure
make && make check
sudo make install
cd ../.. && rm -rf libsodium

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install bot requirements
sudo pip3.5 install -U -r requirements.txt
sudo pip3.5 install -U pynacl
~~~

## CentOS 7.4

~~~sh
# Install dependencies
sudo yum -y update
sudo yum -y groupinstall "Development Tools"
sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
sudo yum -y install curl opus-devel libffi-devel libsodium-devel python35u python35u-devel python35u-pip

# Install FFmpeg
sudo rpm --import http://li.nux.ro/download/nux/RPM-GPG-KEY-nux.ro
sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el7/x86_64/nux-dextop-release-0-5.el7.nux.noarch.rpm
sudo yum -y install ffmpeg ffmpeg-devel -y

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install bot requirements
sudo python3.5 -m pip install -U -r requirements.txt
~~~
{: title="CentOS 7.4" }

Once everything has been completed, you can go ahead and [configure]({{ site.baseurl }}/using/configuration) the bot and then run with `sudo ./run.sh`.