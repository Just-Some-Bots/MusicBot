#!/usr/local/bin/python3

import subprocess


# 调整音频播放速率
def a_speed(input_file, speed, out_file):
    try:
        cmd = "ffmpeg -y -i %s -filter_complex \"atempo=tempo=%s\" %s" % (input_file, speed, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False


# 音频截取 str_second 开始时间秒数   intercept 截取长度秒。从开始时间截取多少秒的音频
def a_intercept(input_file, str_second, duration, out_file):
    try:
        cmd = "ffmpeg -y -i %s -ss %s -t %s %s" % (input_file, str_second, duration, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False


# 音频拼接 input_file_list = ["1.mp3", "2.mp3"]
def a_split(input_file_list, out_file):
    try:
        if len(input_file_list) < 2:
            return False
        split_str = "|"
        a_list = split_str.join(input_file_list)

        cmd= "ffmpeg -y -i \"concot:%s\" %s" % (a_list, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False


# 调整音量大小
def a_volume(input_file, volume, out_file):
    try:
        cmd = "ffmpeg -y -i %s -af volume=%s %s" % (input_file, volume, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False
