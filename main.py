import os
import threading

system_lock = threading.Lock()


def run():
    os.system('nohup python keep_alive.py > /dev/null 2>&1 &')


run()
os.system('bash ./run.sh')