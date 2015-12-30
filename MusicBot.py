import asyncio
import discord
import re
import datetime
import youtube_dl
import os
import traceback
from random import shuffle

if not discord.opus.is_loaded():
    discord.opus.load_opus('libopus-0.dll')

try:
    with open('blacklist.txt') as f:
        blacklist = f.readlines()
    for i, item in enumerate(blacklist):
        blacklist[i] = item.rstrip()
    with open('backuplist.txt') as f:
        backuplist = f.readlines()
    for i, item in enumerate(backuplist):
        backuplist[i] = item.rstrip()
    with open('whitelist.txt') as f:
        whitelist = f.readlines()
    for i, item in enumerate(whitelist):
        whitelist[i] = item.rstrip()
    with open('options.txt') as f:
        options = f.readlines()
    for i, item in enumerate(options):
        options[i] = item.rstrip()
    options[2] = bool(options[2])
    options[5] = int(options[5])
except:
    print('one of the text files was deleted, reinstall')

savedir = "playlist"
if not os.path.exists(savedir):
    os.makedirs(savedir)

option = 'butts'
isPlaying = False
firstTime = True

whitelistcheck = options[2]
volume = 0.10
ownerID = options[4]
skipsRequired = options[5]
skipCount = 0
skipperlist = []

playlistnames = []
playlist = []
currentlyPlaying = ''

helpmessage = '`!play [youtube link]` will allow me to play a new song or add it to the queue.' \
              '\n`!playlist` will print out all links to youtube videos currently in the queue!' \
              '\n`!play skip` will make it skip to the next song after ' + \
              str(options[5]) + ' people vote to skip the current one!'

client = discord.Client()


@client.async_event
def on_ready():
    print('Connected!')
    print('Username: ' + client.user.name)
    print('ID: ' + client.user.id)
    print('--Server List--')
    for server in client.servers:
        print(server.name)


@client.async_event
def on_message(message):
    global options
    global option
    global playlistnames
    global ownerID
    global firstTime
    global skipCount
    global skipperlist
    global volume
    if message.author == client.user:
        return
    if message.channel.is_private:
        yield from client.send_message(message.channel, 'You cannot use this bot in private messages.')
    if '!whatismyuserid' in message.content.lower():
        print('HELLO, ' + message.author.name + ' THE ID YOU NEED TO USE IS ' + message.author.id)
    elif '!creator' in message.content.lower():
        yield from client.send_message(message.channel,'I was coded by SexualRhinoceros and am currently on rev1.0! Go here for more info: https://github.com/SexualRhinoceros/MusicBot')
    ownerLocation = None
    for server in client.servers:
        for channel in server.channels:
            pre = discord.utils.get(channel.voice_members, id=ownerID)
            if pre is not None: ownerLocation = pre.server
    if message.server == ownerLocation:
        if '!whitelist' in message.content.lower() and message.author.id == ownerID:
            msg = message.content
            substrStart = msg.find('!whitelist') + 11
            msg = msg[substrStart:]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            f = open('whitelist.txt', 'a')
            f.write(msg + "\r")
            f.close()
            whitelist.append(msg)
        elif '!blacklist' in message.content.lower() and message.author.id == ownerID:
            msg = message.content
            substrStart = msg.find('!blacklist') + 11
            msg = msg[substrStart:]
            msg.strip()
            msg = re.sub('<|@|>', '', msg)
            f = open('blacklist.txt', 'a')
            f.write(msg + "\r")
            f.close()
            blacklist.append(msg)
        elif '!joinserver' in message.content.lower() and message.author.id == ownerID:
            msg = message.content
            substrStart = msg.find('!joinserver') + 12
            msg = msg[substrStart:]
            msg.strip()
            try:
                yield from client.accept_invite(msg)
            except:
                print('you dun fucked up with the URL')
        elif '!servers' in message.content.lower() and message.author.id == '77511942717046784':
            count = 0
            for servers in client.servers:
                count += 1
            if count > 1:
                yield from client.send_message(message.channel,'I DIDN\'T LISTEN TO DIRECTIONS AND HAVE MY BOT ON MORE THAN ONE SERVER')
            else:
                print('you good')
        elif '!playlist' in message.content.lower():

            print('GETTING PLAYLIST: If this is large the bot WILL hang')
            msglist = []
            playlistmsgstorage = []
            endmsg = currentlyPlaying
            count = 1
            for titles in playlistnames:
                print(len(endmsg))
                if len(endmsg) > 1500:
                    msglist.append(endmsg)
                    endmsg = ''
                else:
                    endmsg = endmsg + str(count) + ":  " + titles + " \n"
                    count += 1
            if len(msglist) == 0:
                msglist.append(endmsg)
            for items in msglist:
                temp = yield from client.send_message(message.channel, endmsg)
                playlistmsgstorage.append(temp)
            try:
                yield from client.delete_message(message)
            except:
                print('Error: Cannot delete messages!')
            yield from asyncio.sleep(15)
            for msgs in playlistmsgstorage:
                yield from client.delete_message(msgs)
        elif '!play' in message.content.lower():
            msg = message.content
            substrStart = msg.find('!play') + 6
            msg = msg[substrStart:]
            msg.strip()
            if message.author.id in blacklist:
                print('no, blacklisted')
                return
            if whitelistcheck is True:
                if message.author.id != ownerID:
                    if not is_long_member(message.author.joined_at) and message.author.id not in whitelist:
                        print('no, not whitelisted and new')
                        return
            if msg.lower() == 'help':
                hotsmessage = yield from client.send_message(message.channel, helpmessage)
                yield from asyncio.sleep(10)
                yield from client.delete_message(hotsmessage)
            elif message.author.id == ownerID and firstTime is True:
                yield from client.join_voice_channel(message.author.voice_channel)
                firstTime = False
                if 'playlist' in msg:
                    options = {
                        'format': 'bestaudio/best',
                        'extractaudio': True,
                        'audioformat': "mp3",
                        'outtmpl': '%(id)s',
                        'noplaylist': True,
                        'nocheckcertificate': True,
                        'ignoreerrors': True,
                        'quiet': True,
                        'no_warnings': True,}
                    ydl = youtube_dl.YoutubeDL(options)
                    print('Playlist detected, attempting to parse all URLs. ERRORS MAY OCCUR!')
                    info = ydl.extract_info(msg, download=False)
                    try:
                        boolfirst = True
                        for items in info['entries']:
                            if boolfirst:
                                boolfirst=False
                                playlist.append(items['webpage_url'])
                            else:
                                playlist.append(items['webpage_url'])
                                playlistnames.append(items['title'])
                    except:
                        print('Error with one URL, continuing processing!')
                    print('Playlist Processing finished!')
                else:
                    updateNames(msg)
            elif msg.lower() == 'move' and message.author.id == ownerID:
                option = 'pause'
                playlist_update()
                yield from client.voice.disconnect()
                yield from client.join_voice_channel(message.author.voice_channel)
                option = 'resume'
                playlist_update()
            elif msg.lower() == 'skip':
                if message.author.id == ownerID:
                    print('instaskipping')
                    skipperlist = []
                    skipCount = 0
                    option = 'skip'
                elif message.author.id not in skipperlist:
                    skipperlist.append(message.author.id)
                    skipCount += 1
                    print('Skip Vote by `' + message.author.name + '` to a total of `' + str(skipCount) + '/' + str(skipsRequired) + '`')
                else:
                    print('already voted to skip')
                if skipCount >= skipsRequired:
                    skipperlist = []
                    skipCount = 0
                    option = 'skip'
            elif msg.lower() == 'shuffle':
                if message.author.id == ownerID:
                    shuffle(playlist)
                else:
                    print('only the owner can shuffle')
            elif msg.lower() == 'pause':
                if message.author.id == ownerID:
                    option = 'pause'
                else:
                    print('only the owner can pause')
            elif msg.lower() == 'resume':
                if message.author.id == ownerID:
                    option = 'resume'
                else:
                    print('only the owner can resume')
            elif 'volume' in msg.lower():
                substrStart = msg.find('volume') + 7
                msg = msg[substrStart:]
                msg.strip()
                try:
                    volume = msg
                except:
                    print('thats not a number please use a number')
            else:
                if 'playlist' in msg:
                    options = {
                        'format': 'bestaudio/best',
                        'extractaudio': True,
                        'audioformat': "mp3",
                        'outtmpl': '%(id)s',
                        'noplaylist': True,
                        'nocheckcertificate': True,
                        'ignoreerrors': True,
                        'quiet': True,
                        'no_warnings': True,}
                    ydl = youtube_dl.YoutubeDL(options)
                    print('Playlist detected, attempting to parse all URLs. ERRORS MAY OCCUR!')
                    try:
                        info = ydl.extract_info(msg, download=False)
                        boolfirst = True
                        for items in info['entries']:
                            if boolfirst:
                                boolfirst=False
                                playlist.append(items['webpage_url'])
                            else:
                                playlist.append(items['webpage_url'])
                                playlistnames.append(items['title'])
                    except:
                        print('Error with one URL, continuing processing!')
                    print('Playlist Processing finished!')
                else:
                    updateNames(msg)
            yield from asyncio.sleep(5)
            try:
                yield from client.delete_message(message)
            except:
                print('Couldn\'t delete message for some reason')


def is_long_member(dateJoined):
    convDT = dateJoined.date()
    today = datetime.date.today()
    margin = datetime.timedelta(days=int(options[3]))
    return today - margin > convDT


def do_format(message):
    replacements = (('4', 'a'), ('3', 'e'), ('1', 'l'), ('0', 'o'), ('7', 't'))
    endMsg = re.sub('À|à|Á|á|Â|â|Ã|ã|Ä|ä', 'a', message)
    endMsg = re.sub('È|è|É|é|Ê|ê|Ë|ë', 'e', endMsg)
    endMsg = re.sub('Ì|ì|Í|í|Î|î|Ï|ï', 'i', endMsg)
    endMsg = re.sub('Ò|ò|Ó|ó|Ô|ô|Õ|õ|Ö', 'o', endMsg)
    endMsg = re.sub('Ù|ù|Ú|ú|Û|û|Ü|ü', 'u', endMsg)
    endMsg = re.sub('Ý|ý|Ÿ|ÿ', 'y', endMsg)
    endMsg = re.sub('Ñ|ñ', 'n', endMsg)
    for old, new in replacements:
        endMsg = endMsg.replace(old, new)
    endMsg = re.sub('[^0-9a-zA-Z]+', '', endMsg)
    endMsg = re.sub(r'([a-z])\1+', r'\1', endMsg)
    return endMsg


def updateNames(url):
    options = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': "mp3",
        'outtmpl': '%(id)s',
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'quiet': True,
        'no_warnings': True,}
    ydl = youtube_dl.YoutubeDL(options)
    try:
        info = ydl.extract_info(url, download=False)
        playlistnames.append(info['title'])
        playlist.append(url)
        fixPlaylist()
    except Exception as e:
        x = 0


def fixPlaylist():
    for things in playlist:
        options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': "mp3",
            'outtmpl': '%(id)s',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,}
        ydl = youtube_dl.YoutubeDL(options)
        try:
            info = ydl.extract_info(fixedThings, download=False)
        except Exception as e:
            while fixedThings in playlist: playlist.remove(fixedThings)


def make_savepath(title, savedir=savedir):
    return os.path.join(savedir, "%s.mp3" % (title))


def download_song(unfixedsongURL):
    global currentlyPlaying
    songURL = unfixedsongURL
    options = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': "mp3",
        'outtmpl': '%(id)s',
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'quiet': True,
        'no_warnings': True,}
    ydl = youtube_dl.YoutubeDL(options)
    try:
        info = ydl.extract_info(songURL, download=False)
        title = info['title']
        currentlyPlaying = 'Now: ' + title + '\n'
        title = do_format(title)
        savepath = make_savepath(title)
    except Exception as e:
        print("Can't access song! %s\n" % traceback.format_exc())
        return 'butts!'
    try:
        os.stat(savepath)
        return savepath
    except OSError:
        try:
            result = ydl.extract_info(songURL, download=True)
            os.rename(result['id'], savepath)
            return savepath
        except Exception as e:
            print("Can't download audio! %s\n" % traceback.format_exc())
            return 'butts!'


@asyncio.coroutine
def playlist_update():
    # print('ding')
    global isPlaying
    global backuplist
    global option
    global volume
    global firstTime
    global currentlyPlaying
    yield from client.wait_until_ready()
    count = 0
    time = 0
    while count != -1:
        if isPlaying is False and firstTime is False and option != 'pause':
            if playlist:
                vce = client.voice
                thing = playlist[0]
                try:
                    path = download_song(thing)
                    if path != 'butts!':
                        yield from client.change_status(discord.Game(name=currentlyPlaying[5:]))
                        player = vce.create_ffmpeg_player(path, options='''-filter:a "volume={}"'''.format(volume))
                        player.start()
                        isPlaying = True
                        while thing in playlist: playlist.remove(thing)
                        option = 'sleep'
                    else:
                        while thing in playlist: playlist.remove(thing)
                except:
                    while thing in playlist: playlist.remove(thing)
            elif backuplist:
                shuffle(backuplist)
                thing = backuplist[0]
                vce = client.voice
                try:
                    path = download_song(thing)
                    if path != 'butts!':
                        yield from client.change_status(discord.Game(name=currentlyPlaying[5:]))
                        player = vce.create_ffmpeg_player(path, options='''-filter:a "volume={}"'''.format(volume))
                        player.start()
                        isPlaying = True
                        while thing in backuplist: backuplist.remove(thing)
                        option = 'sleep'
                    else:
                        while thing in backuplist: backuplist.remove(thing)
                except:
                    while thing in backuplist: backuplist.remove(thing)
            else:
                with open('backuplist.txt') as f:
                    backuplist = f.readlines()
                for i, item in enumerate(backuplist):
                    backuplist[i] = item.rstrip()
                shuffle(backuplist)
                vce = client.voice
                thing = backuplist[0]
                try:
                    path = download_song(thing)
                    if path != 'butts!':
                        yield from client.change_status(discord.Game(name=currentlyPlaying[5:]))
                        player = vce.create_ffmpeg_player(path, options='''-filter:a "volume={}"'''.format(volume))
                        player.start()
                        isPlaying = True
                        while thing in backuplist: backuplist.remove(thing)
                        option = 'sleep'
                    else:
                        while thing in backuplist: backuplist.remove(thing)
                except:
                    while thing in backuplist: backuplist.remove(thing)
        if option == 'sleep' or option == 'skip':
            while option != 'skip' and player.is_playing():
                if option == 'pause':
                    player.pause()
                else:
                    yield from asyncio.sleep(1)
            player.stop()
            currentlyPlaying = ''
            isPlaying = False
        elif option == 'pause':
            player.pause()
            isPlaying = False
            while option != 'resume':
                yield from asyncio.sleep(1)
            player.resume()
        else:
            yield from asyncio.sleep(1)


loop = asyncio.get_event_loop()
try:
    loop.create_task(playlist_update())
    loop.run_until_complete(client.login(options[0], options[1]))
    loop.run_until_complete(client.connect())
except Exception:
    loop.run_until_complete(client.close())
finally:
    loop.close()
