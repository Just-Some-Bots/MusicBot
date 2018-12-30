import discord

class VoiceChannel:
    __slots__ = ('original')

    def __init__(self, discord_voicechannel: discord.VoiceChannel):
        self.original = discord_voicechannel

    def is_empty(self, exclude_me = True, exclude_deaf = False):
        def check(member: discord.Member):
            if exclude_me and member == self.original.guild.me:
                return False

            if exclude_deaf and any([member.voice.deaf, member.voice.self_deaf]):
                return False

            return True

        return not sum(1 for m in self.original.members if check(m))
