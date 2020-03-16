import aiohttp
import discord
from discord.ext import commands
import os
import re

import challonge

class Tournament(object):
    """Tournaments are unique to a guild + channel."""
    def __init__(self, ctx, tournament_id, owner, session):
        self.guild = ctx.guild
        self.owner = owner
        self.open_matches = []
        # TODO: Should ask user for their Challonge key.
        self.challonge_key = os.environ.get('CHALLONGE_KEY')
        self.gar = challonge.Challonge(
                self.challonge_key, tournament_id, session)

    async def get_open_matches(self):
        self.open_matches = await self.gar.get_open_matches()

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
        # TODO: Map Challonge usernames to Discord usernames.
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

    def tourney_start(self, ctx, tournament_id, owner):
        tourney = Tournament(ctx, tournament_id, owner, self.session)
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
        # TODO: DM users with help text.
        await ctx.send(r'¯\_(ツ)_/¯')

    @auTO.command(brief='Challonge URL of tournament')
    async def start(self, ctx, url: str):
        """Sets tournament URL and start calling matches."""
        if self.get_tourney(ctx) is not None:
            await ctx.send('Tournament is already in progress')
            return

        try:
            tournament_id = challonge.extract_id(url)
        except ValueError as e:
            await ctx.send(e)
            return

        await ctx.trigger_typing()
        tourney = self.tourney_start(ctx, tournament_id, ctx.author)
        await tourney.gar.get_raw()

        if tourney.gar.get_state() != 'underway':
            await ctx.send("Tournament hasn't been started yet.")
            return

        start_msg = await ctx.send('Starting {}! {}'.format(
            tourney.gar.get_name(), tourney.gar.get_url()))
        await start_msg.pin()
        await self.matches(ctx)

    @auTO.command()
    async def stop(self, ctx):
        self.tourney_stop(ctx)
        await ctx.send('Goodbye')

    async def end_tournament(self, ctx):
        # TODO: Print the top 3.
        self.tourney_stop(ctx)
        await ctx.send('End of tournament. Thanks for coming!')

    @auTO.command()
    async def matches(self, ctx):
        """Checks for match updates and prints matches to the channel."""
        tourney = self.get_tourney(ctx)
        if tourney is None:
            await ctx.send('Tournament not started')
            return

        await ctx.trigger_typing()
        await tourney.get_open_matches()

        if not tourney.open_matches:
            await self.end_tournament(ctx)
            return

        announcement = []
        for m in tourney.open_matches:
            match = '**{}**: {} vs {}'.format(
                    m['round'], tourney.mention_user(m['player1']),
                    tourney.mention_user(m['player2']))
            if m['underway']:
                match += ' (Playing)'
            announcement.append(match)

        await ctx.send('\n'.join(announcement))

    @auTO.command(brief='Report match results')
    async def report(self, ctx, scores_csv: str):
        tourney = self.get_tourney(ctx)
        if tourney is None:
            return

        if not re.match('\d-\d', scores_csv):
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
        # TODO: This assumes the Challonge and Discord usernames are the same.
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
        print('>>> auTO has connected to Discord')

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)


    @commands.Cog.listener()
    async def on_message(self, message):
        tourney = self.get_tourney(guild=message.guild, channel=message.channel)
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

    # TODO: Make it so only users with correct permissions can start a
    # tournament.

    bot = commands.Bot(command_prefix='/', description='Talk to the TO')
    bot.add_cog(TOCommands(bot))
    bot.run(TOKEN)
