from discord.ext import commands
import discord

# TODO: Copy challonge API code to here.

bot = commands.Bot(command_prefix='/', description='Talk to the TO')

@bot.group()
async def auTO(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Use `/auTO help` for options')

@auTO.command()
async def start(ctx, url):
    # TODO: DM caller to configure Challonge credentials, otherwise start
    # calling matches.

@auTO.command()
async def matches(ctx):
    """Checks for match updates and prints current matches to the channel."""
    pass

@bot.event
async def on_ready():
    print('>>> auTO has connected to Discord')

@bot.event
async def on_message(message):
    # TODO: Verify that the user is allowed to run this command.
    if not isinstance(message.channel, discord.channel.DMChannel):
        return

    # TODO: Pass Challonge credentials to the bot.
    print('got dm: "{}"'.format(message.content))

if __name__ == '__main__':
    token = ''
    bot.run(token)
