from discord.ext import commands
import discord
import os

import challonge

bot = commands.Bot(command_prefix='/', description='Talk to the TO')
tournament_url = 'https://mtvmelee.challonge.com/100_amateur'
gar = challonge.Challonge(tournament_url)

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
    open_matches = await gar.get_open_matches()
    for match in open_matches:
        await ctx.send('{round}: @{player1} vs @{player2}', **match)
    await ctx.send('@DJSwerve vs @DJSwerve')

@bot.event
async def on_ready():
    print('>>> auTO has connected to Discord')

@bot.event
async def on_message(message):
    if message.content == '!bracket':
        await message.channel.send(tournament_url)

if __name__ == '__main__':
    token = os.environ.get('DISCORD_TOKEN')

    if token is None:
        raise RuntimeError('DISCORD_TOKEN not set')

    bot.run(token)
