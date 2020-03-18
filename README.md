# auTO

**auTO** (pronounced *[Otto][otto]*) is a Discord bot for
running Melee netplay tournaments by calling matches and reporting results.

auTO can only manage tournaments ran through [Challonge](https://challonge.com) due to its more
comprehensive API compared to smash.gg's.

## Features
* List active matches.
* Ping players when it's time for them to play.
* Mark matches as in progress when players post netplay codes in the chat.
* Players can report their own matches without going through the TO.

## Install

Invite auTO to your Discord server by [clicking here][discord]. You'll need the "Manage Server"
permission.

## Discord Commands

Commands are called by typing `/auTO [command]` in the channel.

| Command               | Permissions | Description                                  |
|-----------------------|-------------|----------------------------------------------|
| start [CHALLONGE_URL] | TO          | Start TOing the bracket                      |
| stop                  | TO          | Stop TOing                                   |
| matches               | All         | Print current matches                        |
| report 0-2            | Players     | Report a match (reporter's score goes first) |

## Running a Tournament

1. [Invite auTO to your server.][discord]
2. Create your Challonge bracket and add players.
    a. NB: The player's tag in the Challonge bracket should match their Discord username *exactly*.
2. Run `/auTO start [CHALLONGE_URL]` in the channel you want the tournament to run.
    a. auTO will dm you to ask for your Challonge API key. (This is deleted as soon as the
       tournament finishes).
3. auTO will start calling matches!
4. Players can report their matches using the `/auTO report` command.

## Development

Requires Python 3.7+

## Author

Max "DJSwerve" Timkovich

[otto]: https://www.ssbwiki.com/Smasher:Silent_Wolf
[discord]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=10240&scope=bot
