from .tournament import Tournament

class TournamentMap(dict):
    def __init__(self, guild, api_key: str, session):
        super().__init__()
        self.guild = guild
        self.api_key = api_key
        self.session = session

    def __getitem__(self, tid: str):
        return self[tid]

    def add(self, ctx, tournament_id: str):
        self[tournament_id] = Tournament(
                ctx, tournament_id, self.api_key, self.session)
        return self[tournament_id]

    # TODO: Find which commands need to be surfaced to this class.

    async def get_open_matches(self):
    async def create_matches_category(self):
    async def delete_matches_category(self):
    async def mark_match_underway(self, user1, user2=None):
    def find_match(self, username: str) -> Match:
    async def report_match(self, match, winner_id, reporter, scores_csv):
    def _add_to_recently_called(self, match, reporter):
    def is_duplicate_report(self, reporter: str) -> bool:
    async def missing_tags(self, owner) -> bool:
    def permissions(self) -> discord.Permissions:
    def mention_user(self, username: str) -> str:
    def get_user(self, username: str) -> Optional[discord.Member]:
    def get_channels(self, channel_name: str, type: ChannelType = None):
    def _create_channel_name(self, a: str, b: str) -> str:
    async def clean_up_channels(self, open_matches):
