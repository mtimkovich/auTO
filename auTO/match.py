import asyncio
import discord
from discord import ChannelType
import functools
import logging
from random import random
from typing import Optional

from . import utils


default = discord.PermissionOverwrite(
    read_messages=False,
    send_messages=False,
    add_reactions=False,
)

player_perm = discord.PermissionOverwrite(
    read_messages=True,
    send_messages=True,
    speak=True,
    stream=True,
    add_reactions=True,
)

voice_default = discord.PermissionOverwrite(
    view_channel=True,
    connect=True,
    speak=False,
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


class Match(object):
    """Handles private channel creation."""
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

    @manage_channels
    async def create_channels(self):
        if not (self.player1 and self.player2):
            return

        overwrites = {
            self.guild.default_role: default,
            self.guild.me: player_perm,
            self.player1: player_perm,
            self.player2: player_perm,
        }

        to_role = self.tourney.get_role('TO')
        if to_role is not None:
            overwrites[to_role] = player_perm

        voice_overwrites = overwrites.copy()
        voice_overwrites[self.guild.default_role] = voice_default

        name = utils.channel_name(self.name())
        create_channels = []
        new_text = False

        # Check if text or voice channels already exist.
        text = next(self.tourney.get_channels(name, ChannelType.text), None)
        if text is None:
            text_aw = self.guild.create_text_channel(
                    name, category=self.tourney.category,
                    overwrites=overwrites)
            new_text = True
            create_channels.append(text_aw)

        voice = next(self.tourney.get_channels(name, ChannelType.voice), None)
        if voice is None:
            voice_aw = self.guild.create_voice_channel(
                    name, category=self.tourney.category,
                    overwrites=voice_overwrites)
            create_channels.append(voice_aw)

        channels = await asyncio.gather(*create_channels)
        self.channels += channels

        if new_text:
            text = channels[0]

        await text.send("Private channel for {}. Report results with "
                        "`!auTO report 0-2`. The reporter's score goes first."
                        .format(self.name(True)))

    @manage_channels
    async def close(self):
        try:
            await asyncio.gather(*(c.delete() for c in self.channels))
        except discord.errors.NotFound as e:
            logging.warning(e)
