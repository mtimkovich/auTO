"""Challonge API wrapper."""
import asyncio
import collections
import functools
import os
import re
from typing import Optional, List

import aiohttp
from aiohttp.client_exceptions import ClientResponseError

from . import utils

BASE_CHALLONGE_API_URL = 'https://api.challonge.com/v1/tournaments'
URLS = {
    'tournament': os.path.join(BASE_CHALLONGE_API_URL, '{}.json'),
    'participants': os.path.join(
        BASE_CHALLONGE_API_URL, '{}', 'participants.json'),
    'matches': os.path.join(BASE_CHALLONGE_API_URL, '{}', 'matches.json'),
}

MATCH_URL = os.path.join(BASE_CHALLONGE_API_URL, '{}', 'matches', '{}')
PARTICIPANT_URL = os.path.join(
        BASE_CHALLONGE_API_URL, '{}', 'participants', '{}.json')


def extract_id(url):
    """Extract the tournament id of the tournament from its name or URL."""
    match = re.search(r'(\w+)?\.?challonge.com/([^/]+)', url)

    if match is None or match.group(2) is None:
        raise ValueError(f'Invalid Challonge URL: {url}')

    subdomain, tourney = match.groups()

    if subdomain is None:
        return tourney
    return f'{subdomain}-{tourney}'


def raw_dict(func):
    """Erect the raw_dict if it's not already up."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.raw_dict is None:
            await self.get_raw()
        return await func(self, *args, **kwargs)
    return wrapper


class Challonge():
    def __init__(self, api_key, tournament_id, session):
        self.api_key = api_key
        self.api_key_dict = {'api_key': self.api_key}
        self.tournament_id = tournament_id
        self.session = session
        self.losers_rounds = None
        self.winners_rounds = None

        self.player_map = None
        self.raw_dict = None

    async def get_raw(self):
        self.raw_dict = {}

        await asyncio.gather(*(self.update_data(key) for key in URLS))

        self._set_player_map()
        self._max_rounds()

        return self.raw_dict

    async def update_data(self, key):
        url = URLS[key].format(self.tournament_id)
        async with self.session.get(url, params=self.api_key_dict) as resp:
            data = await resp.json()
            self.raw_dict[key] = data

            return data

    @raw_dict
    async def get_url(self) -> str:
        return self.raw_dict['tournament']['tournament']['full_challonge_url']

    @raw_dict
    async def get_name(self) -> str:
        return self.raw_dict['tournament']['tournament']['name'].strip()

    def get_state(self) -> str:
        return self.raw_dict['tournament']['tournament']['state']

    def _is_elimination(self) -> bool:
        return (self.raw_dict['tournament']['tournament']['tournament_type']
                .endswith('elimination'))

    def _max_rounds(self):
        for match in self.raw_dict['matches']:
            round_num = match['match']['round']
            if self.losers_rounds is None or self.winners_rounds is None:
                self.losers_rounds = round_num
                self.winners_rounds = round_num
                continue

            self.losers_rounds = min(self.losers_rounds, round_num)
            self.winners_rounds = max(self.winners_rounds, round_num)

    def round_name(self, round_num: int) -> str:
        """Creates the shortened, human-readable version of round names."""
        prefix = 'W' if round_num > 0 else 'L'
        suffix = f'R{abs(round_num)}'

        if self.winners_rounds is None or self.losers_rounds is None:
            return f'{prefix}{suffix}'

        if round_num == self.winners_rounds:
            return 'GF'
        if round_num in (self.winners_rounds - 1, self.losers_rounds):
            suffix = 'F'
        elif round_num in (self.winners_rounds - 2, self.losers_rounds + 1):
            suffix = 'SF'
        elif round_num in (self.winners_rounds - 3, self.losers_rounds + 2):
            suffix = 'QF'

        return f'{prefix}{suffix}'

    def _set_player_map(self):
        """Creates map from id to player tag.

        Sometimes Challonge seems to use the "group_player_ids" parameter of
        "participant" instead of the "id" parameter of "participant" in the
        "matches" API. Not sure exactly when this happens, but the following
        code checks for both.
        """
        self.player_map = {}
        for p in self.raw_dict['participants']:
            if p['participant'].get('name'):
                player_name = p['participant']['name'].strip()
            else:
                player_name = p['participant'].get(
                    'username', '<unknown>').strip()
            self.player_map[p['participant'].get('id')] = player_name
            if p['participant'].get('group_player_ids'):
                for gpid in p['participant']['group_player_ids']:
                    self.player_map[gpid] = player_name

    @raw_dict
    async def progress_meter(self) -> int:
        tournament = await self.update_data('tournament')
        return tournament['tournament']['progress_meter']

    async def report_match(self, match_id: int, winner_id: int,
                           scores: str) -> str:
        url = MATCH_URL.format(self.tournament_id, match_id) + '.json'
        data = self.api_key_dict.copy()
        data['match[winner_id]'] = winner_id
        data['match[scores_csv]'] = scores

        async with self.session.put(url, data=data) as r:
            return await r.json()

    async def mark_underway(self, match_id: int) -> str:
        url = os.path.join(MATCH_URL.format(self.tournament_id, match_id),
                           'mark_as_underway.json')
        async with self.session.post(url, data=self.api_key_dict) as r:
            return await r.json()

    async def finalize(self) -> str:
        url = os.path.join(BASE_CHALLONGE_API_URL, self.tournament_id,
                           'finalize.json')
        async with self.session.post(url, data=self.api_key_dict) as r:
            await r.json()

    async def start(self):
        url = os.path.join(BASE_CHALLONGE_API_URL, self.tournament_id,
                           'start.json')
        async with self.session.post(url, data=self.api_key_dict) as r:
            await r.json()

    @raw_dict
    async def get_matches(self) -> List:
        """Fetch latest match data.

        Unlike the other variables, this one needs to be fetched every time
        we use it.
        """
        matches = []
        for m in await self.update_data('matches'):
            m = m['match']

            player1_id = m['player1_id']
            player2_id = m['player2_id']
            round_num = m['round']
            winner_id = m['winner_id']
            loser_id = m['loser_id']

            if self._is_elimination():
                round_name = self.round_name(round_num)
            else:
                round_name = f'R{round_num}'

            if player1_id is None or player2_id is None:
                continue

            player1 = self.player_map[player1_id]
            player2 = self.player_map[player2_id]

            winner = None
            loser = None
            if winner_id is not None and loser_id is not None:
                winner = self.player_map[winner_id]
                loser = self.player_map[loser_id]

            match = {
                'id': m['id'],
                'loser': loser,
                'player1': player1,
                'player1_id': player1_id,
                'player2': player2,
                'player2_id': player2_id,
                'round': round_name,
                'state': m['state'],
                'suggested_play_order': m['suggested_play_order'],
                'underway': m['underway_at'] is not None,
                'winner': winner,
            }
            matches.append(match)
        return matches

    def _get_player_name(self, p) -> str:
        return (p['participant']['name'].strip()
                if p['participant']['name']
                else p['participant']['username'].strip())

    @raw_dict
    async def get_players(self) -> List[str]:
        return [self._get_player_name(p)
                for p in self.raw_dict['participants']]

    async def get_top8(self) -> Optional[List]:
        await self.get_raw()
        if self.get_state() != 'complete':
            return None

        top8 = collections.defaultdict(list)
        for p in self.raw_dict['participants']:
            rank = p['participant']['final_rank']
            if rank <= 7:
                top8[rank].append(self._get_player_name(p))

        return sorted(top8.items())

    @raw_dict
    async def _get_player(self, tag: str) -> Optional:
        for p in self.raw_dict['participants']:
            name = self._get_player_name(p)
            if utils.istrcmp(tag, name):
                return p
        return None

    async def _player_url(self, tag: str) -> str:
        p = await self._get_player(tag)
        if p is None:
            raise ValueError(f"Can't find player with tag: '{tag}'")
        player = p['participant']
        return PARTICIPANT_URL.format(self.tournament_id, player['id'])

    async def rename(self, tag: str, discord_name: str):
        """Rename player from |tag| to |discord_name|."""
        url = await self._player_url(tag)
        data = self.api_key_dict.copy()
        data['participant[name]'] = discord_name
        try:
            async with self.session.put(url, data=data) as r:
                await r.json()
        except ClientResponseError as e:
            if e.code == 422:
                raise ValueError(
                    f"Can't rename '{tag}' to '{discord_name}'. "
                    "Possible duplicate?") from ClientResponseError
            raise e

        await self.get_raw()

    async def dq(self, tag: str):
        url = await self._player_url(tag)
        async with self.session.delete(url, data=self.api_key_dict) as r:
            await r.json()


async def main():
    # tournament_id = 'mtvmelee-netplay2'
    tournament_id = 'djswerve1'
    api_key = os.environ.get('CHALLONGE_KEY')
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        gar = Challonge(api_key, tournament_id, session)
        await gar.get_raw()
        await gar.rename('tinklefairy6', 'DJSwerve')
        print(await gar.get_players())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
