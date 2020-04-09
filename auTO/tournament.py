import asyncio
import discord
from discord import ChannelType
from time import time
from typing import Optional

from . import challonge
from .match import manage_channels, Match
from . import utils


class FakeContext(object):
    def __init__(self, guild, saved):
        self.guild = guild
        self.channel = guild.get_channel(saved.channel_id)
        self.author = guild.get_member(saved.owner_id)

        if not (self.guild or self.channel or self.author):
            raise ValueError('Error loading tournament')


class TournamentPickle(object):
    """Pickleable version of Tournament."""
    def __init__(self, tourney):
        self.channel_id = tourney.channel.id
        self.owner_id = tourney.owner.id
        self.tournament_id = tourney.gar.tournament_id
        self.api_key = tourney.gar.api_key


class Tournament(object):
    """Tournaments are unique to a guild."""
    def __init__(self, ctx, tournament_id, api_key, session):
        self.guild = ctx.guild
        # The channel where matches are posted.
        self.channel = ctx.channel
        self.owner = ctx.author
        self.previous_match_msgs = []
        self.called_matches = {}
        self.recently_called = {}
        self.category = None
        self.gar = challonge.Challonge(api_key, tournament_id, session)

    async def get_open_matches(self):
        matches = await self.gar.get_matches()
        return [m for m in matches if m['state'] == 'open']

    @manage_channels
    async def create_matches_category(self):
        if self.category is not None:
            return
        await self.delete_matches_category()
        self.category = await self.guild.create_category('matches')

    @manage_channels
    async def delete_matches_category(self):
        """Delete matches category and all its channels."""
        existing_categories = self.get_channels(
                'matches', ChannelType.category)
        for c in existing_categories:
            try:
                await asyncio.gather(*(chan.delete() for chan in c.channels))
                await c.delete()
            # We can't delete channels not created by us.
            except discord.errors.Forbidden as e:
                logging.warning(e)

    async def mark_match_underway(self, user1, user2):
        match_id = None

        for user in [user1, user2]:
            match = self.find_match(user.display_name)
            if match is None:
                return
            elif match_id is None:
                match_id = match.id
            elif match_id != match.id:
                return

        await self.gar.mark_underway(match_id)

    def find_match(self, username: str) -> Match:
        for _, match in self.called_matches.items():
            if match.has_player(username):
                return match
        return None

    async def report_match(self, match, winner_id, reporter, scores_csv):
        self.add_to_recently_called(match, reporter),
        await self.gar.report_match(match.id, winner_id, scores_csv)
        await match.close()
        self.called_matches.pop(match.id)

    def add_to_recently_called(self, match, reporter):
        """Prevent both players from reporting at the same time."""
        if utils.istrcmp(match.player1_tag, reporter):
            other = match.player2_tag
        else:
            other = match.player1_tag
        self.recently_called[other] = time()

    def is_duplicate_report(self, reporter: str) -> bool:
        reporter = reporter.lower()
        last_report_time = self.recently_called.get(reporter)
        if last_report_time is not None:
            if time() - last_report_time < 10:
                return True
            else:
                self.recently_called.pop(reporter)
        return False

    async def missing_tags(self, owner) -> bool:
        """Check the participants list for players not on the server."""
        dms = await utils.get_dms(owner)
        missing = [player for player in await self.gar.get_players()
                   if not self.get_user(player)]
        if not missing:
            return False
        message = ['Missing Discord accounts for the following players:']
        for p in missing:
            message.append(f'- {p}')
        await utils.send_list(dms, message)
        return True

    def permissions(self) -> discord.Permissions:
        """Gets our permissions on the server."""
        return self.channel.permissions_for(self.guild.me)

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        member = self.get_user(username)
        if member:
            return member.mention
        return username

    def get_user(self, username: str) -> Optional[discord.Member]:
        """Get member by username."""
        return next((m for m in self.guild.members
                    if utils.istrcmp(m.display_name, username)), None)

    def get_role(self, role_name: str) -> Optional[discord.Role]:
        return next((r for r in self.guild.roles if r.name == role_name), None)

    def get_channels(self, channel_name: str, type: ChannelType = None):
        if type == ChannelType.text:
            lst = self.guild.text_channels
        elif type == ChannelType.voice:
            lst = self.guild.voice_channels
        elif type == ChannelType.category:
            lst = self.guild.categories
        else:
            lst = self.guild.channels
        return (r for r in lst if r.name == channel_name)

    def create_channel_name(self, player1: str, player2: str) -> str:
        return utils.channel_name(f'{player1} vs {player2}')

    @manage_channels
    async def clean_up_channels(self, open_matches):
        if self.category is None:
            return
        channel_names = set()

        for m in open_matches:
            player1 = m['player1']
            player2 = m['player2']
            channel_names.add(self.create_channel_name(player1, player2))
            channel_names.add(self.create_channel_name(player2, player1))
        await asyncio.gather(*(c.delete() for c in self.category.channels
                             if c.name not in channel_names))
