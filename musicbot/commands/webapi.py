# This cogs will implement webserver that can respond to bot query, maybe useful for interfacing with external application
# If you don't need querying via webserver, you shouldn't load this cog

# If the API will be exposed to the internet, consider specifying certificate for security

# This cog requires Python 3.7

import socket
import sys
import logging
import asyncio
import threading
import json
import uuid
import traceback
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import discord

from ssl import SSLContext, SSLError

from ..constructs import Response
from ..cogsmanager import gen_cog_list, gen_cmd_list_from_cog
from ..wrappers import dev_only

log = logging.getLogger(__name__)

cog_name = 'webapi'
 
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = ''
botinst = None
authtoken = set()

class RequestHdlr(BaseHTTPRequestHandler):
    def gen_content_POST(self):
        path = self.path[4:]
        param = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if path == '/exec':
            if 'token' in param and param['token'] in authtoken:
                if 'code' in param:
                    try:
                        threadsafe_exec_bot(param['code'])
                        return {'action':True, 'error':False, 'result':''}
                    except:
                        return {'action':True, 'error':True, 'result':traceback.format_exc()}
            return {'action':False}
        if path == '/eval':
            if 'token' in param and param['token'] in authtoken:
                if 'code' in param:
                    try:
                        ret = threadsafe_eval_bot(param['code'])
                        return {'action':True, 'error':False, 'result':str(ret)}
                    except:
                        return {'action':True, 'error':True, 'result':traceback.format_exc()}
            return {'action':False}
        return None

    def gen_content_GET(self):
        path = self.path[4:]
        parse = urlparse(path)
        return str(parse)

    def do_POST(self):
        if self.path.startswith('/api'):
            f = self.gen_content_POST()
            if f:
                self.send_response(200)
                self.send_header("Connection", "close")
                f = json.dumps(f)
                f = f.encode('UTF-8', 'replace')
                self.send_header("Content-Type", "application/json;charset=utf-8")
                log.debug('sending {} bytes'.format(len(f)))
                self.send_header("Content-Length", str(len(f)))
                self.end_headers()
                self.wfile.write(f)
                return
        self.send_error(404)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api'):
            self.send_response(200)
            self.send_header("Connection", "close")
            f = self.gen_content_GET()
            f = f.encode('UTF-8', 'replace')
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
    log.debug('binding to port {0}'.format(bot.config.webapi_port))
    global botinst
    botinst = bot
    serv = ThreadingHTTPServer((host, bot.config.webapi_port), RequestHdlr)
    if bot.config.ssl_certfile and bot.config.ssl_keyfile:
        try:
            cont = SSLContext()
            cont.load_cert_chain(bot.config.ssl_certfile, keyfile = bot.config.ssl_keyfile)
        except SSLError:
            log.error('Error loading certificate, falling back to http. Traceback below.')
            log.error(traceback.format_exc())
            log.info('using http for webapi')
        else:
            serv.socket = cont.wrap_socket(sock = serv.socket, server_side = True)
            log.info('using https for webapi')
    else:
        log.info('using http for webapi')
    server_thread = threading.Thread(target=serv.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()

# @TheerapakG: TODO: dm this
@dev_only
async def cmd_gentoken(bot):
    token = str(uuid.uuid4())
    authtoken.add(token)
    return Response("Generated token `{0}`".format(token))

# @TheerapakG: TODO: dm this
@dev_only
async def cmd_revoketoken(bot, token):
    try:
        authtoken.remove(token)
        return Response("Successfully revoked token `{0}`".format(token))
    except KeyError:
        return Response("Token `{0}` not found".format(token))

def threadsafe_exec_bot(code):
    fut = asyncio.run_coroutine_threadsafe(botinst.exec_bot(code), botinst.loop)
    fut.result() # wait for exec to finish
    return

def threadsafe_eval_bot(code):
    fut = asyncio.run_coroutine_threadsafe(botinst.eval_bot(code), botinst.loop)
    result = fut.result()
    if asyncio.iscoroutine(result):
        resultfut = asyncio.run_coroutine_threadsafe(result, botinst.loop)
        result = resultfut.result()
    return result

def get_cog_list():
    # structure:
    # return = list(coginfo)
    # commandinfo = tuple(cogname, cogloaded)
    fut = asyncio.run_coroutine_threadsafe(gen_cog_list(), botinst.loop)
    result = fut.result()
    coglist = list()
    for cog in result:
        cogfut = asyncio.run_coroutine_threadsafe(cog.isload(), botinst.loop)
        cogresult = cogfut.result()
        coglist.append((cog.name, cogresult))
    return coglist

def get_cmd_list(cogname):
    # structure:
    # return = list(commandinfo)
    # commandinfo = tuple(commandname, commandaliases)
    # commandaliases = list(commandalias)
    fut = asyncio.run_coroutine_threadsafe(gen_cmd_list_from_cog(cogname), botinst.loop)
    result = fut.result()
    cmdlist = list()
    for command in result:
        commandfut = asyncio.run_coroutine_threadsafe(command.list_alias(), botinst.loop)
        commandresult = commandfut.result()
        cmdlist.append((command.name, commandresult))
    return cmdlist

def get_guild_list():
    # structure:
    # return = list(guildinfo)
    # guildinfo = tuple(guildid, guildname, guildownerid, guildvoice_channelsid, guildtext_channelsid)
    # guildvoice_channelsid = list(guildvoice_channelid)
    # guildtext_channelsid = list(guildtext_channelid)
    guildlist = list()
    # @TheerapakG: TODO: thread unsafe, need deep copy in the bot thread or lock bot execution up
    for guild in botinst.guilds.copy():
        guildlist.append((guild.id, guild.name, guild.owner.id, [voice_channel.id for voice_channel in guild.voice_channels], [text_channel.id for text_channel in guild.text_channels]))
    return guildlist

def get_member_list(guildid):
    # structure:
    # return = list(memberinfo)
    # memberinfo = tuple(memberid, membername, memberdisplay_name, memberstatus, memberactivity)
    # memberactivity = tuple(None) | tuple('Game', gamename) | tuple('Streaming', streamingname, streamingurl)
    guild = threadsafe_eval_bot('self.get_guild({0})'.format(guildid))
    memberlist = list()
    # @TheerapakG: TODO: thread unsafe, need deep copy in the bot thread or lock bot execution up
    for member in guild.members.copy():
        memberactivity = None
        if isinstance(member.activity, discord.Game):
            memberactivity = ('Game', member.activity.name)
        elif isinstance(member.activity, discord.Streaming):
            memberactivity = ('Streaming', member.activity.name, member.activity.url)
        memberlist.append((member.id, member.name, member.display_name, str(member.status), memberactivity))
    return memberlist

def get_player(guildid):
    # structure:
    # return = tuple(voiceclientid, playerplaylist, playercurrententry, playerstate, playerkaraokemode) | None
    # playerplaylist = list(playerentry)
    # playercurrententry = playerentry | None
    # playerentry = tuple(entry.url, entry.title)
    player = threadsafe_eval_bot('self.get_player_in(self.get_guild({0}))'.format(guildid))
    # @TheerapakG: TODO: thread unsafe, need deep copy in the bot thread or lock bot execution up
    return (player.voice_client.session_id, [(entry.url, entry.title) for entry in player.playlist.entries.copy()], (player._current_entry.url, player._current_entry.title) if player._current_entry else None, str(player.state), player.karaoke_mode) if player else None