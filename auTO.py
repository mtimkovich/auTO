import aiohttp
import discord
from discord.ext import commands
import logging
import os
import re
from typing import Optional

import challonge

logging.basicConfig(level=logging.INFO)


class Tournament(object):
    """Tournaments are unique to a guild + channel."""
    def __init__(self, ctx, tournament_id, owner, api_key, session):
        self.guild = ctx.guild
        self.owner = owner
        self.open_matches = []
        self.gar = challonge.Challonge(api_key, tournament_id, session)

    async def get_open_matches(self):
        matches = await self.gar.get_matches()
        self.open_matches = [m for m in matches if m['state'] == 'open']

    async def mark_match_underway(self, user1, user2):
        match_id = None

        for user in [user1, user2]:
            match = self.find_match(user.display_name)
            if match is None:
                return
            elif match_id is None:
                match_id = match['id']
            elif match_id != match['id']:
                return

        await self.gar.mark_underway(match_id)

    def find_match(self, username):
        for match in self.open_matches:
            if username in [match['player1'], match['player2']]:
                return match
        else:
            return None

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        for member in self.guild.members:
            if member.display_name == username:
                return member.mention
        return '@{}'.format(username)

    @classmethod
    def key(cls, ctx):
        return ctx.guild, ctx.channel


class TOCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.tournament_map = {}
        self.bot.loop.create_task(self.create_session())

    async def create_session(self):
        await self.bot.wait_until_ready()
        self.session = aiohttp.ClientSession(raise_for_status=True)

    def get_tourney(self, ctx=None, guild=None, channel=None):
        if ctx is None:
            key = (guild, channel)
        else:
            key = Tournament.key(ctx)
        return self.tournament_map.get(key)

    def tourney_start(self, ctx, tournament_id, owner, api_key):
        tourney = Tournament(ctx, tournament_id, owner, api_key, self.session)
        self.tournament_map[Tournament.key(ctx)] = tourney
        return tourney

    def tourney_stop(self, ctx):
        self.tournament_map.pop(Tournament.key(ctx))

    @commands.group()
    async def auTO(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Use `/auTO help` for options')

    @auTO.command()
    async def help(self, ctx):
        help_list = [
            '- `start [URL]` - start TOing',
            '- `stop` - stop TOing',
            '- `report 0-2` - report a match',
            '- `matches` - print the active matches',
        ]
        await self.send_list(ctx, help_list)

    async def send_list(self, ctx, the_list):
        """Send multi-line messages."""
        await ctx.send('\n'.join(the_list))

    async def ask_for_challonge_key(self,
                                    owner: discord.Member) -> Optional[str]:
        """DM the TO for their Challonge key."""
        dms = owner.dm_channel if owner.dm_channel else await owner.create_dm()
        await dms.send("Hey there! To run this tournament for you, I'll need "
                       "your Challonge API key "
                       "(https://challonge.com/settings/developer). "
                       "The key is only used to run the bracket and is "
                       "deleted after the tournament finishes.")
        await dms.send("If that's ok with you, respond to this message with "
                       "your Challonge API key, otherwise, with 'NO'.")

        def check(m):
            return m.channel == dms and m.author == owner

        while True:
            msg = await self.bot.wait_for('message', check=check)

            content = msg.content.strip()
            if content.lower() == 'no':
                await dms.send('👍')
                return None
            elif re.match(r'[a-z0-9]+$', content, re.I):
                return content
            else:
                await dms.send('Invalid API key, try again.')

    @auTO.command(brief='Challonge URL of tournament')
    async def start(self, ctx, url: str):
        """Sets tournament URL and start calling matches."""
        if self.get_tourney(ctx) is not None:
            await ctx.send('A tournament is already in progress')
            return

        try:
            tournament_id = challonge.extract_id(url)
        except ValueError as e:
            await ctx.send(e)
            return

        api_key = await self.ask_for_challonge_key(ctx.author)

        if api_key is None:
            return

        await ctx.trigger_typing()
        tourney = self.tourney_start(ctx, tournament_id, ctx.author, api_key)
        try:
            await tourney.gar.get_raw()
        except aiohttp.client_exceptions.ClientResponseError as e:
            if e.code == 401:
                await ctx.author.dm_channel.send('Invalid API Key')
                self.tourney_stop(ctx)
                return

        if tourney.gar.get_state() == 'pending':
            await ctx.send("Tournament hasn't been started yet.")
            self.tourney_stop(ctx)
            return
        elif tourney.gar.get_state() == 'ended':
            await ctx.send("Tournament has already finished.")
            self.tourney_stop(ctx)
            return

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

        logging.info('Starting tournament {} on {}'.format(
            tourney.gar.get_name(), tourney.guild.name))
        start_msg = await ctx.send('Starting {}! {}'.format(
            tourney.gar.get_name(), tourney.gar.get_url()))
        await start_msg.pin()
        await self.matches(ctx)

    @auTO.command()
    async def stop(self, ctx):
        tourney = self.get_tourney(ctx)

        if tourney is None:
            return
        elif ctx.author != tourney.owner:
            await ctx.send('Sorry, only {} can stop this tournament.'
                           .format(tourney.mention_user(ctx.author)))
            return

        self.tourney_stop(ctx)
        await self.bot.change_presence()
        await ctx.send('Goodbye 😞')

    async def end_tournament(self, ctx, tourney):
        top3 = await tourney.gar.top3()
        top3 = list(map(tourney.mention_user, top3))
        message = [
            'Congrats to the winner of {}: **{}**!!'.format(
                tourney.gar.get_name(), top3[0]),
            'We had {} entrants!\n'.format(len(tourney.gar.get_players())),
        ]

        for i, player in enumerate(top3, 1):
            message.append('{}. {}'.format(i, player))

        await self.send_list(ctx, message)
        self.tourney_stop(ctx)

    @auTO.command()
    async def matches(self, ctx):
        """Checks for match updates and prints matches to the channel."""
        tourney = self.get_tourney(ctx)
        if tourney is None:
            await ctx.send('No tournament running')
            return

        await ctx.trigger_typing()
        await tourney.get_open_matches()

        if not tourney.open_matches:
            await self.end_tournament(ctx, tourney)
            return

        announcement = []
        for m in tourney.open_matches:
            match = '**{}**: {} vs {}'.format(
                    m['round'], tourney.mention_user(m['player1']),
                    tourney.mention_user(m['player2']))
            if m['underway']:
                match += ' (Playing)'
            announcement.append(match)

        await self.send_list(ctx, announcement)

    @auTO.command(brief='Report match results')
    async def report(self, ctx, scores_csv: str):
        tourney = self.get_tourney(ctx)
        if tourney is None:
            return

        if not re.match(r'\d-\d', scores_csv):
            await ctx.send('Invalid report. Should be `/auTO report 0-2`')
            return

        scores = [int(n) for n in scores_csv.split('-')]

        if scores[0] > scores[1]:
            player1_win = True
        elif scores[0] < scores[1]:
            player1_win = False
        else:
            await ctx.send('No ties allowed.')
            return

        match_id = None
        winner_id = None
        username = ctx.author.display_name

        match = tourney.find_match(username)
        if match is None:
            await ctx.send('{} not found in current matches'.format(username))
            return

        match_id = match['id']
        if username == match['player2']:
            # Scores are reported with player1's score first.
            scores_csv = scores_csv[::-1]
            player1_win = not player1_win

        if player1_win:
            winner_id = match['player1_id']
        else:
            winner_id = match['player2_id']

        await ctx.trigger_typing()
        await tourney.gar.report_match(match_id, winner_id, scores_csv)
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
        logging.info('auTO has connected to Discord')

    @commands.Cog.listener()
    async def on_message(self, message):
        tourney = self.get_tourney(guild=message.guild,
                                   channel=message.channel)
        if tourney is None:
            return

        if message.content == '!bracket':
            await message.channel.send(tourney.gar.get_url())
        # If someone posts a netplay code for their opponent, mark their
        # match as underway.
        elif (len(message.mentions) == 1 and
              re.search(r'\b[a-f0-9]{8}\b', message.content)):
            await tourney.mark_match_underway(
                    message.mentions[0], message.author)


if __name__ == '__main__':
    TOKEN = os.environ.get('DISCORD_TOKEN')

    if TOKEN is None:
        raise RuntimeError('DISCORD_TOKEN is unset')

    bot = commands.Bot(command_prefix='/', description='Talk to the TO')
    bot.add_cog(TOCommands(bot))
    bot.run(TOKEN)
