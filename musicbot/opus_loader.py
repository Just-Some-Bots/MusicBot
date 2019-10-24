from discord import opus

def load_opus_lib():
    if opus.is_loaded():
        return

    try:
        opus._load_default()
        return
    except OSError:
         pass

    raise RuntimeError('Could not load an opus lib.')
