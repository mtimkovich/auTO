# auTO

**auTO** (pronounced *[Otto][otto]*) is a Discord bot for
running Melee netplay tournaments by calling matches and reporting results.

auTO can only manage tournaments ran through [Challonge](https://challonge.com) at the moment.

## Features
* List active matches.
* Ping players when it's time for them to play.
* Mark matches as in progress when players post netplay codes in the chat.
* Players can report their own matches without going through the TO.
* auTO can run multiple tournaments on the same server (useful for amateur brackets), they
  just need to be on separate channels.

## Install

Invite auTO to your Discord server by [clicking here][invite]. You'll need the "Manage Server"
permission.

## Running a Tournament

1. [Invite auTO to your server.][invite]
2. Create your Challonge bracket and add players.
    1. NB: The player's tag in the Challonge bracket **must be** their Discord username.
3. Run `/auTO start [CHALLONGE_URL]` in the channel you want the tournament to run.
    1. auTO will dm you to ask for your Challonge API key. (This is deleted as soon as the
       tournament finishes).
4. auTO will start calling matches!
5. Players can report their matches using the `/auTO report` command.

## Discord Commands

Commands are called by typing `/auTO [command]` in the channel.

| Command                 | Permissions | Description                                  |
|-------------------------|-------------|----------------------------------------------|
| `start [CHALLONGE_URL]` | TO          | Start TOing the bracket                      |
| `stop`                  | TO          | Stop TOing                                   |
| `matches`               | All         | Print current matches                        |
| `status`                | All         | Print how far along the tournament is        |
| `report 0-2`            | Players     | Report a match (reporter's score goes first) |

## Development

Requires Python 3.7+

## Changelog

### 1.2
- Check that all players in in the server before starting.
- Make commands case-insensitive.

### 1.1
- Only ping for new matches.
- Add timeout between reports to avoid duplicates.

## Author

Max "DJSwerve" Timkovich

[otto]: https://www.ssbwiki.com/Smasher:Silent_Wolf
[invite]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=10240&scope=bot
