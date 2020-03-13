import aiohttp
import asyncio
import iso8601
import os
import re

BASE_CHALLONGE_API_URL = 'https://api.challonge.com/v1/tournaments'
URLS = {
    'tournament': os.path.join(BASE_CHALLONGE_API_URL, '{}.json'),
    'participants': os.path.join(
            BASE_CHALLONGE_API_URL, '{}', 'participants.json'),
    'matches': os.path.join(BASE_CHALLONGE_API_URL, '{}', 'matches.json'),
}

class Challonge(object):
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self.get_raw()
        return self

    async def __aexit__(self, *args, **kwargs):
        await self.session.close()
        self.session = None

    def __init__(self, tournament_url):
        self.api_key = os.environ.get('CHALLONGE_KEY')
        self.api_key_dict = {'api_key': self.api_key}
        self.tournament_url = tournament_url
        self.tournament_id = self.extract_id(tournament_url)

        self.raw_dict = None

    async def get_raw(self):
        if self.raw_dict is not None:
            return self.raw_dict

        self.raw_dict = {}

        for key in URLS.keys():
            await self.update_data(key)

        return self.raw_dict

    async def update_data(self, key):
        url = URLS[key].format(self.tournament_id)
        async with self.session.get(url, params=self.api_key_dict) as resp:
            self.raw_dict[key] = await resp.json()

    async def get_url(self):
        return self.get_raw()['tournament']['tournament']['full_challonge_url']

    async def get_name(self):
        return self.get_raw()['tournament']['tournament']['name'].strip()

    async def get_date(self):
        return iso8601.parse_date(self.get_raw()['tournament']['tournament']['created_at'])

    async def _human_round_names(self, matches):
        """Convert round names from numbers into strings like WQF and LF."""
        last_round = matches[-1]['round']

        SUFFIXES = ['GF', 'F', 'SF', 'QF']

        rounds = {}
        for i, finals in enumerate(SUFFIXES):
            rounds[last_round-i] = finals
        for i, finals in enumerate(SUFFIXES[1:]):
            rounds[-(last_round-i)-1] = finals

        reset = matches[-1]['round'] == matches[-2]['round']
        reset_count = 1

        for m in matches:
            r = m['round']
            name = 'W' if r > 0 else 'L'
            if r not in rounds:
                name = '{}R{}'.format(name, abs(r))
            else:
                if rounds[r] != 'GF':
                    name += rounds[r]
                else:
                    name = 'GF'

                    if reset:
                        name += str(reset_count)
                        reset_count += 1

            m['round'] = name


    async def get_matches(self):
        # sometimes challonge seems to use the "group_player_ids" parameter of "participant" instead
        # of the "id" parameter of "participant" in the "matches" api.
        # not sure exactly when this happens, but the following code checks for both
        # TODO: We only want open matches.
        # TODO: Player map should be an instance variable.
        player_map = dict()
        for p in self.get_raw()['participants']:
            if p['participant'].get('name'):
                player_name = p['participant']['name'].strip()
            else:
                player_name = p['participant'].get('username', '<unknown>').strip()
            player_map[p['participant'].get('id')] = player_name
            if p['participant'].get('group_player_ids'):
                for gpid in p['participant']['group_player_ids']:
                    player_map[gpid] = player_name

        matches = []
        # TODO: We don't want to use the cached matches value here.
        for m in self.get_raw()['matches']:
            m = m['match']

            set_count = m['scores_csv']
            winner_id = m['winner_id']
            loser_id = m['loser_id']
            round_num = m['round']
            if winner_id is not None and loser_id is not None:
                winner = player_map[winner_id]
                loser = player_map[loser_id]
                match_result = {'winner': winner, 'loser': loser, 'round': round_num}
                matches.append(match_result)
        self._human_round_names(matches)
        return matches

    async def get_players(self):
        return [p['participant']['name'].strip()
                if p['participant']['name'] else p['participant']['username'].strip()
                for p in self.get_raw()['participants']]

    def extract_id(self, url):
        """Extract the tournament id of the tournament from its name or URL."""
        match = re.search(r'(\w+)?\.?challonge.com/([^/]+)', url)

        if match is None or match.group(2) is None:
            raise ValueError('Invalid Challonge URL: {}.'.format(url))

        subdomain, tourney = match.groups()

        if subdomain is None:
            return tourney
        else:
            return '{}-{}'.format(subdomain, tourney)

async def main():
    tournament_url = 'https://mtvmelee.challonge.com/100_amateur'
    async with Challonge(tournament_url) as gar:
        print(await gar.get_raw())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
