cogs = list()
from . import autoplaylist
cogs.extend(autoplaylist.cogs)
from . import botmanipulate
cogs.extend(botmanipulate.cogs)
from . import cogsmanipulate
cogs.extend(cogsmanipulate.cogs)
from . import dev
cogs.extend(dev.cogs)
# help
from . import info
cogs.extend(info.cogs)
from . import moderate
cogs.extend(moderate.cogs)
# playback
# queuemanipulate
from . import utility
cogs.extend(utility.cogs)