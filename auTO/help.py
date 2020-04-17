class HelpDoc(dict):
    def __init__(self, brief: str, description='', usage=''):
        if not description:
            description = self.descriptify(brief)
        super().__init__(
            brief=brief,
            description=description,
            usage=usage
        )

    def descriptify(self, s):
        return s[0].upper() + s[1:] + '.'


help = dict(
    bracket=HelpDoc('print the bracket URL'),
    matches=HelpDoc('print the current matches'),
    noshow=HelpDoc(
        'start DQ process for player',
        ('Notify @Player that they are in danger of being DQed. They have '
         '5 minutes to post in the chat before being removed from bracket.'),
        '@Player'),
    rename=HelpDoc(
        'rename player to their Discord tag',
        '',
        '"TAG" @Player'),
    report=HelpDoc(
        'report a match',
        "Report a match result. The reporter's score goes first.",
        '0-2 OR\n!auTO 0-2'),
    results=HelpDoc(
        'print Top 8',
        'Print Top 8 if the bracket is finished.'),
    start=HelpDoc(
        'start running bracket',
        'Start TOing and calling matches.',
        'CHALLONGE_URL'),
    status=HelpDoc('how far along the tournament is'),
    stop=HelpDoc('stop TOing'),
    update_tags=HelpDoc('get latest Challonge tags'),
)
