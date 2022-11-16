#!/usr/local/bin/python3
# module sys

import subprocess


# png 转 gif
def img_trans_gif(png_list, out_file):
    try:
        cmd = "ffmpeg -f image2 -i %s -y %s" % (png_list, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False


# png 转 视频
def img_trans_video(png_list, duration, out_file):
    try:
        cmd = "ffmpeg -loop 1 -f image2 -i %s -t %s -vcodec libx264 -y %s" % (png_list, duration, out_file)
        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False


# gif 转 图片
def gif_trans_img(input_file, out_path, img_prefix, category="png"):
    try:
        if out_path == "":
            return False
        out_path = out_path.rstrip("/")
        img = img_prefix + "_%d"

        out_img = "%s/%s.%s" % (out_path, img, category)
        cmd = "ffmpeg -y -i %s %s" % (input_file, out_img)

        res = subprocess.call(cmd, shell=True)

        if res != 0:
            return False
        return True
    except Exception:
        return False
