from discord.ext import commands
import discord
import os

bot = commands.Bot(command_prefix='/', description='Talk to the TO')

@bot.group()
async def auTO(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Use `/auTO help` for options')

@auTO.command()
async def start(ctx, url):
    """Sets tournament URL and start calling matches."""
    pass

@auTO.command()
async def matches(ctx):
    """Checks for match updates and prints current matches to the channel."""
    pass

@bot.event
async def on_ready():
    print('>>> auTO has connected to Discord')

@bot.event
async def on_message(message):
    if message.content == '!bracket':
        # TODO: Post tournament URL.
        pass

if __name__ == '__main__':
    token = os.environ.get('DISCORD_TOKEN')
    bot.run(token)
