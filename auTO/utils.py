import discord
from typing import List


def istrcmp(a: str, b: str) -> bool:
    return a.lower() == b.lower()


async def send_list(ctx, the_list) -> List:
    """Send multi-line messages. Split messages longer than 2000 characters."""
    MAX_CHARS = 2000
    contents = ''
    msgs = []

    for line in the_list:
        if len(contents) + len(line) + 1 > MAX_CHARS:
            msg = await ctx.send(contents)
            msgs.append(msg)
            content = ''
        content += line + '\n'
    if contents:
        msg = await ctx.send(contents)
        msgs.append(msg)

    return msgs


async def get_dms(owner: discord.Member):
    return owner.dm_channel if owner.dm_channel else await owner.create_dm()
