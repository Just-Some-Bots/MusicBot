from .common import *

async def cmd_repeat(self, player, channel, author, permissions):
    """
    Usage:
        {command_prefix}repeat

    puts the current song on a loop.
    """
    if not player.is_playing:
        reply_text = "Music needs to be playing before you can repeat."

    else:
        player.repeat = not player.repeat
        status = "enabled" if player.repeat else "disabled"
        reply_text = "repeat has been " + status


    return Response(reply_text, delete_after=30)

async def cmd_choose(self, channel, author, leftover_args):
    """
    Usage:
        {command_prefix}choose a;b;c;...

    The bot will choose an option from all the ones listed separated by a semicolon.
    """
    if leftover_args:
        full_string = ' '.join([*leftover_args])
        option_list = full_string.split(';')
        num_options = len(option_list) - 1
        reply_text = option_list[randint(0, num_options)]
        return Response(reply_text)

async def cmd_8ball(self, channel, author, leftover_args):
    """
    Usage:
        {command_prefix}8ball [a yes/no question]

    The bot will answer your question with one of many answers.
    """
    if leftover_args:
        ebr = ["Yes", "Very doubtful", "Totally!" ,"Probably not","Perhaps","Of course!","Not sure","Nope","No","NO - It may cause disease contraction","My sources say yes","My sources say no","Most likely no","Most likely","Most definitely yes","Maybe","It is uncertain","For sure","Dont even think about it","Don't count on it","Definitely no" ,"Ask me again later" ,"As I see it, yes"]
        num_options = len(ebr) - 1
        reply_text = ebr[randint(0, num_options)]
        print(reply_text)
        return Response(reply_text)


 