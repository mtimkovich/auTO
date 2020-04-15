help = {
    'bracket': {'brief': 'print the bracket URL'},
    'matches': {'brief': 'print the current matches'},
    'noshow': {
        'brief': 'start DQ process for player',
        'usage': '@Player',
        'description': (
            'Notify @Player that they are in danger of being DQed. They have '
            '5 minutes to post in the chat before being removed from bracket.')
    },
    'rename': {
        'brief': 'rename player to their Discord tag',
        'usage': 'TAG @Player',
    },
    'report': {
        'brief': 'report a match',
        'description': (
            "Report a match result. The reporter's score goes first."),
        'usage': '0-2 OR\n!auTO 2-0',
    },
    'results': {
        'brief': 'print Top 8',
        'description': 'Print Top 8 if the bracket is finished.',
    },
    'start': {
        'brief': 'start running bracket',
        'description': 'Start TOing and calling matches.',
        'usage': 'CHALLONGE_URL'
    },
    'status': {'brief': 'how far along the tournament is'},
    'stop': {'brief': 'stop TOing'},
    'update_tags': {'brief': 'get latest Challonge tags'},
}

def descriptify(s):
    return s[0].upper() + s[1:] + '.'

for cmd, args in help.items():
    if 'usage' not in args:
        help[cmd]['usage'] = ''
    if 'description' not in args:
        help[cmd]['description'] = descriptify(help[cmd]['brief'])
