# auTO

auTO is a Discord bot for running [Challonge](https://challonge.com) netplay tournaments by calling
matches and allowing players to self-report results. It speeds up running brackets and lets TOs do
less work.

![auTO Preview][preview]

## Features
* List active matches.
* Ping players when it's time for them to play.
* Create private voice and text channels for each match.
* Players can report their own matches without going through the TO.
* TOs can start an auto DQ timer for missing players (`noshow`).
* Automatic RPS. No more need to use Mr. Game & Watch to figure out who
  gets to stage-strike first.

## Setup

Invite auTO to your Discord server by [clicking here][invite]. You'll need the "Manage Server"
permission.

It's also recommended to create a role called "TO" on your server. Everyone with this role will
be able to run commands requiring the TO permission. By default, only the creator and admins
are able to run TO commands.

## Running a Tournament

1. [Invite auTO to your server.][setup]
2. Create your Challonge bracket and add players.
    1. Note: The player's tag in the Challonge bracket **must be** their Discord username. This is
    their nickname as it appears on the tournament server and doesn't include the "#12345"
    identifier at the end.
3. Run `@auTO start CHALLONGE_URL` in the channel you want the tournament to run.
    1. Note: If your tournament is part of a community, the `CHALLONGE_URL` will need to be `https://challonge.com/community_name-tournament_name`. You can find `community_name` under the "Settings" tab for your community, in the "Subdomain" field.
    2. auTO will dm you to ask for your Challonge API key. (This is deleted as soon as the
       tournament finishes.)
4. auTO will start calling matches!
5. Players report their matches using the `@auTO report` command.

## Discord Commands

Commands are called by typing `@auTO COMMAND` or `!auTO COMMAND` in the channel. To run a TO
command, the user must be an admin or in a role called "TO".

| Command                 | Permissions | Description                                          |
|-------------------------|-------------|------------------------------------------------------|
| `start CHALLONGE_URL`   | All         | Start TOing the bracket                              |
| `stop`                  | TO          | Stop TOing                                           |
| `results`               | TO          | Print results after tournament is finalized          |
| `rename TAG @PLAYER`    | TO          | Rename player to their Discord username              |
| `noshow @PLAYER`        | TO          | Give player 5 minutes to post in the chat or be DQed |
| `dq @PLAYER`            | TO          | DQ player                                            |
| `update_tags`           | TO          | Get the latest tags from Challonge                   |
| `report 0-2` or `0-2`   | Players     | Report a match (reporter's score goes first)         |
| `matches`               | All         | Print current matches                                |
| `status`                | All         | Print how far along the tournament is                |
| `bracket`               | All         | Print the bracket URL                                |
| `help`                  | All         | Print the list of commands                           |

## Used By
* Dutch Melee Netplay
* Hamburg SSB
* Chicagoland Melee
* North Carolina Melee
* Smash Mines Online
* MTV Melee

Let me know if you use auTO for your tournament—I'd love to hear about it!

## Bug/Feature Requests

* [File an issue!](https://github.com/mtimkovich/auTO/issues)
* Message me on:
  * Twitter: [@DJSwerveGG][twitter]
  * Discord: DJSwerve#0567

## Author

Max "DJSwerve" Timkovich

[setup]: https://github.com/mtimkovich/auTO#setup
[invite]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=75856&scope=bot
[preview]: https://raw.githubusercontent.com/mtimkovich/auTO/master/img/auTO_preview.png
[twitter]: https://twitter.com/DJSwerveGG
