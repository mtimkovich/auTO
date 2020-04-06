import discord
from enum import Enum, auto
from typing import List, Optional


def istrcmp(a: str, b: str) -> bool:
    return a.lower() == b.lower()


async def send_list(ctx: discord.abc.Messageable, the_list: List[str]) -> List:
    """Send multi-line messages. Split messages longer than 2000 characters."""
    MAX_CHARS = 2000
    contents = ''
    msgs = []

    for line in the_list:
        if len(contents) + len(line) + 1 > MAX_CHARS:
            msg = await ctx.send(contents)
            msgs.append(msg)
            contents = ''
        contents += line + '\n'
    if contents:
        msg = await ctx.send(contents)
        msgs.append(msg)

    return msgs


async def get_dms(owner: discord.Member):
    return owner.dm_channel if owner.dm_channel else await owner.create_dm()


def mention_user(guild, username: str) -> str:
    """Gets the user mention string. If the user isn't found, just return
    the username."""
    member = get_user(guild, username)
    if member:
        return member.mention
    return username


def get_user(guild, username: str) -> Optional[discord.Member]:
    """Get member by username."""
    return next((m for m in guild.members
                if istrcmp(m.display_name, username)), None)


def get_role(guild, role_name: str) -> Optional[discord.Role]:
    return next((r for r in guild.roles if r.name == role_name), None)


class ChannelType(Enum):
    ALL = auto()
    TEXT = auto()
    VOICE = auto()


def get_channel(guild, channel_name: str,
                type: ChannelType = ChannelType.ALL) -> Optional:
    if type == ChannelType.TEXT:
        lst = guild.text_channels
    elif type == ChannelType.VOICE:
        lst = guild.voice_channels
    else:
        lst = guild.channels
    return next((r for r in lst if r.name == channel_name), None)
