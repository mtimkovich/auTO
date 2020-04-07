import aiohttp
from aiohttp.client_exceptions import ClientResponseError
import asyncio
import discord
from discord.ext import commands
import functools
import logging
import os
import pickle
import re
from typing import Optional

from . import challonge
from .config import config
from .match import Match
from .tournament import Tournament, TournamentPickle, FakeContext
from . import utils

logging.basicConfig(level=logging.INFO)

PICKLE_FILE = 'auTO.pickle'


class TOCommands(commands.Cog):
    def __init__(self, bot, saved):
        self.bot = bot
        self.saved = saved
        self.tournament_map = {}
        self.session = aiohttp.ClientSession(raise_for_status=True)

    def save(self):
        if not self.tournament_map:
            return
        tournament_pickle = {}
        for tourney in self.tournament_map.values():
            tournament_pickle[tourney.guild.id] = TournamentPickle(tourney)
        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(tournament_pickle, f)
        logging.info('Saved active tournaments.')

    async def close(self):
        self.save()
        await self.session.close()

    def tourney_start(self, ctx, tournament_id, api_key):
        tourney = Tournament(ctx, tournament_id, api_key, self.session)
        self.tournament_map[ctx.guild] = tourney
        return tourney

    async def tourney_stop(self, guild):
        tourney = self.tournament_map.pop(guild, None)
        if tourney is not None:
            await tourney.delete_matches_category()

    @commands.group(case_insensitive=True)
    async def auTO(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Use `!auTO help` for options')

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
            '- `status` - print how far along the tournament is',
            '- `bracket` - print the bracket URL',
        ]
        await utils.send_list(ctx, help_list)

    def has_tourney(func):
        """Decorator that returns if no tourney is set."""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            ctx = args[0]
            tourney = self.tournament_map.get(ctx.guild)
            if tourney is None:
                await ctx.send('No tournament running.')
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
        if self.tournament_map.get(ctx.guild) is not None:
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
                await self.tourney_stop(ctx.guild)
                return
            elif e.code == 404:
                await ctx.send(
                        'Invalid tournament URL.')
                await self.tourney_stop(ctx.guild)
                return
            else:
                raise e

        if tourney.gar.get_state() == 'pending':
            try:
                await tourney.gar.start()
            except ClientResponseError as e:
                if e.code == 422:
                    await ctx.send('Tournament needs at least 2 players.')
                else:
                    await self.tourney_stop(ctx.guild)
                    logging.warning(e)
                    return
        elif tourney.gar.get_state() == 'ended':
            await ctx.send("Tournament has already finished.")
            await self.tourney_stop(ctx.guild)
            return

        has_missing = await tourney.missing_tags(ctx.author)
        if has_missing:
            confirm = await self.confirm(ctx.author, 'Continue anyway?')
            if confirm:
                await self.update_tags(ctx)
            else:
                await self.tourney_stop(ctx.guild)
                return

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

        await tourney.channel.trigger_typing()
        logging.info('Starting tournament {} on {}'.format(
            tourney.gar.get_name(), tourney.guild.name))
        start_msg = await ctx.send(
                'Starting {}! Please stop your friendlies. {}'
                .format(tourney.gar.get_name(), tourney.gar.get_url()))
        try:
            await start_msg.pin()
        except discord.errors.HttpException as e:
            logging.warning(e)
        await self.matches(ctx)

    @auTO.command()
    @has_tourney
    @is_to
    async def stop(self, ctx, *, tourney=None):
        await self.tourney_stop(ctx.guild)
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
        await self.tourney_stop(tourney.guild)
        await self.bot.change_presence()

    @auTO.command()
    @has_tourney
    async def matches(self, ctx, *, tourney=None):
        """Checks for match updates and prints matches to the channel."""
        await tourney.channel.trigger_typing()
        await tourney.get_open_matches()

        if not tourney.open_matches:
            await tourney.clean_up_channels()
            await tourney.channel.send('Tournament has finished!')
            await self.end_tournament(ctx, tourney)
            return

        await tourney.clean_up_channels()

        announcement = []
        create_channels = []
        for m in sorted(tourney.open_matches,
                        key=lambda m: m['suggested_play_order']):
            player1 = m['player1']
            player2 = m['player2']

            # We want to only ping players the first time their match is
            # called.
            if m['id'] not in tourney.called_matches:
                match = Match(tourney, player1, player2)
                tourney.called_matches[m['id']] = match
                create_channels.append(match.create_channels())

            match = tourney.called_matches[m['id']]
            round = '**{}**: '.format(m['round'])
            if match.first:
                players = match.name(True)
                match.first = False
            else:
                players = match.name()

            if m['underway']:
                players = '*{}*'.format(players)
            announcement.append(round + players)

        aws = await asyncio.gather(
            utils.send_list(tourney.channel, announcement),
            *create_channels
        )

        await asyncio.gather(
                *(msg.delete() for msg in tourney.previous_match_msgs))
        tourney.previous_match_msgs = aws[0]

    @auTO.command(brief='Report match results')
    @has_tourney
    async def report(self, ctx, scores_csv: str, *, tourney=None,
                     username=None):
        await ctx.trigger_typing()
        score_match = re.match(r'(-?\d+)-(-?\d+)', scores_csv)
        if not score_match:
            await ctx.send('Invalid report. Should be `!auTO report 0-2`')
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

        if tourney.is_duplicate_report(username):
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
        await tourney.channel.trigger_typing()
        match = tourney.find_match(user.display_name)
        if match is None:
            await tourney.channel.send(
                    '{} does not have a match to be DQed from.'
                    .format(user.display_name))
            return

        await tourney.channel.send(
                '{}: message in the chat and start playing your match within '
                '5 minutes or you will be DQed.'.format(user.mention))
        try:
            FIVE_MINUTES = 5 * 60
            await self.bot.wait_for(
                    'message', check=lambda m: m.author == user,
                    timeout=FIVE_MINUTES)
        except asyncio.TimeoutError:
            msg = await tourney.channel.send(
                    '{} has been DQed'.format(user.mention))
            if tourney.permissions().add_reactions:
                await msg.add_reaction('🇫')
            await tourney.gar.dq(user.display_name)
            await self.matches(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if isinstance(err, commands.CommandNotFound):
            # These are useless and clutter the log.
            return
        elif (isinstance(err, commands.errors.CommandInvokeError) and
                isinstance(err.original, ClientResponseError)):
            if err.original.code == 401:
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

    async def load(self):
        if not self.saved:
            return
        for guild in self.bot.guilds:
            saved = self.saved.get(guild.id)
            if not saved:
                continue
            try:
                ctx = FakeContext(guild, saved)
            except ValueError as e:
                logging.warning(e)
                continue
            tourney = self.tourney_start(
                    ctx, saved.tournament_id, saved.api_key)
            await tourney.gar.get_raw()
        logging.info('Loaded saved tournaments.')

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info('auTO has connected to Discord.')
        await self.load()

    @commands.Cog.listener()
    async def on_message(self, message):
        tourney = self.tournament_map.get(message.guild)
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


class Bot(commands.Bot):
    async def close(self):
        await self.get_cog('TOCommands').close()
        await super().close()


def load_tournaments():
    saved = {}
    try:
        with open(PICKLE_FILE, 'rb') as f:
            saved = pickle.load(f)
    except OSError:
        pass
    except Exception as e:
        logging.warning('Error unpickling: {}'.format(e))

    try:
        os.remove(PICKLE_FILE)
    except OSError:
        pass

    return saved


def main():
    saved = load_tournaments()
    bot = Bot(command_prefix='!', description='Talk to the TO',
              case_insensitive=True)
    bot.add_cog(TOCommands(bot, saved))
    bot.run(config.get('DISCORD_TOKEN'))


if __name__ == '__main__':
    main()
