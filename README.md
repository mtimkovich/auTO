# auTO

auTO is a Discord bot for running netplay tournaments by calling matches and reporting results.

![auTO Preview][preview]

auTO can only manage tournaments ran through [Challonge](https://challonge.com).

## Features
* List active matches.
* Ping players when it's time for them to play.
* Create private channels for each match.
* Players can report their own matches without going through the TO.
* TOs can start auto DQ timer for missing players (`noshow`).
* Mark matches as in progress when players post netplay codes in the chat.
* Automatic RPS: Player order is randomized, so first player listed stage strikes first.

## Setup

Invite auTO to your Discord server by [clicking here][invite]. You'll need the "Manage Server"
permission.

I also recommend creating a role called "TO" on your server. Everyone with this role will
be able to run commands requiring the TO permission. By default, only the creator and admins
will be able to run TO commands.

## Running a Tournament

1. [Invite auTO to your server.][setup]
2. Create your Challonge bracket and add players.
    1. Note: The player's tag in the Challonge bracket **must be** their Discord username. This is
    the username as it appears on the server you're on, and not including the "#1234" discriminator
    at the end.
3. Run `!auTO start [CHALLONGE_URL]` in the channel you want the tournament to run.
    1. auTO will dm you to ask for your Challonge API key. (This is deleted as soon as the
       tournament finishes.)
4. auTO will start calling matches!
5. Players can report their matches using the `!auTO report` command.

## Discord Commands

Commands are called by typing `!auTO [command]` in the channel. To run a TO command,
the user must be an admin or in a role called "TO".

| Command                 | Permissions | Description                                          |
|-------------------------|-------------|------------------------------------------------------|
| `start [CHALLONGE_URL]` | All         | Start TOing the bracket                              |
| `stop`                  | TO          | Stop TOing                                           |
| `results`               | TO          | Print results after tournament is finalized          |
| `rename tag @Player`    | TO          | Rename player to their Discord username              |
| `noshow @Player`        | TO          | Give player 5 minutes to post in the chat or be DQed |
| `update_tags`           | TO          | Get the latest tags from Challonge                   |
| `report 0-2`            | Players     | Report a match (reporter's score goes first)         |
| `matches`               | All         | Print current matches                                |
| `status`                | All         | Print how far along the tournament is                |
| `bracket`               | All         | Print the bracket URL                                |
| `help`                  | All         | Print the list of commands                           |

## Used By
* Dutch Melee Netplay
* 6 Buffer Saturday
* Hamburg SSB
* Chicagoland Melee
* Pacific Showdown Online
* MTV Melee

Please let me know if you use auTO for your tournament: I'd love to hear about it!

## Bug/Feature Requests

* [File an issue!](https://github.com/mtimkovich/auTO/issues)
* Message me on:
  * Twitter: [@DJSwerveGG][twitter]
  * Discord: DJSwerve#0567

## Author

Max "DJSwerve" Timkovich

[setup]: https://github.com/mtimkovich/auTO#setup
[invite]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=75840&scope=bot
[preview]: https://raw.githubusercontent.com/mtimkovich/auTO/master/img/auTO_preview.png
[twitter]: https://twitter.com/DJSwerveGG
