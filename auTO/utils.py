"""Some helper functions."""
import re
from typing import List

import discord


def istrcmp(a: str, b: str) -> bool:
    """This is dumb, but I like it."""
    return a.lower() == b.lower()


async def send_list(ctx: discord.abc.Messageable, the_list: List[str]) -> List:
    """Send multi-line messages. Split messages longer than 2000 characters."""
    max_chars = 2000
    contents = ''
    msgs = []

    for line in the_list:
        if len(contents) + len(line) + 1 > max_chars:
            msg = await ctx.send(contents)
            msgs.append(msg)
            contents = ''
        contents += line + '\n'
    if contents:
        msg = await ctx.send(contents)
        msgs.append(msg)

    return msgs


async def get_dms(owner: discord.Member):
    """Gets dm channel or creates it."""
    return owner.dm_channel if owner.dm_channel else await owner.create_dm()


def channel_name(name: str) -> str:
    """Match the style of the text channel."""
    name = name.lower().replace(' ', '-')
    punctuation = re.escape(r'!"#$%&\'()*+,./:;<=>?@[\]^`{|}~')
    return re.sub(rf'[{punctuation}]+', '', name)
