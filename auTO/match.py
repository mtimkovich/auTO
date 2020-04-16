import asyncio
import functools
import logging
from random import random
from typing import Optional

import discord

from . import utils

log = logging.getLogger(__name__)


DEFAULT = discord.PermissionOverwrite(
    read_messages=False,
    send_messages=False,
    add_reactions=False,
)

PLAYER_PERM = discord.PermissionOverwrite(
    read_messages=True,
    send_messages=True,
    speak=True,
    stream=True,
    add_reactions=True,
)

VOICE_DEFAULT = discord.PermissionOverwrite(
    view_channel=True,
    connect=True,
    stream=False,
)


def manage_channels(func):
    """Decorator that checks for the manage channels permission."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if hasattr(self, 'tourney'):
            tourney = self.tourney
        else:
            tourney = self
        if not tourney.permissions().manage_channels:
            return
        return await func(self, *args, **kwargs)
    return wrapper


class MatchPickle():
    """Pickleable version of Match."""
    def __init__(self, match):
        self.id = match.id
        self.player1_id = match.player1_id
        self.player2_id = match.player2_id
        self.player1_tag = match.player1_tag
        self.player2_tag = match.player2_tag
        self.rps = match.rps
        self.channel_ids = [c.id for c in match.channels]

    def unpickle(self, tourney):
        fake_raw = {
            'id': self.id,
            'player1': self.player1_tag,
            'player2': self.player2_tag,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
        }

        match = Match(tourney, fake_raw, self.rps)
        for c in self.channel_ids:
            channel = tourney.guild.get_channel(c)
            if channel is not None:
                match.channels.append(channel)
        return match


class Match():
    """Handles private channel creation."""
    def __init__(self, tourney, raw, rps=None):
        if rps is None:
            self.rps = random() < .5
        else:
            self.rps = rps
        self.id = raw['id']
        self.player1_tag = raw['player1']
        self.player2_tag = raw['player2']
        self.player1_id = raw['player1_id']
        self.player2_id = raw['player2_id']
        self.tourney = tourney
        self.guild = tourney.guild
        self.player1 = tourney.get_user(self.player1_tag)
        self.player2 = tourney.get_user(self.player2_tag)
        self.first = rps is None
        self.channels = []

    def pickle(self):
        return MatchPickle(self)

    def _tag(self, player: Optional[discord.Member], tag: str,
             mention: bool) -> str:
        if player is None:
            return tag
        if mention:
            return player.mention
        return player.display_name

    def name(self, mention: bool = False) -> str:
        player1 = self._tag(self.player1, self.player1_tag, mention)
        player2 = self._tag(self.player2, self.player2_tag, mention)
        if self.rps:
            return f'{player1} vs {player2}'
        return f'{player2} vs {player1}'

    def has_player(self, tag: str) -> bool:
        return tag.lower() in list(
            map(lambda s: s.lower(), [self.player1_tag, self.player2_tag]))

    def update_player(self, old_tag: str, member: discord.Member):
        if utils.istrcmp(self.player1_tag, old_tag):
            self.player1_tag = member.display_name
            self.player1 = member
        elif utils.istrcmp(self.player2_tag, old_tag):
            self.player2_tag = member.display_name
            self.player2 = member

    @manage_channels
    async def create_channels(self):
        if not self.player1 or not self.player2:
            return

        overwrites = {
            self.guild.default_role: DEFAULT,
            self.guild.me: PLAYER_PERM,
            self.player1: PLAYER_PERM,
            self.player2: PLAYER_PERM,
        }

        to_role = discord.utils.get(self.guild.roles, name='TO')
        if to_role is not None:
            overwrites[to_role] = PLAYER_PERM

        voice_overwrites = overwrites.copy()
        voice_overwrites[self.guild.default_role] = VOICE_DEFAULT

        name = utils.channel_name(self.name())

        self.channels = await asyncio.gather(
            self.tourney.category.create_text_channel(
                name, overwrites=overwrites),
            self.tourney.category.create_voice_channel(
                name, overwrites=voice_overwrites)
        )

        text = self.channels[0]

        rps_winner = (self.player1.display_name if self.rps
                      else self.player2.display_name)

        await text.send(
            f"Private channel for {self.name(True)}. {rps_winner} won RPS. "
            "Report results with `@auTO report 0-2`. "
            "The reporter's score goes first.")

    @manage_channels
    async def close(self):
        try:
            await asyncio.gather(*(c.delete() for c in self.channels))
        except discord.HTTPException as e:
            log.warning(e)
