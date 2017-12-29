#!/bin/bash
sudo yum install -y https://centos7.iuscommunity.org/ius-release.rpm
sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el7/x86_64/nux-dextop-release-0-5.el7.nux.noarch.rpm
sudo yum -y update
sudo yum -y install libffi.x86_64 libffi-devel.x86_64
sudo yum -y install opus-devel.x86_64 opus-tools.x86_64 opus.x86_64 
sudo yum -y install ffmpeg ffmpeg-devel
python3.5 -V > /dev/null 2>&1 || sudo yum install -y python35u python35u-libs python35u-devel python35u-pip
sudo /usr/bin/python3.5 run.py
