import discord
from discord import ChannelType
import logging
from random import random
from typing import Optional

from . import utils


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

        name = utils.channel_name(self.name())

        # Check if text or voice channels already exist.
        text = next(self.tourney.get_channels(name, ChannelType.text), None)
        if text is None:
            text = await self.guild.create_text_channel(
                    name, category=self.tourney.category,
                    overwrites=overwrites)
            self.channels.append(text)
        
        voice = next(self.tourney.get_channels(name, ChannelType.voice), None)
        if voice is None:
            voice = await self.guild.create_voice_channel(
                    name, category=self.tourney.category,
                    overwrites=voice_overwrites)
            self.channels.append(voice)

        await text.send("Private channel for {}. Report results with "
                        "`!auTO report 0-2`. The reporter's score goes first."
                        .format(self.name(True)))

    async def close(self):
        for c in self.channels:
            try:
                await c.delete()
            except discord.errors.NotFound as e:
                logging.warning(e)
