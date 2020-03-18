from .BaseEB import BaseEB
from .LocalEB import LocalEB
from .SpotifyEB import SpotifyEB
from .YtdlEB import YtdlEB

entrybuilders = [LocalEB, SpotifyEB, YtdlEB]