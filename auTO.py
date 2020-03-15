import aiohttp
import discord
from discord.ext import tasks, commands
import logging
import os
import re

import challonge

# logger = logging.getLogger('discord')
# logger.setLevel(logging.DEBUG)
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
# handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
# logger.addHandler(handler)

class TOCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.open_matches = []
        self.session = None
        self.gar = None
        self.started = False
        self.bot.loop.create_task(self.create_gar())

    async def create_gar(self):
        await self.bot.wait_until_ready()
        self.session = aiohttp.ClientSession(raise_for_status=True)
        self.gar = challonge.Challonge(self.session)

    @commands.group()
    async def auTO(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Use `/auTO help` for options')

    @auTO.command()
    async def help(self, ctx):
        await ctx.send('¯\_(ツ)_/¯')

    @auTO.command(brief='Challonge URL of tournament')
    async def start(self, ctx, url):
        """Sets tournament URL and start calling matches."""
        if self.started:
            await ctx.send('Tournament is already in progress')
            return

        try:
            tournament_id = challonge.extract_id(url)
        except ValueError as e:
            await ctx.send(e)
            return

        await ctx.trigger_typing()
        await self.gar.get_raw(tournament_id)
        self.started = True

        start_msg = await ctx.send('Starting {}! {}'.format(
            self.gar.get_name(), self.gar.get_url()))
        await start_msg.pin()
        await self.matches(ctx)

    async def end_tournament(self, ctx):
        # TODO: Print the top 3.
        self.started = False
        await ctx.send('End of tournament. Thanks for coming!')

    @auTO.command()
    async def matches(self, ctx):
        """Checks for match updates and prints matches to the channel."""
        if not self.started:
            await ctx.send('tournament not started')
            return

        await ctx.trigger_typing()
        self.open_matches = await self.gar.get_open_matches()

        if not self.open_matches:
            await self.end_tournament(ctx)
            return

        announcement = []
        for m in self.open_matches:
            match = '**{}**: {} vs {}'.format(m['round'],
                                              self.mention_user(m['player1']),
                                              self.mention_user(m['player2']))
            announcement.append(match)

        await ctx.send('\n'.join(announcement))

    @auTO.command(brief='Report match results')
    async def report(self, ctx, scores_csv: str):
        if not self.started:
            return

        if not re.match('\d-\d', scores_csv):
            await ctx.send('Invalid report. Should be `/auTO report your_score-opponent_score`')
            return

        scores = [int(n) for n in scores_csv.split('-')]

        if scores[0] > scores[1]:
            player1_win = True
        elif scores[0] < scores[1]:
            player1_win = False
        else:
            await ctx.send('No ties allowed')
            return

        match_id = None
        winner_id = None
        # TODO: This assumes the Challonge and Discord usernames are the same.
        username = ctx.author.display_name

        for match in self.open_matches:
            if username not in [match['player1'], match['player2']]:
                continue

            match_id = match['id']
            if username == match['player2']:
                # Scores are reported with player1's score first.
                scores_csv = scores_csv[::-1]
                player1_win = not player1_win

            if player1_win:
                winner_id = match['player1_id']
            else:
                winner_id = match['player2_id']

        if match_id is None:
            await ctx.send('{} not found in current matches'.format(username))
            return

        await ctx.trigger_typing()
        await self.gar.report_match(match_id, winner_id, scores_csv)
        await self.matches(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if not isinstance(err, commands.MissingRequiredArgument):
            raise err

        if ctx.invoked_subcommand.name == 'start':
            await ctx.send('Tournament URL is required')
        else:
            await ctx.send(err)

    @commands.Cog.listener()
    async def on_ready(self):
        print('>>> auTO has connected to Discord')

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.started and message.content == '!bracket':
            await message.channel.send(self.gar.get_url())

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        # TODO: Map Challonge usernames to Discord usernames.
        for member in self.bot.get_all_members():
            if member.display_name == username:
                return member.mention
        return '@{}'.format(username)

if __name__ == '__main__':
    TOKEN = os.environ.get('DISCORD_TOKEN')

    if TOKEN is None:
        raise RuntimeError('DISCORD_TOKEN is unset')

    bot = commands.Bot(command_prefix='/', description='Talk to the TO')
    bot.add_cog(TOCommands(bot))
    bot.run(TOKEN)
