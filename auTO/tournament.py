import asyncio
import discord
from discord import ChannelType
from typing import Optional

from . import challonge
from .match import manage_channels
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
        self.open_matches = []
        self.called_matches = {}
        self.recently_called = set()
        self.category = None
        self.gar = challonge.Challonge(api_key, tournament_id, session)

    async def get_open_matches(self):
        matches = await self.gar.get_matches()
        self.open_matches = [m for m in matches if m['state'] == 'open']

        if self.permissions().manage_channels and self.category is None:
            await self.delete_matches_category()
            self.category = await self.guild.create_category('matches')

    @manage_channels
    async def delete_matches_category(self):
        """Delete matches category and all its channels."""
        existing_categories = self.get_channels(
                'matches', ChannelType.category)
        for c in existing_categories:
            await asyncio.gather(*(chan.delete() for chan in c.channels))
            await c.delete()

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

    def user_in_match(self, username, match) -> bool:
        return username.lower() in map(lambda s: s.lower(), [match['player1'],
                                       match['player2']])

    def find_match(self, username) -> Optional:
        for match in self.open_matches:
            if self.user_in_match(username, match):
                return match
        return None

    async def report_match(self, match, winner_id, reporter, scores_csv):
        await asyncio.gather(
            self.add_to_recently_called(match, reporter),
            self.gar.report_match(match['id'], winner_id, scores_csv)
        )
        match_obj = self.called_matches.get(match['id'])
        if match_obj:
            await match_obj.close()
            self.called_matches.pop(match['id'])

    async def add_to_recently_called(self, match, reporter):
        """Prevent both players from reporting at the same time."""
        if utils.istrcmp(match['player1'], reporter):
            other = match['player2']
        else:
            other = match['player1']
        self.recently_called.add(other)
        await asyncio.sleep(10)
        self.recently_called.remove(other)

    async def missing_tags(self, owner) -> bool:
        """Check the participants list for players not on the server."""
        dms = await utils.get_dms(owner)
        missing = [player for player in self.gar.get_players()
                   if not self.get_user(player)]
        if not missing:
            return False
        message = ['Missing Discord accounts for the following players:']
        for p in missing:
            message.append('- {}'.format(p))
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
        return utils.channel_name('{} vs {}'.format(player1, player2))

    @manage_channels
    async def clean_up_channels(self):
        if self.category is None:
            return
        channel_names = set()

        for m in self.open_matches:
            player1 = m['player1']
            player2 = m['player2']
            channel_names.add(self.create_channel_name(player1, player2))
            channel_names.add(self.create_channel_name(player2, player1))
        await asyncio.gather(*(c.delete() for c in self.category.channels
                             if c.name not in channel_names))
