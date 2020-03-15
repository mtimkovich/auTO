import aiohttp
import discord
from discord.ext import tasks, commands
import os
import re

import challonge

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
        # TODO: DM users with help text.
        await ctx.send('¯\_(ツ)_/¯')

    @auTO.command(brief='Challonge URL of tournament')
    async def start(self, ctx, url: str):
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

        if self.gar.get_state() != 'underway':
            await ctx.send("Tournament hasn't started yet.")
            return

        self.started = True
        start_msg = await ctx.send('Starting {}! {}'.format(
            self.gar.get_name(), self.gar.get_url()))
        await start_msg.pin()
        await self.matches(ctx)

    @auTO.command()
    async def stop(self, ctx):
        self.started = False
        self.gar.reset()
        await ctx.send('Goodbye')

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
            match = '{}: {} vs {}'.format(m['round'],
                                              self.mention_user(m['player1']),
                                              self.mention_user(m['player2']))
            if m['underway']:
                match += ' (Playing)'
            announcement.append(match)

        await ctx.send('\n'.join(announcement))

    def find_match(self, username):
        for match in self.open_matches:
            if username in [match['player1'], match['player2']]:
                return match
        else:
            return None

    @auTO.command(brief='Report match results')
    async def report(self, ctx, scores_csv: str):
        if not self.started:
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

        match = self.find_match(username)
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.started:
            return

        if message.content == '!bracket':
            await message.channel.send(self.gar.get_url())
        # If someone posts a netplay code for their opponent, mark their
        # match as underway.
        elif (len(message.mentions) == 1 and
              re.search(r'\b[a-f0-9]{8}\b', message.content)):
            await self.mark_match_underway(message.mentions[0], message.author)

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        # TODO: Map Challonge usernames to Discord usernames.
        # TODO: This should only check the current guild.
        for member in self.bot.get_all_members():
            if member.display_name == username:
                return member.mention
        return '@{}'.format(username)

if __name__ == '__main__':
    TOKEN = os.environ.get('DISCORD_TOKEN')

    if TOKEN is None:
        raise RuntimeError('DISCORD_TOKEN is unset')

    # TODO: Ask user for Challonge key.
    # TODO: Make it so only users with correct permissions can start a
    # tournament.
    # TODO: Work across multiple guilds.

    bot = commands.Bot(command_prefix='/', description='Talk to the TO')
    bot.add_cog(TOCommands(bot))
    bot.run(TOKEN)
