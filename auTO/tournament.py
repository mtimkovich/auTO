import asyncio
from typing import List

from . import challonge
from . import utils


class Tournament(object):
    """Tournaments are unique to a guild + channel."""
    def __init__(self, ctx, tournament_id, api_key, session):
        self.guild = ctx.guild
        # The channel where matches are posted.
        self.channel = ctx.channel
        self.owner = ctx.author
        self.previous_match_msgs = None
        self.open_matches = []
        self.called_matches = set()
        self.recently_called = set()
        self.gar = challonge.Challonge(api_key, tournament_id, session)

    async def get_open_matches(self):
        matches = await self.gar.get_matches()
        self.open_matches = [m for m in matches if m['state'] == 'open']

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

    def find_match(self, username):
        for match in self.open_matches:
            if self.user_in_match(username, match):
                return match
        else:
            return None

    def mention_user(self, username: str) -> str:
        """Gets the user mention string. If the user isn't found, just return
        the username."""
        for member in self.guild.members:
            if utils.istrcmp(member.display_name, username):
                return member.mention
        return username

    def has_user(self, username: str) -> bool:
        """Finds if username is on the server."""
        return any(utils.istrcmp(m.display_name, username)
                   for m in self.guild.members)

    async def report_match(self, match, winner_id, reporter, scores_csv):
        await self.add_to_recently_called(match, reporter)
        await self.gar.report_match(
                match['id'], winner_id, scores_csv)
        try:
            self.called_matches.remove(match['id'])
        except KeyError:
            pass

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
                   if not self.has_user(player)]
        if not missing:
            return False
        message = ['Missing Discord accounts for the following players:']
        for p in missing:
            message.append('- {}'.format(p))
        await utils.send_list(dms, message)
        return True
