from discord.ext.commands import Cog, group

class Base(Cog):
    '''
    This cog describe elementary actions such as add and remove
    '''
    @group(invoke_without_command=False)
    async def add(self, ctx):
        """
        A command group for adding things
        """
        pass

    @group(invoke_without_command=False)
    async def remove(self, ctx):
        """
        A command group for removing things
        """
        pass

    @group(invoke_without_command=False)
    async def set(self, ctx):
        """
        A command group for setting things
        """
        pass

    @group(invoke_without_command=False)
    async def toggle(self, ctx):
        """
        A command group for toggling things
        """
        pass

    @group(invoke_without_command=False)
    async def list(self, ctx):
        """
        A command group for listing things
        """
        pass


cogs = [Base]