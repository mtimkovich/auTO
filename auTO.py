import aiohttp
import discord
from discord.ext import tasks, commands
import logging
import os

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

    @auTO.command()
    async def matches(self, ctx):
        """Checks for match updates and prints matches to the channel."""
        if not self.started:
            await ctx.send('tournament not started')
            return

        await ctx.trigger_typing()
        self.open_matches = await self.gar.get_open_matches()
        announcement = []
        for m in self.open_matches:
            match = '**{}**: {} vs {}'.format(m['round'],
                                              self.mention_user(m['player1']),
                                              self.mention_user(m['player2']))
            announcement.append(match)

        await ctx.send('\n'.join(announcement))

    @auTO.command()
    async def report(self, ctx, scores_csv):
        if not self.started:
            return

        await ctx.trigger_typing()
        """TODO:
        1. Validate scores_csv
        2. Determine is reporting user is player1 or player2
        3. Get winner_id
        4. Make API call.
        """

        if not re.match('\d-\d'):
            await ctx.send('Invalid report. Should be `report your-score-opponent-score`')
            return

        scores = [int(n) for n in scores_csv.split('-')]

        if scores[0] > scores[1]:
            pass
        elif scores[0] < scores[1]:
            pass
        else:
            await ctx.send('No ties allowed')
            return

        for match in self.open_matches:
            # TODO: Find the player's match and who is player1.
            if ctx.author.display_name == match['player1']:
                pass

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
