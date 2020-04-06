import asyncio
import discord
from enum import Enum, auto
from random import random
from typing import Optional

from . import challonge
from . import utils


class ChannelType(Enum):
    ALL = auto()
    TEXT = auto()
    VOICE = auto()


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


class Match(object):
    def __init__(self, tourney, player1_tag: str, player2_tag: str):
        if random() < .5:
            player1_tag, player2_tag = player2_tag, player1_tag
        self.tourney = tourney
        self.guild = tourney.guild
        self.player1_tag = player1_tag
        self.player2_tag = player2_tag
        self.player1 = tourney.get_user(player1_tag)
        self.player2 = tourney.get_user(player2_tag)
        self.first = True
        self.channels = []

    def tag(self, player: Optional[discord.Member], tag: str,
            mention: bool) -> str:
        if player is None:
            return tag
        elif mention:
            return player.mention
        else:
            return player.display_name

    def name(self, mention: bool = False) -> str:
        player1 = self.tag(self.player1, self.player1_tag, mention)
        player2 = self.tag(self.player2, self.player2_tag, mention)
        return '{} vs {}'.format(player1, player2)

    def channel_name(self) -> str:
        """Match the style of the text channel."""
        return self.name().lower().replace(' ', '-')

    async def create_channels(self):
        if not (self.tourney.permissions().manage_channels and
                self.player1 and self.player2):
            return

        default = discord.PermissionOverwrite(
            read_messages=False,
            send_messages=False,
            speak=False,
            add_reactions=False,
        )

        player_perm = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            speak=True,
            stream=True,
            add_reactions=True,
        )

        overwrites = {
            self.guild.default_role: default,
            self.guild.me: player_perm,
            self.player1: player_perm,
            self.player2: player_perm,
        }

        to_role = self.tourney.get_role('TO')
        if to_role is not None:
            overwrites[to_role] = player_perm

        voice_default = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
        )

        voice_overwrites = overwrites.copy()
        voice_overwrites[self.guild.default_role] = voice_default

        # Check if text or voice channels already exist.
        text = self.tourney.get_channel(self.channel_name(), ChannelType.TEXT)
        if text is None:
            text = await self.guild.create_text_channel(
                self.channel_name(),
                category=self.tourney.category,
                overwrites=overwrites)
            self.channels.append(text)

        if not self.tourney.get_channel(
                self.channel_name(), ChannelType.VOICE):
            voice = await self.guild.create_voice_channel(
                self.channel_name(),
                category=self.tourney.category,
                overwrites=voice_overwrites)
            self.channels.append(voice)

        await text.send("Private channel for {}. Report results with "
                        "`!auTO report 0-2`. (The reporter's score goes "
                        "first.)".format(self.name(True)))

    async def close(self):
        for c in self.channels:
            await c.delete()


class Tournament(object):
    """Tournaments are unique to a guild."""
    def __init__(self, ctx, tournament_id, api_key, session):
        self.guild = ctx.guild
        # The channel where matches are posted.
        self.channel = ctx.channel
        self.owner = ctx.author
        self.previous_match_msgs = None
        self.open_matches = []
        self.called_matches = {}
        self.recently_called = set()
        self.category = None
        self.gar = challonge.Challonge(api_key, tournament_id, session)

    async def get_open_matches(self):
        matches = await self.gar.get_matches()
        self.open_matches = [m for m in matches if m['state'] == 'open']
        if self.permissions().manage_channels and self.category is None:
            self.category = await self.guild.create_category('matches')

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
        await self.add_to_recently_called(match, reporter)
        await self.gar.report_match(
                match['id'], winner_id, scores_csv)
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

    async def stop(self):
        """Cleanup channels we've created."""
        for match in self.called_matches.values():
            await match.close()
        if self.category:
            await self.category.delete()

    def permissions(self) -> discord.Permissions:
        """Gets our permissions on the server."""
        return self.channel.permissions_for(self.guild.me)

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        member = get_user(self.guild, username)
        if member:
            return member.mention
        return username

    def get_user(self, username: str) -> Optional[discord.Member]:
        """Get member by username."""
        return next((m for m in self.guild.members
                    if utils.istrcmp(m.display_name, username)), None)

    def get_role(self, role_name: str) -> Optional[discord.Role]:
        return next((r for r in self.guild.roles if r.name == role_name), None)

    def get_channel(self, channel_name: str,
                    type: ChannelType = ChannelType.ALL) -> Optional:
        if type == ChannelType.TEXT:
            lst = self.guild.text_channels
        elif type == ChannelType.VOICE:
            lst = self.guild.voice_channels
        else:
            lst = self.guild.channels
        return next((r for r in lst if r.name == channel_name), None)
