import discord
from .utils import add_method

@add_method(discord.VoiceChannel)
def is_empty(self, exclude_me = True, exclude_deaf = False):
    def check(member: discord.Member):
        if exclude_me and member == self.guild.me:
            return False

        if exclude_deaf and any([member.voice.deaf, member.voice.self_deaf]):
            return False

        return True

    return not sum(1 for m in self.members if check(m))

@add_method(discord.VoiceChannel)
async def get_voice_client(self):
    if self.guild.voice_client:
        return self.guild.voice_client
    else:
        return await self.connect(timeout=60, reconnect=True)

