import aiohttp
import asyncio
import iso8601
import math
import os
import re

BASE_CHALLONGE_API_URL = 'https://api.challonge.com/v1/tournaments'
URLS = {
    'tournament': os.path.join(BASE_CHALLONGE_API_URL, '{}.json'),
    'participants': os.path.join(
            BASE_CHALLONGE_API_URL, '{}', 'participants.json'),
    'matches': os.path.join(BASE_CHALLONGE_API_URL, '{}', 'matches.json'),
}

MATCH_URL = os.path.join(BASE_CHALLONGE_API_URL, '{}', 'matches', '{}')

def extract_id(url):
    """Extract the tournament id of the tournament from its name or URL."""
    match = re.search(r'(\w+)?\.?challonge.com/([^/]+)', url)

    if match is None or match.group(2) is None:
        raise ValueError('Invalid Challonge URL: {}.'.format(url))

    subdomain, tourney = match.groups()

    if subdomain is None:
        return tourney
    else:
        return '{}-{}'.format(subdomain, tourney)

class Challonge(object):
    def __init__(self, session):
        self.api_key = os.environ.get('CHALLONGE_KEY')
        if self.api_key is None:
            raise RuntimeError('CHALLONGE_KEY is unset')
        self.api_key_dict = {'api_key': self.api_key}
        self.session = session

        self.player_map = None
        self.raw_dict = None

    async def get_raw(self, tournament_id):
        self.tournament_id = tournament_id

        if self.raw_dict is not None:
            return self.raw_dict

        self.raw_dict = {}

        for key in URLS.keys():
            await self.update_data(key)

        return self.raw_dict

    async def update_data(self, key):
        url = URLS[key].format(self.tournament_id)
        async with self.session.get(url, params=self.api_key_dict) as resp:
            data = await resp.json()
            self.raw_dict[key] = data

            return data

    def get_url(self):
        return self.raw_dict['tournament']['tournament']['full_challonge_url']

    def get_name(self):
        return self.raw_dict['tournament']['tournament']['name'].strip()

    def get_date(self):
        return iso8601.parse_date(self.raw_dict['tournament']['tournament']['created_at'])

    def num_winners_rounds(self, num_players: int) -> int:
        return int(math.ceil(math.log(num_players, 2))) + 1

    def num_total_rounds(self, num_players: int) -> int:
        log2 = math.log(num_players, 2)
        return int(math.ceil(log2) + math.ceil(math.log(log2, 2)))

    def round_name(self, round_num: int) -> str:
        """Creates the shortened human-readable version of round names."""
        num_players = len(self.get_players())
        winners_rounds = self.num_winners_rounds(num_players)
        total_rounds = self.num_total_rounds(num_players)

        prefix = 'W' if round_num > 0 else 'L'
        suffix = 'R{}'.format(abs(round_num))

        if round_num == winners_rounds:
            return 'GF'
        elif round_num == winners_rounds - 1 or round_num == -total_rounds:
            suffix = 'F'
        elif round_num == winners_rounds - 2 or round_num == -total_rounds + 1:
            suffix = 'SF'
        elif round_num == winners_rounds - 3 or round_num == -total_rounds + 2:
            suffix = 'QF'

        return '{}{}'.format(prefix, suffix)

    def get_player_map(self):
        if self.player_map is not None:
            return self.player_map

        self.player_map = {}
        for p in self.raw_dict['participants']:
            if p['participant'].get('name'):
                player_name = p['participant']['name'].strip()
            else:
                player_name = p['participant'].get('username', '<unknown>').strip()
            self.player_map[p['participant'].get('id')] = player_name
            if p['participant'].get('group_player_ids'):
                for gpid in p['participant']['group_player_ids']:
                    self.player_map[gpid] = player_name
        return self.player_map

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

    async def get_open_matches(self):
        # sometimes challonge seems to use the "group_player_ids" parameter of "participant" instead
        # of the "id" parameter of "participant" in the "matches" api.
        # not sure exactly when this happens, but the following code checks for both

        # Unlike the other variables, this one needs to be fetched everytime
        # we use it.
        matches = []
        for m in await self.update_data('matches'):
            m = m['match']

            player1_id = m['player1_id']
            player2_id = m['player2_id']
            id = m['id']
            state = m['state']
            round_num = m['round']
            underway = m['underway_at'] is not None

            if state != 'open':
                continue

            player1 = self.get_player_map()[player1_id]
            player2 = self.get_player_map()[player2_id]
            match = {
                'player1': player1,
                'player1_id': player1_id,
                'player2': player2,
                'player2_id': player2_id,
                'id': id,
                'round': self.round_name(round_num),
                'underway': underway,
            }
            matches.append(match)
        return matches

    def get_players(self):
        return [p['participant']['name'].strip()
                if p['participant']['name'] else p['participant']['username'].strip()
                for p in self.raw_dict['participants']]


async def main():
    tournament_id = 'mtvmelee-100_amateur'
    match_id = 163507232
    winner_id = 88948490
    async with aiohttp.ClientSession() as session:
        gar = Challonge(session)
        await gar.get_raw(tournament_id)
        # err = await gar.report_match(match_id, winner_id, '2-0')
        # print(err)
        await gar.mark_underway(match_id)
        open_matches = await gar.get_open_matches()
        print(open_matches)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
