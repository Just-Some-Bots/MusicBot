#!/bin/bash

# might need to change this script to another location on the site

version=3.8.7

echo "Installing deps."

sudo apt-get install -y build-essential tk-dev libncurses5-dev \
libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev \
libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev git

sudo wget https://www.python.org/ftp/python/$version/Python-$version.tgz

sudo tar zxf Python-$version.tgz
cd Python-$version
sudo ./configure --enable-optimizations
sudo make -j4
sudo make altinstall

sudo cd ..
sudo rm -f -r Python-$version
sudo rm Python-$version.tgz






# not yet working
