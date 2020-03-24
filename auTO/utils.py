

def istrcmp(a: str, b: str) -> bool:
    return a.lower() == b.lower()


async def send_list(ctx, the_list):
    """Send multi-line messages."""
    return await ctx.send('\n'.join(the_list))
