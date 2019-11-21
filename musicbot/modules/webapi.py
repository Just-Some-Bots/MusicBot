"""
This cog implement webserver that can respond to bot query which
maybe useful for interfacing with external application.
If you don't need querying via webserver, you shouldn't load this cog

If the API will be exposed to the internet, consider specifying
certificate for security against packet sniffing from third party

DO NOT GIVE GENERATED TOKENS TO UNKNOWN RANDOM PEOPLE!! ANYONE WITH TOKEN
CAN ISSUE REMOTE EXECUTION VIA post:eval and post:exec METHODS. FAILING TO DO
THIS CAN RESULT IN COMPROMISE OF YOUR MACHINE'S SECURITY.
"""

import socket
import sys
import logging
import asyncio
import threading
import json
import traceback
import os
from discord.ext.commands import Cog, command
from functools import partial
from collections import defaultdict
from secrets import token_urlsafe
from urllib.parse import urlparse, parse_qs
from aiohttp import web

import discord

import ssl

from ..wrappers import owner_only

from .. import messagemanager
from ..rich_guild import get_guild

aiolocks = defaultdict(asyncio.Lock)

def notify():
    return __doc__

authtoken = list()

async def serialize_tokens(bot):
    directory = 'data/tokens.json'
    async with aiolocks['token_serialization']:
        bot.log.debug("Serializing tokens")

        with open(directory, 'w', encoding='utf8') as f:
            f.write(json.dumps(authtoken))

async def deserialize_tokens(bot) -> list:
    directory = 'data/tokens.json'

    async with aiolocks['token_serialization']:
        if not os.path.isfile(directory):
            return list()

        bot.log.debug("Deserializing tokens")

        with open(directory, 'r', encoding='utf8') as f:
            data = f.read()
    
    return json.loads(data)

class Webapi(Cog):
    def __init__(self):
        self.bot = None
        self.webservers = []

    async def pre_init(self, bot):
        self.bot = bot

    async def init(self):
        if self.bot.config.webapi_persistent_tokens:
            global authtoken
            authtoken = await deserialize_tokens(self.bot)

        app = web.Application()
        app.add_routes([
            web.get('/api', self.do_GET),
            web.post('/api/{path}', self.do_POST)
        ])
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        httpsite = web.TCPSite(self.runner, port = self.bot.config.webapi_http_port)
        await httpsite.start()
        self.bot.log.info('enabled http for webapi, binded to {}'.format(self.bot.config.webapi_http_port))
        
        if self.bot.config.ssl_certfile and self.bot.config.ssl_keyfile:
            try:
                cont = ssl.SSLContext()
                cont.load_cert_chain(self.bot.config.ssl_certfile, keyfile = self.bot.config.ssl_keyfile)
            except ssl.SSLError:
                self.bot.log.error('Error loading certificate. Will only enabling http. Traceback below.')
                self.bot.log.error(traceback.format_exc())
            else:
                httpssite = web.TCPSite(self.runner, port = self.bot.config.webapi_https_port, ssl_context = cont)
                await httpssite.start()
                self.bot.log.info('enabled https for webapi, binded to {}'.format(self.bot.config.webapi_https_port))

    async def uninit(self):
        self.bot.log.debug('stopping webservers...')
        await self.runner.cleanup()
            
    async def do_GET(self, request):
        self.bot.log.debug('GET: {}'.format(request.path_qs))
        f = await self.gen_content_GET(request)
        if f != None:
            return web.json_response(f)
        return web.Response(text = 'ERROR 404', status = 404)

    async def do_POST(self, request):
        self.bot.log.debug('POST: {}'.format(request.path_qs))
        f = await self.gen_content_POST(request)
        if f != None:
            return web.json_response(f)
        return web.Response(text = 'ERROR 404', status = 404)

    async def gen_content_GET(self, request):
        param = request.query
        if 'token' in param and param['token'] in authtoken and 'get' in param:
            if param['get'] == 'guild':
                return await get_guild_list(self.bot)
            elif param['get'] == 'member' and 'guild' in param:
                return await get_member_list(self.bot, int(param['guild']))
            elif param['get'] == 'player' and 'guild' in param:
                return await get_player(self.bot, int(param['guild']))
        return None

    async def gen_content_POST(self, request):
        param = await request.json()
        path = request.match_info['path']
        if 'token' in param and param['token'] in authtoken:
            if path == 'exec':
                if 'code' in param:
                    try:
                        await self.bot.exec_bot(param['code'])
                        return {'action':True, 'error':False, 'result':''}
                    except:
                        return {'action':True, 'error':True, 'result':traceback.format_exc()}
                return {'action':False}
            elif path == 'eval':
                if 'code' in param:
                    try:
                        ret = await self.bot.eval_bot(param['code'])
                        return {'action':True, 'error':False, 'result':str(ret)}
                    except:
                        return {'action':True, 'error':True, 'result':traceback.format_exc()}
                return {'action':False}
        return None

    @command()
    @owner_only
    async def gentoken(self, ctx):
        """
        Usage:
            {command_prefix}gentoken

        Generate a token. DO NOT GIVE GENERATED TOKENS TO UNKNOWN RANDOM PEOPLE!!
        ANYONE WITH TOKEN CAN ISSUE REMOTE EXECUTION VIA post:eval and post:exec METHODS.
        FAILING TO DO THIS CAN RESULT IN COMPROMISE OF YOUR MACHINE'S SECURITY.
        """
        token = str(token_urlsafe(64))
        # @TheerapakG: MAYDO: salt this (actually nevermind, if they got this they probably got the bot token too, and that's worse)
        authtoken.append(token)
        if ctx.bot.config.webapi_persistent_tokens:
            await serialize_tokens(ctx.bot)
        await messagemanager.safe_send_normal(ctx, ctx.author, ctx.bot.str.get('webapi?cmd?gentoken?success@gentoken', "Generated token `{0}`.").format(token))
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('webapi?cmd?gentoken?success@sent', "Sent a message containing the token generated."), expire_in=20)

    @command()
    @owner_only
    async def revoketoken(self, ctx, token:str):
        """
        Usage:
            {command_prefix}revoketoken token

        Revoke a token's access to the api.
        """
        try:
            authtoken.remove(token)
            if ctx.bot.config.webapi_persistent_tokens:
                await serialize_tokens(ctx.bot)
            await messagemanager.safe_send_normal(ctx, ctx.author, ctx.bot.str.get('webapi?cmd?revoketoken?success@revtoken', "Successfully revoked token `{0}`").format(token))
        except ValueError:
            await messagemanager.safe_send_message(ctx.author, messagemanager.content_gen(ctx, ctx.bot.str.get('webapi?cmd?revoketoken?fail@revtoken', "Token `{0}` not found").format(token), color = messagemanager.ContentTypeColor.ERROR))
        finally:
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('webapi?cmd?revoketoken?info@action', "Sent a message with information regarding the action."), expire_in=20)

cogs = [Webapi]

async def get_guild_list(bot):
    # structure:
    # return = list(guildinfo)
    # guildinfo = dict(guildid, guildname, guildownerid, guildvoice_channelsid, guildtext_channelsid)
    # guildvoice_channelsid = list(guildvoice_channelid)
    # guildtext_channelsid = list(guildtext_channelid)
    guildlist = list()
    for guild in bot.guilds.copy():
        guildlist.append({'guildid':guild.id, 'guildname':guild.name, 'guildownerid':guild.owner.id, 'guildvoice_channelsid':[voice_channel.id for voice_channel in guild.voice_channels], 'guildtext_channelsid':[text_channel.id for text_channel in guild.text_channels]})
    return guildlist

async def get_member_list(bot, guildid):
    # structure:
    # return = list(memberinfo)
    # memberinfo = dict(memberid, membername, memberdisplay_name, memberstatus, memberactivity)
    # memberactivity = dict('state':'None') | dict('state':'Game', gamename) | dict('state':'Streaming', streamingname, streamingurl)
    guild = bot.get_guild(guildid)
    memberlist = list()
    for member in guild.members.copy():
        memberactivity = {'state':'None'}
        if isinstance(member.activity, discord.Game):
            memberactivity = {'state':'Game', 'gamename':member.activity.name}
        elif isinstance(member.activity, discord.Streaming):
            memberactivity = {'state':'Streaming', 'streamingname':member.activity.name, 'streamingurl':member.activity.url}
        memberlist.append({'memberid':member.id, 'membername':member.name, 'memberdisplay_name':member.display_name, 'memberstatus':str(member.status), 'memberactivity':memberactivity})
    return memberlist

async def get_player(bot, guildid):
    # structure:
    # return = dict(voiceclientid, playerplaylist, playercurrententry, playerstate, playerkaraokemode) | dict()
    # playerplaylist = list(playerentry)
    # playercurrententry = playerentry | dict()
    # playerentry = dict(entryurl, entrytitle)
    guild = get_guild(bot, bot.get_guild(guildid))
    player = await guild.get_player()
    playlist = await player.get_playlist()
    return {'voiceclientid':guild._voice_client.session_id, 'playerplaylist':[{'entryurl':entry.source_url, 'entrytitle':entry.title} for entry in playlist], 'playercurrententry':{'entryurl':player._current.source_url, 'entrytitle':player._current.title} if player._current else dict(), 'playerstate':str(player.state), 'playlistkaraokemode':playlist.karaoke_mode} if player else dict()