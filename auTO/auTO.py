import aiohttp
from aiohttp.client_exceptions import ClientResponseError
import asyncio
import discord
from discord.ext import commands
import functools
import logging
import re
from typing import Optional
import yaml

from . import challonge
from . config import config
from . import utils
from . tournament import Tournament

logging.basicConfig(level=logging.INFO)


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

    def tourney_start(self, ctx, tournament_id, api_key):
        tourney = Tournament(ctx, tournament_id, api_key, self.session)
        self.tournament_map[Tournament.key(ctx)] = tourney
        return tourney

    def tourney_stop(self, ctx=None, guild=None, channel=None):
        if ctx is None:
            key = (guild, channel)
        else:
            key = Tournament.key(ctx)
        self.tournament_map.pop(key, None)

    @commands.group(case_insensitive=True)
    async def auTO(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Use `!auto help` for options')

    @auTO.command()
    async def help(self, ctx):
        help_list = [
            '- `start [URL]` - start TOing',
            '- `stop` - stop TOing',
            '- `rename tag @Player` - Rename player to their Discord tag',
            '- `noshow @Player` - Start DQ process for player',
            '- `update_tags` - get the latest Challonge tags',
            '- `report 0-2` - report a match',
            '- `matches` - print the active matches',
            '- `status` - show how far along the tournament is',
            '- `bracket` - print the bracket URL',
        ]
        await utils.send_list(ctx, help_list)

    def has_tourney(func):
        """Decorator that returns if no tourney is set."""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            ctx = args[0]
            tourney = self.get_tourney(ctx)
            if tourney is None:
                await ctx.send('No tournament running')
                return
            kwargs['tourney'] = tourney
            return await func(self, *args, **kwargs)
        return wrapper

    def is_to(func):
        """Decorator that ensures caller is owner, TO, or admin."""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            ctx = args[0]
            user = ctx.author
            tourney = kwargs['tourney']
            if not (user == tourney.owner or
                    tourney.channel.permissions_for(user).administrator or
                    any(role.name == 'TO' for role in user.roles)):
                await ctx.send('Only a TO can run this command.')
                return
            return await func(self, *args, **kwargs)
        return wrapper

    @auTO.command()
    @has_tourney
    @is_to
    async def update_tags(self, ctx, *, tourney=None):
        await tourney.gar.get_raw()

    @auTO.command()
    @has_tourney
    @is_to
    async def rename(self, ctx, challonge_tag: str, member: discord.Member,
                     *, tourney=None):
        await ctx.trigger_typing()
        try:
            await tourney.gar.rename(challonge_tag, member.display_name)
        except ValueError as e:
            await ctx.send(e)
            return
        await ctx.send('Renamed {} to {}'.format(
                       challonge_tag, member.display_name))

    @auTO.command()
    @has_tourney
    async def status(self, ctx, *, tourney=None):
        await ctx.trigger_typing()
        await ctx.send('Tournament is {}% completed.'
                       .format(await tourney.gar.progress_meter()))

    def is_dm_response(self, owner):
        return lambda m: m.channel == owner.dm_channel and m.author == owner

    async def ask_for_challonge_key(self,
                                    owner: discord.Member) -> Optional[str]:
        """DM the TO for their Challonge key."""
        await owner.send("Hey there! To run this tournament for you, I'll "
                         "need your Challonge API key "
                         "(https://challonge.com/settings/developer). "
                         "The key is only used to run the bracket and is "
                         "deleted after the tournament finishes.")
        await owner.send("If that's ok with you, respond to this message with "
                         "your Challonge API key, otherwise, with 'NO'.")

        while True:
            msg = await self.bot.wait_for(
                    'message', check=self.is_dm_response(owner))

            content = msg.content.strip()
            if utils.istrcmp(content, 'no'):
                await owner.send('👍')
                return None
            elif re.match(r'[a-z0-9]+$', content, re.I):
                return content
            else:
                await owner.send('Invalid API key, try again.')

    async def confirm(self, user, question) -> bool:
        """DM the user a yes/no question."""
        await user.send('{} [Y/n]'.format(question))
        msg = await self.bot.wait_for(
                'message', check=self.is_dm_response(user))

        return msg.content.strip().lower() in ['y', 'yes']

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

        # Useful for debugging.
        api_key = config.get('CHALLONGE_KEY')
        if api_key is None:
            api_key = await self.ask_for_challonge_key(ctx.author)
            if api_key is None:
                return

        tourney = self.tourney_start(ctx, tournament_id, api_key)
        try:
            await tourney.gar.get_raw()
        except ClientResponseError as e:
            if e.code == 401:
                await ctx.author.dm_channel.send('Invalid API Key')
                self.tourney_stop(ctx)
                return
            elif e.code == 404:
                await ctx.send(
                        'Invalid tournament URL or invalid permissions.')
                self.tourney_stop(ctx)
                return
            else:
                raise e

        if tourney.gar.get_state() == 'pending':
            await ctx.send('Click "Start the Tournament" on Challonge.')
            self.tourney_stop(ctx)
            return
        elif tourney.gar.get_state() == 'ended':
            await ctx.send("Tournament has already finished.")
            self.tourney_stop(ctx)
            return

        has_missing = await tourney.missing_tags(ctx.author)
        if has_missing:
            confirm = await self.confirm(ctx.author, 'Continue anyway?')
            if confirm:
                await self.update_tags(ctx)
            else:
                self.tourney_stop(ctx)
                return

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

        await ctx.trigger_typing()
        logging.info('Starting tournament {} on {}'.format(
            tourney.gar.get_name(), tourney.guild.name))
        start_msg = await ctx.send('Starting {}! {}'.format(
            tourney.gar.get_name(), tourney.gar.get_url()))
        await start_msg.pin()
        await self.matches(ctx)

    @auTO.command()
    @has_tourney
    @is_to
    async def stop(self, ctx, *, tourney=None):
        self.tourney_stop(ctx)
        await self.bot.change_presence()
        await ctx.send('Goodbye 😞')

    async def end_tournament(self, ctx, tourney):
        confirm = await self.confirm(
                tourney.owner, '{} is completed. Finalize?'
                .format(tourney.gar.get_name()))
        if not confirm:
            return

        try:
            await tourney.gar.finalize()
        except ClientResponseError as e:
            if e.code != 422:
                raise e
        await self.print_results(tourney)

    @auTO.command()
    @has_tourney
    @is_to
    async def results(self, ctx, *, tourney=None):
        await self.print_results(tourney)

    async def print_results(self, tourney):
        """Print the results thread."""
        top8 = await tourney.gar.get_top8()
        if top8 is None:
            return

        winner = tourney.mention_user(top8[0][1][0])
        message = [
            'Congrats to the winner of {}: **{}**!!'.format(
                tourney.gar.get_name(), winner),
            'We had {} entrants!\n'.format(len(tourney.gar.get_players())),
        ]

        for i, players in top8:
            players = ' / '.join(map(tourney.mention_user, players))
            message.append('{}. {}'.format(i, players))

        await utils.send_list(tourney.channel, message)
        self.tourney_stop(guild=tourney.guild, channel=tourney.channel)
        await self.bot.change_presence()

    @auTO.command()
    @has_tourney
    async def matches(self, ctx, *, tourney=None):
        """Checks for match updates and prints matches to the channel."""
        await ctx.trigger_typing()
        await tourney.get_open_matches()

        if not tourney.open_matches:
            await self.end_tournament(ctx, tourney)
            return

        announcement = []
        for m in sorted(tourney.open_matches,
                        key=lambda m: m['suggested_play_order']):
            player1 = m['player1']
            player2 = m['player2']

            # We want to only ping players the first time their match is
            # called.
            if m['id'] not in tourney.called_matches:
                player1 = tourney.mention_user(player1)
                player2 = tourney.mention_user(player2)
                tourney.called_matches.add(m['id'])

            match = '**{}**: {} vs {}'.format(m['round'], player1, player2)
            if m['underway']:
                match += ' (Playing)'
            announcement.append(match)

        msgs = await utils.send_list(ctx, announcement)
        if tourney.previous_match_msgs is not None:
            for msg in tourney.previous_match_msgs:
                await msg.delete()
        tourney.previous_match_msgs = msgs

    @auTO.command(brief='Report match results')
    @has_tourney
    async def report(self, ctx, scores_csv: str, *, tourney=None,
                     username=None):
        score_match = re.match(r'(-?\d+)-(-?\d+)', scores_csv)
        if not score_match:
            await ctx.send('Invalid report. Should be `!auto report 0-2`')
            return

        scores = list(map(int, score_match.groups()))

        if scores[0] > scores[1]:
            player1_win = True
        elif scores[0] < scores[1]:
            player1_win = False
        else:
            await ctx.send('No ties allowed.')
            return

        match_id = None
        winner_id = None

        if username is None:
            username = ctx.author.display_name

        if username.lower() in tourney.recently_called:
            await ctx.send('Ignoring potentially duplicate report. Try again '
                           'in a couple seconds if this is incorrect.')
            return

        match = tourney.find_match(username)
        if match is None:
            await ctx.send('{} not found in current matches'.format(username))
            return

        match_id = match['id']
        if utils.istrcmp(username, match['player2']):
            # Scores are reported with player1's score first.
            scores_csv = '{1}-{0}'.format(*scores)
            player1_win = not player1_win

        if player1_win:
            winner_id = match['player1_id']
        else:
            winner_id = match['player2_id']

        await ctx.trigger_typing()
        await tourney.report_match(match, winner_id, username, scores_csv)
        await self.matches(ctx)

    @auTO.command()
    @has_tourney
    async def bracket(self, ctx, *, tourney=None):
        await ctx.trigger_typing()
        await ctx.send(tourney.gar.get_url())

    @auTO.command()
    @has_tourney
    @is_to
    async def noshow(self, ctx, user: discord.Member, *, tourney=None):
        await ctx.trigger_typing()
        match = tourney.find_match(user.display_name)
        if match is None:
            await ctx.send('{} does not have a match to be DQed from.'
                           .format(user.display_name))
            return

        await ctx.send('{}: message in the chat and start playing your match '
                       'within 5 minutes or you will be DQed.'
                       .format(user.mention))
        try:
            FIVE_MINUTES = 5 * 60
            await self.bot.wait_for(
                    'message', check=lambda m: m.author == user,
                    timeout=FIVE_MINUTES)
        except asyncio.TimeoutError:
            msg = await ctx.send('{} has been DQed'.format(user.mention))
            await msg.add_reaction('🇫')
            await tourney.gar.dq(user.display_name)
            await self.matches(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if isinstance(err, commands.CommandNotFound):
            # These are useless and clutter the log.
            return
        elif isinstance(err, ClientResponseError):
            if err.code == 401:
                await ctx.send('Invalid API key.')
            else:
                await ctx.send('Error connecting to Challonge 💀')
            return
        elif isinstance(err, commands.errors.BadArgument):
            await ctx.send(err)
            return
        elif not isinstance(err, commands.MissingRequiredArgument):
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


def main():
    bot = commands.Bot(command_prefix='!', description='Talk to the TO',
                       case_insensitive=True)
    bot.add_cog(TOCommands(bot))
    bot.run(config.get('DISCORD_TOKEN'))


if __name__ == '__main__':
    main()
