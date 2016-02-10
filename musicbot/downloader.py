import functools
import youtube_dl

from concurrent.futures import ThreadPoolExecutor

ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(id)s', # part file temp name
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

thread_pool = ThreadPoolExecutor(max_workers=2)
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


def extract_info(loop, *args, **kwargs):
    """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
    """
    return loop.run_in_executor(thread_pool, functools.partial(ytdl.extract_info, *args, **kwargs))
