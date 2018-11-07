# This cogs will implement webserver that can respond to bot query, maybe useful for interfacing with external application
# If you don't need querying via webserver, you shouldn't load this cog

# This cog requires Python 3.7

import socket
import sys
import logging
import asyncio
import select
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

log = logging.getLogger(__name__)

cog_name = 'webapi'
 
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = ''
botinst = None

class RequestHdlr(BaseHTTPRequestHandler):
    def gen_content(self):
        return '{}'

    def do_GET(self):
        if self.path.startswith('/api'):
            self.send_response(200)
            self.send_header("Connection", "close")
            f = self.gen_content().encode('UTF-8', 'replace')
            self.send_header("Content-Type", "application/json;charset=utf-8")
            log.debug('sending {} bytes'.format(len(f)))
            self.send_header("Content-Length", str(len(f)))
            self.end_headers()
            self.wfile.write(f)
        else:
            self.send_error(404)
            self.end_headers()

    def log_message(self, format, *args):
        log.debug("{addr} - - [{dt}] {args}\n".format(addr = self.address_string(), dt = self.log_date_time_string(), args = format%args))

async def init_webapi(bot):
    botinst = bot
    log.debug('binding to port {0}'.format(bot.config.webapi_port))
    serv = ThreadingHTTPServer((host, bot.config.webapi_port), RequestHdlr)
    server_thread = threading.Thread(target=serv.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()
