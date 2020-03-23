# auTO

**auTO** (pronounced *[Otto][otto]*) is a Discord bot for running Melee netplay tournaments by
calling matches and reporting results.

![auTO Preview][preview]

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

I also recommend creating a role called "TO" on your server. Everyone with this role will
be able to run commands requiring the TO permission.

## Running a Tournament

1. [Invite auTO to your server.][install]
2. Create your Challonge bracket and add players.
    1. Note: The player's tag in the Challonge bracket **must be** their Discord username.
3. Run `!auTO start [CHALLONGE_URL]` in the channel you want the tournament to run.
    1. auTO will dm you to ask for your Challonge API key. (This is deleted as soon as the
       tournament finishes.)
4. auTO will start calling matches!
5. Players can report their matches using the `!auTO report` command.

## Discord Commands

Commands are called by typing `!auTO [command]` in the channel. To run a TO command,
the user must be an admin or in a role called "TO".

| Command                 | Permissions | Description                                  |
|-------------------------|-------------|----------------------------------------------|
| `start [CHALLONGE_URL]` | TO          | Start TOing the bracket                      |
| `stop`                  | TO          | Stop TOing                                   |
| `update_tags`           | TO          | Get the latest tags from Challonge           |
| `report 0-2`            | Players     | Report a match (reporter's score goes first) |
| `matches`               | All         | Print current matches                        |
| `status`                | All         | Print how far along the tournament is        |
| `help`                  | All         | Print the list of commands                   |

## Used By
* 6 Buffer Saturday
* MTV Melee

Please let me know if you use auTO for your tournament: I'd love to hear about it!

## Bug/Feature Requests

* [File an issue!](https://github.com/mtimkovich/auTO/issues)
* Message me on Twitter - [@DJSwerveGG][twitter]

## Development

Requires Python 3.7+

## Changelog

### 1.3
* Use setuptools for package.
* Use `!` as prefix to be more familiar to Twitch ~~nerds~~ users.

### 1.2
* Check that all players in in the server before starting.
* Make commands case-insensitive.

### 1.1
* Only ping for new matches.
* Add timeout between reports to avoid duplicates.

## Author

Max "DJSwerve" Timkovich

[otto]: https://www.ssbwiki.com/Smasher:Silent_Wolf
[install]: https://github.com/mtimkovich/auTO#install
[invite]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=10240&scope=bot
[preview]: https://raw.githubusercontent.com/mtimkovich/auTO/master/img/auTO_preview.png
[twitter]: https://twitter.com/DJSwerveGG
