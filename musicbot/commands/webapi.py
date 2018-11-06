# This cogs will implement webserver that can respond to bot query, maybe useful for interfacing with external application
import socket
import sys
import logging
import asyncio
import select

log = logging.getLogger(__name__)

cog_name = 'webapi'
 
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = ''

status = 'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n'

async def init_webapi(bot):
    log.debug('binding to port {0}'.format(bot.config.webapi_port))
    server_socket.bind((host, bot.config.webapi_port))
    server_socket.listen()

# @TheerapakG: TODO: Change the code from this shitty connection handling to actual code.
#                    Wait... it isn't handling anything either!
async def asyncloop_connect(bot):
    loop = asyncio.get_event_loop()
    client_socket, address = await loop.sock_accept(server_socket)
    log.debug("Connection from {0}".format(address))
    await loop.sock_sendall(client_socket, (status+str(client_socket.getpeername())).encode('utf-8'))
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()