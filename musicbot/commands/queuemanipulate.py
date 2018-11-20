import time
import re
import asyncio
import traceback
import logging
import shlex
import random
import math

from textwrap import dedent

from ..utils import fixg, ftimedelta, _func_
from .. import exceptions
from ..constructs import Response

log = logging.getLogger(__name__)

cog_name = 'queue_management'

async def cmd_play(bot, message, player, channel, author, permissions, leftover_args, song_url):
    """
    Usage:
        {command_prefix}play song_link
        {command_prefix}play text to search for
        {command_prefix}play spotify_uri

    Adds the song to the playlist.  If a link is not provided, the first
    result from a youtube search is added to the queue.

    If enabled in the config, the bot will also support Spotify URIs, however
    it will use the metadata (e.g song name and artist) to find a YouTube
    equivalent of the song. Streaming from Spotify is not possible.
    """

    song_url = song_url.strip('<>')

    await bot.send_typing(channel)

    if leftover_args:
        song_url = ' '.join([song_url, *leftover_args])
    leftover_args = None  # prevent some crazy shit happening down the line

    # Make sure forward slashes work properly in search queries
    linksRegex = '((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)'
    pattern = re.compile(linksRegex)
    matchUrl = pattern.match(song_url)
    song_url = song_url.replace('/', '%2F') if matchUrl is None else song_url

    # Rewrite YouTube playlist URLs if the wrong URL type is given
    playlistRegex = r'watch\?v=.+&(list=[^&]+)'
    matches = re.search(playlistRegex, song_url)
    groups = matches.groups() if matches is not None else []
    song_url = "https://www.youtube.com/playlist?" + groups[0] if len(groups) > 0 else song_url

    if bot.config._spotify:
        if 'open.spotify.com' in song_url:
            song_url = 'spotify:' + re.sub('(http[s]?:\/\/)?(open.spotify.com)\/', '', song_url).replace('/', ':') # pylint: disable=anomalous-backslash-in-string
        if song_url.startswith('spotify:'):
            parts = song_url.split(":")
            try:
                if 'track' in parts:
                    res = await bot.spotify.get_track(parts[-1])
                    song_url = res['artists'][0]['name'] + ' ' + res['name'] 

                elif 'album' in parts:
                    res = await bot.spotify.get_album(parts[-1])
                    await bot._do_playlist_checks(permissions, player, author, res['tracks']['items'])
                    procmesg = await bot.safe_send_message(channel, bot.str.get('cmd-play-spotify-album-process', 'Processing album `{0}` (`{1}`)').format(res['name'], song_url))
                    for i in res['tracks']['items']:
                        song_url = i['name'] + ' ' + i['artists'][0]['name']
                        log.debug('Processing {0}'.format(song_url))
                        await cmd_play(bot, message, player, channel, author, permissions, leftover_args, song_url)
                    await bot.safe_delete_message(procmesg)
                    return Response(bot.str.get('cmd-play-spotify-album-queued', "Enqueued `{0}` with **{1}** songs.").format(res['name'], len(res['tracks']['items'])))
                
                elif 'playlist' in parts:
                    res = []
                    r = await bot.spotify.get_playlist_tracks(parts[-1])
                    while True:
                        res.extend(r['items'])
                        if r['next'] is not None:
                            r = await bot.spotify.make_spotify_req(r['next'])
                            continue
                        else:
                            break
                    await bot._do_playlist_checks(permissions, player, author, res)
                    procmesg = await bot.safe_send_message(channel, bot.str.get('cmd-play-spotify-playlist-process', 'Processing playlist `{0}` (`{1}`)').format(parts[-1], song_url))
                    for i in res:
                        song_url = i['track']['name'] + ' ' + i['track']['artists'][0]['name']
                        log.debug('Processing {0}'.format(song_url))
                        await cmd_play(bot, message, player, channel, author, permissions, leftover_args, song_url)
                    await bot.safe_delete_message(procmesg)
                    return Response(bot.str.get('cmd-play-spotify-playlist-queued', "Enqueued `{0}` with **{1}** songs.").format(parts[-1], len(res)))
                
                else:
                    raise exceptions.CommandError(bot.str.get('cmd-play-spotify-unsupported', 'That is not a supported Spotify URI.'), expire_in=30)
            except exceptions.SpotifyError:
                raise exceptions.CommandError(bot.str.get('cmd-play-spotify-invalid', 'You either provided an invalid URI, or there was a problem.'))

    async with bot.aiolocks[_func_() + ':' + str(author.id)]:
        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                bot.str.get('cmd-play-limit', "You have reached your enqueued song limit ({0})").format(permissions.max_songs), expire_in=30
            )

        if player.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"), expire_in=30
            )

        try:
            info = await bot.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
        except Exception as e:
            if 'unknown url type' in str(e):
                song_url = song_url.replace(':', '')  # it's probably not actually an extractor
                info = await bot.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
            else:
                raise exceptions.CommandError(e, expire_in=30)

        if not info:
            raise exceptions.CommandError(
                bot.str.get('cmd-play-noinfo', "That video cannot be played. Try using the {0}stream command.").format(bot.config.command_prefix),
                expire_in=30
            )

        log.debug(info)

        if info.get('extractor', '') not in permissions.extractors and permissions.extractors:
            raise exceptions.PermissionsError(
                bot.str.get('cmd-play-badextractor', "You do not have permission to play media from this service."), expire_in=30
            )

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
            info = await bot.downloader.extract_info(
                player.playlist.loop,
                song_url,
                download=False,
                process=True,    # ASYNC LAMBDAS WHEN
                on_error=lambda e: asyncio.ensure_future(
                    bot.safe_send_message(channel, "```\n%s\n```" % e, expire_in=120), loop=bot.loop),
                retry_on_error=True
            )

            if not info:
                raise exceptions.CommandError(
                    bot.str.get('cmd-play-nodata', "Error extracting info from search string, youtubedl returned no data. "
                                                    "You may need to restart the bot if this continues to happen."), expire_in=30
                )

            if not all(info.get('entries', [])):
                # empty list, no data
                log.debug("Got empty list, no data")
                return

            # TODO: handle 'webpage_url' being 'ytsearch:...' or extractor type
            song_url = info['entries'][0]['webpage_url']
            info = await bot.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
            # Now I could just do: return await cmd_play(player, channel, author, song_url)
            # But this is probably fine

        # TODO: Possibly add another check here to see about things like the bandcamp issue
        # TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

        if 'entries' in info:
            await bot._do_playlist_checks(permissions, player, author, info['entries'])

            num_songs = sum(1 for _ in info['entries'])

            if info['extractor'].lower() in ['youtube:playlist', 'soundcloud:set', 'bandcamp:album']:
                try:
                    return await _cmd_play_playlist_async(bot, player, channel, author, permissions, song_url, info['extractor'])
                except exceptions.CommandError:
                    raise
                except Exception as e:
                    log.error("Error queuing playlist", exc_info=True)
                    raise exceptions.CommandError(bot.str.get('cmd-play-playlist-error', "Error queuing playlist:\n`{0}`").format(e), expire_in=30)

            t0 = time.time()

            # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
            # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
            # I don't think we can hook into it anyways, so this will have to do.
            # It would probably be a thread to check a few playlists and get the speed from that
            # Different playlists might download at different speeds though
            wait_per_song = 1.2

            procmesg = await bot.safe_send_message(
                channel,
                bot.str.get('cmd-play-playlist-gathering-1', 'Gathering playlist information for {0} songs{1}').format(
                    num_songs,
                    bot.str.get('cmd-play-playlist-gathering-2', ', ETA: {0} seconds').format(fixg(
                        num_songs * wait_per_song)) if num_songs >= 10 else '.'))

            # We don't have a pretty way of doing this yet.  We need either a loop
            # that sends these every 10 seconds or a nice context manager.
            await bot.send_typing(channel)

            # TODO: I can create an event emitter object instead, add event functions, and every play list might be asyncified
            #       Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok

            entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)

            tnow = time.time()
            ttime = tnow - t0
            listlen = len(entry_list)
            drop_count = 0

            if permissions.max_song_length:
                for e in entry_list.copy():
                    if e.duration > permissions.max_song_length:
                        player.playlist.entries.remove(e)
                        entry_list.remove(e)
                        drop_count += 1
                        # Im pretty sure there's no situation where this would ever break
                        # Unless the first entry starts being played, which would make this a race condition
                if drop_count:
                    print("Dropped %s songs" % drop_count)

            log.info("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                listlen,
                fixg(ttime),
                ttime / listlen if listlen else 0,
                ttime / listlen - wait_per_song if listlen - wait_per_song else 0,
                fixg(wait_per_song * num_songs))
            )

            await bot.safe_delete_message(procmesg)

            if not listlen - drop_count:
                raise exceptions.CommandError(
                    bot.str.get('cmd-play-playlist-maxduration', "No songs were added, all songs were over max duration (%ss)") % permissions.max_song_length,
                    expire_in=30
                )

            reply_text = bot.str.get('cmd-play-playlist-reply', "Enqueued **%s** songs to be played. Position in queue: %s")
            btext = str(listlen - drop_count)

        else:
            if info.get('extractor', '').startswith('youtube:playlist'):
                try:
                    info = await bot.downloader.extract_info(player.playlist.loop, 'https://www.youtube.com/watch?v=%s' % info.get('url', ''), download=False, process=False)
                except Exception as e:
                    raise exceptions.CommandError(e, expire_in=30)

            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                raise exceptions.PermissionsError(
                    bot.str.get('cmd-play-song-limit', "Song duration exceeds limit ({0} > {1})").format(info['duration'], permissions.max_song_length),
                    expire_in=30
                )

            try:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            except exceptions.WrongEntryTypeError as e:
                if e.use_url == song_url:
                    log.warning("Determined incorrect entry type, but suggested url is the same.  Help.")

                log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                log.debug("Using \"%s\" instead" % e.use_url)

                return await cmd_play(bot, message, player, channel, author, permissions, leftover_args, e.use_url)

            reply_text = bot.str.get('cmd-play-song-reply', "Enqueued `%s` to be played. Position in queue: %s")
            btext = entry.title


        if position == 1 and player.is_stopped:
            position = bot.str.get('cmd-play-next', 'Up next!')
            reply_text %= (btext, position)

        else:
            try:
                time_until = await player.playlist.estimate_time_until(position, player)
                reply_text += bot.str.get('cmd-play-eta', ' - estimated time until playing: %s')
            except:
                traceback.print_exc()
                time_until = ''

            reply_text %= (btext, position, ftimedelta(time_until))

    return Response(reply_text, delete_after=30)

async def _cmd_play_playlist_async(bot, player, channel, author, permissions, playlist_url, extractor_type):
    """
    Secret handler to use the async wizardry to make playlist queuing non-"blocking"
    """

    await bot.send_typing(channel)
    info = await bot.downloader.extract_info(player.playlist.loop, playlist_url, download=False, process=False)

    if not info:
        raise exceptions.CommandError(bot.str.get('cmd-play-playlist-invalid', "That playlist cannot be played."))

    num_songs = sum(1 for _ in info['entries'])
    t0 = time.time()

    busymsg = await bot.safe_send_message(
        channel, bot.str.get('cmd-play-playlist-process', "Processing {0} songs...").format(num_songs))  # TODO: From playlist_title
    await bot.send_typing(channel)

    entries_added = 0
    if extractor_type == 'youtube:playlist':
        try:
            entries_added = await player.playlist.async_process_youtube_playlist(
                playlist_url, channel=channel, author=author)
            # TODO: Add hook to be called after each song
            # TODO: Add permissions

        except Exception:
            log.error("Error processing playlist", exc_info=True)
            raise exceptions.CommandError(bot.str.get('cmd-play-playlist-queueerror', 'Error handling playlist {0} queuing.').format(playlist_url), expire_in=30)

    elif extractor_type.lower() in ['soundcloud:set', 'bandcamp:album']:
        try:
            entries_added = await player.playlist.async_process_sc_bc_playlist(
                playlist_url, channel=channel, author=author)
            # TODO: Add hook to be called after each song
            # TODO: Add permissions

        except Exception:
            log.error("Error processing playlist", exc_info=True)
            raise exceptions.CommandError(bot.str.get('cmd-play-playlist-queueerror', 'Error handling playlist {0} queuing.').format(playlist_url), expire_in=30)


    songs_processed = len(entries_added)
    drop_count = 0
    skipped = False

    if permissions.max_song_length:
        for e in entries_added.copy():
            if e.duration > permissions.max_song_length:
                try:
                    player.playlist.entries.remove(e)
                    entries_added.remove(e)
                    drop_count += 1
                except:
                    pass

        if drop_count:
            log.debug("Dropped %s songs" % drop_count)

        if player.current_entry and player.current_entry.duration > permissions.max_song_length:
            await bot.safe_delete_message(bot.server_specific_data[channel.guild]['last_np_msg'])
            bot.server_specific_data[channel.guild]['last_np_msg'] = None
            skipped = True
            player.skip()
            entries_added.pop()

    await bot.safe_delete_message(busymsg)

    songs_added = len(entries_added)
    tnow = time.time()
    ttime = tnow - t0
    wait_per_song = 1.2
    # TODO: actually calculate wait per song in the process function and return that too

    # This is technically inaccurate since bad songs are ignored but still take up time
    log.info("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
        songs_processed,
        num_songs,
        fixg(ttime),
        ttime / num_songs if num_songs else 0,
        ttime / num_songs - wait_per_song if num_songs - wait_per_song else 0,
        fixg(wait_per_song * num_songs))
    )

    if not songs_added:
        basetext = bot.str.get('cmd-play-playlist-maxduration', "No songs were added, all songs were over max duration (%ss)") % permissions.max_song_length
        if skipped:
            basetext += bot.str.get('cmd-play-playlist-skipped', "\nAdditionally, the current song was skipped for being too long.")

        raise exceptions.CommandError(basetext, expire_in=30)

    return Response(bot.str.get('cmd-play-playlist-reply-secs', "Enqueued {0} songs to be played in {1} seconds").format(
        songs_added, fixg(ttime, 1)), delete_after=30)

async def cmd_stream(bot, player, channel, author, permissions, song_url):
    """
    Usage:
        {command_prefix}stream song_link

    Enqueue a media stream.
    This could mean an actual stream like Twitch or shoutcast, or simply streaming
    media without predownloading it.  Note: FFmpeg is notoriously bad at handling
    streams, especially on poor connections.  You have been warned.
    """

    song_url = song_url.strip('<>')

    if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
        raise exceptions.PermissionsError(
            bot.str.get('cmd-stream-limit', "You have reached your enqueued song limit ({0})").format(permissions.max_songs), expire_in=30
        )

    if player.karaoke_mode and not permissions.bypass_karaoke_mode:
        raise exceptions.PermissionsError(
            bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"), expire_in=30
        )

    await bot.send_typing(channel)
    await player.playlist.add_stream_entry(song_url, channel=channel, author=author)

    return Response(bot.str.get('cmd-stream-success', "Streaming."), delete_after=6)

async def cmd_search(bot, message, player, channel, author, permissions, leftover_args):
    """
    Usage:
        {command_prefix}search [service] [number] query

    Searches a service for a video and adds it to the queue.
    - service: any one of the following services:
        - youtube (yt) (default if unspecified)
        - soundcloud (sc)
        - yahoo (yh)
    - number: return a number of video results and waits for user to choose one
        - defaults to 3 if unspecified
        - note: If your search query starts with a number,
                you must put your query in quotes
        - ex: {command_prefix}search 2 "I ran seagulls"
    The command issuer can use reactions to indicate their response to each result.
    """

    if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
        raise exceptions.PermissionsError(
            bot.str.get('cmd-search-limit', "You have reached your playlist item limit ({0})").format(permissions.max_songs),
            expire_in=30
        )

    if player.karaoke_mode and not permissions.bypass_karaoke_mode:
        raise exceptions.PermissionsError(
            bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"), expire_in=30
        )

    def argcheck():
        if not leftover_args:
            # noinspection PyUnresolvedReferences
            raise exceptions.CommandError(
                bot.str.get('cmd-search-noquery', "Please specify a search query.\n%s") % dedent(
                    cmd_search.__doc__.format(command_prefix=bot.config.command_prefix)),
                expire_in=60
            )

    argcheck()

    try:
        leftover_args = shlex.split(' '.join(leftover_args))
    except ValueError:
        raise exceptions.CommandError(bot.str.get('cmd-search-noquote', "Please quote your search query properly."), expire_in=30)

    service = 'youtube'
    items_requested = 3
    max_items = permissions.max_search_items
    services = {
        'youtube': 'ytsearch',
        'soundcloud': 'scsearch',
        'yahoo': 'yvsearch',
        'yt': 'ytsearch',
        'sc': 'scsearch',
        'yh': 'yvsearch'
    }

    if leftover_args[0] in services:
        service = leftover_args.pop(0)
        argcheck()

    if leftover_args[0].isdigit():
        items_requested = int(leftover_args.pop(0))
        argcheck()

        if items_requested > max_items:
            raise exceptions.CommandError(bot.str.get('cmd-search-searchlimit', "You cannot search for more than %s videos") % max_items)

    # Look jake, if you see this and go "what the fuck are you doing"
    # and have a better idea on how to do this, i'd be delighted to know.
    # I don't want to just do ' '.join(leftover_args).strip("\"'")
    # Because that eats both quotes if they're there
    # where I only want to eat the outermost ones
    if leftover_args[0][0] in '\'"':
        lchar = leftover_args[0][0]
        leftover_args[0] = leftover_args[0].lstrip(lchar)
        leftover_args[-1] = leftover_args[-1].rstrip(lchar)

    search_query = '%s%s:%s' % (services[service], items_requested, ' '.join(leftover_args))

    search_msg = await bot.safe_send_message(channel, bot.str.get('cmd-search-searching', "Searching for videos..."))
    await bot.send_typing(channel)

    try:
        info = await bot.downloader.extract_info(player.playlist.loop, search_query, download=False, process=True)

    except Exception as e:
        await bot.safe_edit_message(search_msg, str(e), send_if_fail=True)
        return
    else:
        await bot.safe_delete_message(search_msg)

    if not info:
        return Response(bot.str.get('cmd-search-none', "No videos found."), delete_after=30)

    for e in info['entries']:
        result_message = await bot.safe_send_message(channel, bot.str.get('cmd-search-result', "Result {0}/{1}: {2}").format(
            info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

        def check(reaction, user):
            return user == message.author and reaction.message.id == result_message.id  # why can't these objs be compared directly?

        reactions = ['\u2705', '\U0001F6AB', '\U0001F3C1']
        for r in reactions:
            await result_message.add_reaction(r)

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check) # pylint: disable=unused-variable
        except asyncio.TimeoutError:
            await bot.safe_delete_message(result_message)
            return

        if str(reaction.emoji) == '\u2705':  # check
            await bot.safe_delete_message(result_message)
            await cmd_play(bot, message, player, channel, author, permissions, [], e['webpage_url'])
            return Response(bot.str.get('cmd-search-accept', "Alright, coming right up!"), delete_after=30)
        elif str(reaction.emoji) == '\U0001F6AB':  # cross
            await bot.safe_delete_message(result_message)
            continue
        else:
            await bot.safe_delete_message(result_message)
            break

    return Response(bot.str.get('cmd-search-decline', "Oh well :("), delete_after=30)

async def cmd_shuffle(bot, channel, player):
    """
    Usage:
        {command_prefix}shuffle

    Shuffles the server's queue.
    """

    player.playlist.shuffle()

    cards = ['\N{BLACK SPADE SUIT}', '\N{BLACK CLUB SUIT}', '\N{BLACK HEART SUIT}', '\N{BLACK DIAMOND SUIT}']
    random.shuffle(cards)

    hand = await bot.safe_send_message(channel, ' '.join(cards))
    await asyncio.sleep(0.6)

    for x in range(4): # pylint: disable=unused-variable
        random.shuffle(cards)
        await bot.safe_edit_message(hand, ' '.join(cards))
        await asyncio.sleep(0.6)

    await bot.safe_delete_message(hand, quiet=True)
    return Response(bot.str.get('cmd-shuffle-reply', "Shuffled `{0}`'s queue.").format(player.voice_client.channel.guild), delete_after=15)

async def cmd_clear(bot, player, author):
    """
    Usage:
        {command_prefix}clear

    Clears the playlist.
    """

    player.playlist.clear()
    return Response(bot.str.get('cmd-clear-reply', "Cleared `{0}`'s queue").format(player.voice_client.channel.guild), delete_after=20)

async def cmd_remove(bot, user_mentions, message, author, permissions, channel, player, index=None):
    """
    Usage:
        {command_prefix}remove [# in queue]

    Removes queued songs. If a number is specified, removes that song in the queue, otherwise removes the most recently queued song.
    """

    if not player.playlist.entries:
        raise exceptions.CommandError(bot.str.get('cmd-remove-none', "There's nothing to remove!"), expire_in=20)

    if user_mentions:
        for user in user_mentions:
            if permissions.remove or author == user:
                try:
                    entry_indexes = [e for e in player.playlist.entries if e.meta.get('author', None) == user]
                    for entry in entry_indexes:
                        player.playlist.entries.remove(entry)
                    entry_text = '%s ' % len(entry_indexes) + 'item'
                    if len(entry_indexes) > 1:
                        entry_text += 's'
                    return Response(bot.str.get('cmd-remove-reply', "Removed `{0}` added by `{1}`").format(entry_text, user.name).strip())

                except ValueError:
                    raise exceptions.CommandError(bot.str.get('cmd-remove-missing', "Nothing found in the queue from user `%s`") % user.name, expire_in=20)

            raise exceptions.PermissionsError(
                bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"), expire_in=20)

    if not index:
        index = len(player.playlist.entries)

    try:
        index = int(index)
    except (TypeError, ValueError):
        raise exceptions.CommandError(bot.str.get('cmd-remove-invalid', "Invalid number. Use {}queue to find queue positions.").format(bot.config.command_prefix), expire_in=20)

    if index > len(player.playlist.entries):
        raise exceptions.CommandError(bot.str.get('cmd-remove-invalid', "Invalid number. Use {}queue to find queue positions.").format(bot.config.command_prefix), expire_in=20)

    if permissions.remove or author == player.playlist.get_entry_at_index(index - 1).meta.get('author', None):
        entry = player.playlist.delete_entry_at_index((index - 1))
        await bot._manual_delete_check(message)
        if entry.meta.get('channel', False) and entry.meta.get('author', False):
            return Response(bot.str.get('cmd-remove-reply-author', "Removed entry `{0}` added by `{1}`").format(entry.title, entry.meta['author'].name).strip())
        else:
            return Response(bot.str.get('cmd-remove-reply-noauthor', "Removed entry `{0}`").format(entry.title).strip())
    else:
        raise exceptions.PermissionsError(
            bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"), expire_in=20
        )

async def cmd_skip(bot, player, channel, author, message, permissions, voice_channel, param=''):
    """
    Usage:
        {command_prefix}skip [force/f]

    Skips the current song when enough votes are cast.
    Owners and those with the instaskip permission can add 'force' or 'f' after the command to force skip.
    """

    if player.is_stopped:
        raise exceptions.CommandError(bot.str.get('cmd-skip-none', "Can't skip! The player is not playing!"), expire_in=20)

    if not player.current_entry:
        if player.playlist.peek():
            if player.playlist.peek()._is_downloading:
                return Response(bot.str.get('cmd-skip-dl', "The next song (`%s`) is downloading, please wait.") % player.playlist.peek().title)

            elif player.playlist.peek().is_downloaded:
                print("The next song will be played shortly.  Please wait.")
            else:
                print("Something odd is happening.  "
                        "You might want to restart the bot if it doesn't start working.")
        else:
            print("Something strange is happening.  "
                    "You might want to restart the bot if it doesn't start working.")
    
    current_entry = player.current_entry

    if (param.lower() in ['force', 'f']) or bot.config.legacy_skip:
        if permissions.instaskip \
            or (bot.config.allow_author_skip and author == player.current_entry.meta.get('author', None)):

            player.skip()  # TODO: check autopause stuff here
            await bot._manual_delete_check(message)
            return Response(bot.str.get('cmd-skip-force', 'Force skipped `{}`.').format(current_entry.title), reply=True, delete_after=30)
        else:
            raise exceptions.PermissionsError(bot.str.get('cmd-skip-force-noperms', 'You do not have permission to force skip.'), expire_in=30)

    # TODO: ignore person if they're deaf or take them out of the list or something?
    # Currently is recounted if they vote, deafen, then vote

    num_voice = sum(1 for m in voice_channel.members if not (
        m.voice.deaf or m.voice.self_deaf or m == bot.user))
    if num_voice == 0: num_voice = 1 # incase all users are deafened, to avoid divison by zero

    num_skips = player.skip_state.add_skipper(author.id, message)

    skips_remaining = min(
        bot.config.skips_required,
        math.ceil(bot.config.skip_ratio_required / (1 / num_voice))  # Number of skips from config ratio
    ) - num_skips

    if skips_remaining <= 0:
        player.skip()  # check autopause stuff here
        return Response(
            bot.str.get('cmd-skip-reply-skipped-1', 'Your skip for `{0}` was acknowledged.\nThe vote to skip has been passed.{1}').format(
                current_entry.title,
                bot.str.get('cmd-skip-reply-skipped-2', ' Next song coming up!') if player.playlist.peek() else ''
            ),
            reply=True,
            delete_after=20
        )

    else:
        # TODO: When a song gets skipped, delete the old x needed to skip messages
        return Response(
            bot.str.get('cmd-skip-reply-voted-1', 'Your skip for `{0}` was acknowledged.\n**{1}** more {2} required to vote to skip this song.').format(
                current_entry.title,
                skips_remaining,
                bot.str.get('cmd-skip-reply-voted-2', 'person is') if skips_remaining == 1 else bot.str.get('cmd-skip-reply-voted-3', 'people are')
            ),
            reply=True,
            delete_after=20
        )