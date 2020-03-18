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

To add auTO to your Discord [click here][discord]. You'll need the "Manage Server" permission on
the server you want to add auTO to.

## Discord Commands

* `/auTO start [URL]` - Start TOing the given Challonge bracket.
* `/auTO stop` - Stop TOing.
* `/auTO matches` - Print current matches.
* `/auTO report 0-2` - Report your match.

## Development

Requires Python 3.7+

## Author

Max "DJSwerve" Timkovich

[otto]: https://www.ssbwiki.com/Smasher:Silent_Wolf
[discord]: https://discordapp.com/api/oauth2/authorize?client_id=687888371556548680&permissions=10240&scope=bot
