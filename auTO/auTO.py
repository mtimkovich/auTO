import asyncio
import functools
import logging
import os
import pickle
import re
import sys
from typing import Optional

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
import discord
from discord.ext import commands

from . import challonge
from .config import config, DEBUG
from .help import help
from .match import Match
from .tournament import Tournament, TournamentPickle, FakeContext
from . import utils

PICKLE_FILE = 'auTO.pickle'
log = logging.getLogger(__name__)

netplay_code = re.compile(r'\b[a-f0-9]{8}\b')


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


class ChallongeError(Exception):
    """Error code in Challonge response."""


class auTO(commands.Cog):
    def __init__(self, bot, saved):
        self.bot = bot
        self.saved = saved
        self.tournament_map = {}
        self.session = aiohttp.ClientSession(raise_for_status=True)

    def _save(self):
        if not self.tournament_map:
            return
        tournament_pickle = {}
        for tourney in self.tournament_map.values():
            tp = TournamentPickle(tourney)
            for id, m in tourney.called_matches.items():
                try:
                    tp.matches[id] = m.pickle()
                except AttributeError:
                    continue

            tournament_pickle[tourney.guild.id] = tp

        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(tournament_pickle, f)
        log.info('Saved active tournaments.')

    async def close(self):
        self._save()
        await self.session.close()

    def _tourney_start(self, ctx, tournament_id, api_key):
        tourney = Tournament(ctx, tournament_id, api_key, self.session)
        self.tournament_map[ctx.guild] = tourney
        return tourney

    async def _tourney_stop(self, guild):
        tourney = self.tournament_map.pop(guild, None)
        if tourney is not None:
            await tourney.delete_matches_category()

    @commands.command(**help['update_tags'])
    @has_tourney
    @is_to
    # pylint: disable=unused-argument
    async def update_tags(self, ctx, *, tourney=None):
        await tourney.gar.get_raw()

    @commands.command(**help['rename'])
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

        match = tourney.find_match(challonge_tag)
        match.update_player(challonge_tag, member)

        await ctx.send(f'Renamed {challonge_tag} to {member.display_name}.')

    @commands.command(**help['status'])
    @has_tourney
    async def status(self, ctx, *, tourney=None):
        await ctx.trigger_typing()
        status = await tourney.gar.progress_meter()
        await ctx.send(f'Tournament is {status}% completed.')

    def _is_dm_response(self, owner):
        return lambda m: m.channel == owner.dm_channel and m.author == owner

    async def _ask_for_challonge_key(self,
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
                'message', check=self._is_dm_response(owner))

            content = msg.content.strip()
            if utils.istrcmp(content, 'no'):
                await owner.send('👍')
                return None
            if re.match(r'[a-z0-9]+$', content, re.I):
                return content
            await owner.send('Invalid API key, try again.')

    async def _confirm(self, user, question) -> bool:
        """DM the user a yes/no question."""
        await user.send(f'{question} [Y/n]')
        msg = await self.bot.wait_for(
            'message', check=self._is_dm_response(user))

        return msg.content.strip().lower() in ['y', 'yes']

    async def _invalid_state(self, ctx, tourney) -> bool:
        if tourney.gar.get_state() == 'pending':
            try:
                await tourney.gar.start()
            except ClientResponseError as e:
                if e.code == 422:
                    await ctx.send('Tournament needs at least 2 players.')
                else:
                    log.warning(e)
                return True
        elif tourney.gar.get_state() == 'ended':
            await ctx.send("Tournament has already finished.")
            return True
        return False

    async def _create_tournament(self, ctx, url: str) -> Optional:
        tournament_id = challonge.extract_id(url)

        key_error = ChallongeError('Invalid API Key')

        # Useful for debugging.
        if DEBUG:
            api_key = config.get('CHALLONGE_KEY')
        else:
            api_key = await self._ask_for_challonge_key(ctx.author)
            if api_key is None:
                raise key_error

        tourney = self._tourney_start(ctx, tournament_id, api_key)

        try:
            await tourney.gar.get_raw()
        except ClientResponseError as e:
            if e.code == 401:
                await ctx.author.dm_channel.send('Invalid API Key')
                raise ChallongeError
            if e.code == 404:
                raise ChallongeError('Invalid tournament URL.')
            raise e

        if await self._invalid_state(ctx, tourney):
            raise ChallongeError('Invalid tournament state.')

        has_missing = await tourney.missing_tags(ctx.author)
        if has_missing:
            confirm = await self._confirm(ctx.author, 'Continue anyway?')
            if not confirm:
                raise ValueError
            await self.update_tags(ctx)
        return tourney

    @commands.command(**help['start'])
    async def start(self, ctx, url: str):
        if self.tournament_map.get(ctx.guild) is not None:
            await ctx.send('A tournament is already in progress')
            return

        try:
            tourney = await self._create_tournament(ctx, url)
        except (ValueError, ChallongeError, ClientResponseError) as e:
            tourney = None
            if str(e):
                await ctx.send(e)
        if tourney is None:
            await self._tourney_stop(ctx.guild)
            return

        activity = discord.Activity(name='Dolphin',
                                    type=discord.ActivityType.watching)
        await asyncio.gather(
            self.bot.change_presence(activity=activity),
            tourney.channel.trigger_typing()
        )

        name = await tourney.gar.get_name()
        url = await tourney.gar.get_url()

        log.info(f'Starting tournament {name} ({url}) on '
                 f'{tourney.guild.name}.')
        start_msg = await ctx.send(
            f'Starting {name}! Please stop your friendlies. {url}')
        try:
            await start_msg.pin()
        except discord.HTTPException as e:
            log.warning(e)
        await self.matches(ctx)

    @commands.command(**help['stop'])
    @has_tourney
    @is_to
    # pylint: disable=unused-argument
    async def stop(self, ctx, *, tourney=None):
        await asyncio.gather(
            self._tourney_stop(ctx.guild),
            self.bot.change_presence(),
            ctx.send('Goodbye 😞')
        )

    async def _end_tournament(self, tourney):
        name = await tourney.gar.get_name()
        confirm = await self._confirm(
            tourney.owner, f'{name} is completed. Finalize?')
        if not confirm:
            return

        try:
            await tourney.gar.finalize()
        except ClientResponseError as e:
            if e.code != 422:
                raise e
        await self._print_results(tourney)

    @commands.command(**help['results'])
    @has_tourney
    @is_to
    # pylint: disable=unused-argument
    async def results(self, ctx, *, tourney=None):
        await self._print_results(tourney)

    async def _print_results(self, tourney):
        """Print the results thread."""
        top8 = await tourney.gar.get_top8()
        if top8 is None:
            return

        winner = tourney.mention_user(top8[0][1][0])
        name = await tourney.gar.get_name()
        num_players = len(await tourney.gar.get_players())
        message = [
            f'Congrats to the winner of {name}: **{winner}**!!',
            f'We had {num_players} entrants!\n',
        ]

        for i, players in top8:
            players = ' / '.join(map(tourney.mention_user, players))
            message.append(f'{i}. {players}')

        await asyncio.gather(
            utils.send_list(tourney.channel, message),
            self._tourney_stop(tourney.guild),
            self.bot.change_presence(),
        )

    @commands.command(**help['matches'])
    @has_tourney
    # pylint: disable=unused-argument
    async def matches(self, ctx, *, tourney=None):
        await tourney.channel.trigger_typing()
        await asyncio.wait_for(self._load(), 2)
        open_matches = await tourney.get_open_matches()

        if not open_matches:
            await tourney.clean_up_channels(open_matches)
            await tourney.channel.send('Tournament has finished!')
            await self._end_tournament(tourney)
            return

        await tourney.create_matches_category()
        await tourney.clean_up_channels(open_matches)

        announcement = []
        create_channels = []
        for m in sorted(open_matches,
                        key=lambda m: m['suggested_play_order']):
            if m['id'] not in tourney.called_matches:
                match = Match(tourney, m)
                tourney.called_matches[m['id']] = match

            match = tourney.called_matches[m['id']]
            if not match.channels:
                create_channels.append(match.create_channels())

            round = f"**{m['round']}**: "
            # We want to only ping players the first time their match is
            # called.
            if match.first:
                players = match.name(True)
                match.first = False
            else:
                players = match.name()

            if m['underway']:
                players = f'*{players}*'
            announcement.append(round + players)

        aws = await asyncio.gather(
            utils.send_list(tourney.channel, announcement),
            *create_channels
        )

        await asyncio.gather(
            *(msg.delete() for msg in tourney.previous_match_msgs))
        tourney.previous_match_msgs = aws[0]

    @commands.command(**help['report'])
    @has_tourney
    async def report(self, ctx, scores_csv: str, *, tourney=None,
                     username=None):
        await ctx.trigger_typing()
        score_match = re.match(r'(-?\d+)-(-?\d+)', scores_csv)
        if not score_match:
            await ctx.send('Invalid report. Should be `@auTO report 0-2`')
            return

        scores = list(map(int, score_match.groups()))

        if scores[0] > scores[1]:
            player1_win = True
        elif scores[0] < scores[1]:
            player1_win = False
        else:
            await ctx.send('No ties allowed.')
            return

        winner_id = None

        if username is None:
            username = ctx.author.display_name

        if tourney.is_duplicate_report(username):
            await ctx.send('Ignoring potentially duplicate report. Try again '
                           'in a couple seconds if this is incorrect.')
            return

        match = tourney.find_match(username)
        if match is None:
            await ctx.send(f'{username} not found in current matches.')
            return

        if utils.istrcmp(username, match.player2_tag):
            # Scores are reported with player1's score first.
            scores_csv = '{1}-{0}'.format(*scores)
            player1_win = not player1_win

        if player1_win:
            winner_id = match.player1_id
        else:
            winner_id = match.player2_id

        await tourney.report_match(match, winner_id, username, scores_csv)
        await self.matches(ctx)

    @commands.command(**help['bracket'])
    @has_tourney
    async def bracket(self, ctx, *, tourney=None):
        await ctx.trigger_typing()
        await ctx.send(await tourney.gar.get_url())

    @commands.command(**help['noshow'])
    @has_tourney
    @is_to
    async def noshow(self, ctx, user: discord.Member, *, tourney=None):
        await tourney.channel.trigger_typing()
        match = tourney.find_match(user.display_name)
        if match is None:
            await tourney.channel.send(f'{user.display_name} does not have a '
                                       'match to be DQed from.')
            return

        await tourney.channel.send(
            f'{user.mention}: message in the chat and start playing your '
            'match within 5 minutes or you will be DQed.')
        try:
            FIVE_MINUTES = 5 * 60
            await self.bot.wait_for(
                'message', check=lambda m: m.author == user,
                timeout=FIVE_MINUTES)
        except asyncio.TimeoutError:
            msg = await tourney.channel.send(f'{user.mention} has been DQed')
            try:
                await msg.add_reaction('🇫')
            except discord.DiscordException as e:
                log.warning(e)
            await tourney.gar.dq(user.display_name)
            await self.matches(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if isinstance(err, commands.CommandNotFound):
            # Reporting shorthand.
            msg = ctx.message.content.split()
            if len(msg) == 2 and re.match(r'\d', msg[1]):
                await self.report(ctx, msg[1])
            else:
                await ctx.send('Type `@auTO help` for options.')
            return
        if (isinstance(err, commands.errors.CommandInvokeError) and
                isinstance(err.original, ClientResponseError)):
            if err.original.code == 401:
                await ctx.send('Invalid API key.')
            else:
                await ctx.send('Error connecting to Challonge 💀')
            return
        if isinstance(err, (commands.MissingRequiredArgument,
                            commands.errors.BadArgument)):
            self.bot.help_command.context = ctx
            await self.bot.help_command.send_command_help(ctx.command)
            return
        raise err

    async def _load(self):
        if not self.saved:
            return
        for guild in self.bot.guilds:
            saved = self.saved.get(guild.id)
            if not saved:
                continue
            try:
                ctx = FakeContext(guild, saved)
            except ValueError as e:
                log.warning(e)
                continue
            tourney = self._tourney_start(
                ctx, saved.tournament_id, saved.api_key)
            if saved.category_id:
                tourney.category = ctx.guild.get_channel(saved.category_id)
            for id, mp in saved.matches.items():
                match = mp.unpickle(tourney)
                tourney.called_matches[id] = match
        log.info('Loaded saved tournaments.')
        self.saved = {}

    @commands.Cog.listener()
    async def on_ready(self):
        log.info('auTO has connected to Discord.')
        await self._load()

    async def _has_netplay_code(self, tourney, message):
        """Mark matches underway when a netplay code is posted."""
        if not netplay_code.search(message.content):
            return
        if len(message.mentions) == 1:
            await tourney.mark_match_underway(
                message.author, message.mentions[0])
        elif (tourney.category and
              message.channel in tourney.category.text_channels):
            await tourney.mark_match_underway(message.author)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        bot_id = self.bot.user.id
        if re.match(rf'\s*<@!?{bot_id}>\s*$', message.content):
            ctx = await self.bot.get_context(message)
            ctx.prefix = '@auTO '
            self.bot.help_command.context = ctx
            mapping = self.bot.help_command.get_bot_mapping()
            await self.bot.help_command.send_bot_help(mapping)
            return

        bot_role = utils.get_role(message.guild, self.bot.user.name)
        if bot_role is not None:
            role_pattern = re.compile(rf'\s*<@&{bot_role.id}>')
            if role_pattern.match(message.content):
                message.content = role_pattern.sub('!auTO', message.content)
                await self.bot.process_commands(message)
                return

        tourney = self.tournament_map.get(message.guild)
        if tourney is None:
            return
        if message.content == '!bracket':
            await message.channel.send(await tourney.gar.get_url())
            return

        await self._has_netplay_code(tourney, message)


def load_tournaments():
    saved = {}
    try:
        with open(PICKLE_FILE, 'rb') as f:
            saved = pickle.load(f)
    except OSError:
        pass
    except Exception as e: # pylint: disable=broad-except
        log.warning(f'Error unpickling: {e}')

    try:
        os.remove(PICKLE_FILE)
    except OSError:
        pass

    return saved


def setup_logging():
    """Log Discord and auTO messages to file."""
    logs = ['discord', __name__]
    for l in logs:
        logger = logging.getLogger(l)
        logger.setLevel(logging.INFO)
        handlers = [
            logging.FileHandler(
                filename='auTO.log', encoding='utf-8', mode='a'),
        ]
        if DEBUG:
            handlers.append(logging.StreamHandler(sys.stdout))
        for handler in handlers:
            formatter = logging.Formatter(
                '%(asctime)s:%(levelname)s:%(name)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)


class Bot(commands.Bot):
    async def close(self):
        await self.get_cog('auTO').close()
        await super().close()


def iprefix(bot, message):
    """Make prefix case insensitive and respond to @mentions."""
    msg = message.content
    prefix = '!auto '
    if msg.lower().startswith(prefix):
        return commands.when_mentioned_or(msg[:len(prefix)])(bot, message)
    return commands.when_mentioned(bot, message)


def main():
    saved = load_tournaments()
    setup_logging()
    github = 'https://github.com/mtimkovich/auTO#running-a-tournament'
    bot = Bot(command_prefix=iprefix,
              description=github,
              case_insensitive=True)
    bot.add_cog(auTO(bot, saved))
    bot.run(config.get('DISCORD_TOKEN'))


if __name__ == '__main__':
    main()
