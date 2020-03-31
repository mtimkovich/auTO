import discord


def istrcmp(a: str, b: str) -> bool:
    return a.lower() == b.lower()


async def send_list(ctx, the_list):
    """Send multi-line messages."""
    # TODO(#20): Split into multiple messages if message is longer than 2000
    # characters.
    return await ctx.send('\n'.join(the_list))


async def get_dms(owner: discord.Member):
    return owner.dm_channel if owner.dm_channel else await owner.create_dm()
