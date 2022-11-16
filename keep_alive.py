from flask import Flask
import threading
import ffmpeg

app = Flask(__name__)

app_lock = threading.Lock()


def download():
    with open('listen.txt', 'r+') as f:
        if f.readline() == 'listening':
            f.seek(0)
            f.write('not-listening')
            f.truncate()
            f.seek(0)
            while f.readline() == 'not-listening':
                (ffmpeg.input('https://kxlu.streamguys1.com/kxlu-hi',
                              t=4000).output('kxlu.mp3').run())
                break


@app.route('/')
def index():
    download()
    return 'Hello from Flask!'


def run():
    while True:
        app_lock.acquire()
        app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = threading.Thread(target=run)
    t.start()
    t.join()


keep_alive()
