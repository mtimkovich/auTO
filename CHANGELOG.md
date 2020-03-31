# Changelog

### 1.4.6
* Fix bug in ending tournaments.
* Split large matches messages.
* Fix round names for non-elimination tournaments.
* DQ using the Challonge API.

### 1.4.5
* Add `rename` command for fixing user tags.
* Catch 500 errors from Challonge.

### 1.4.0
* Add `noshow` command for auto-DQing!
* Report works for negative scores.
* auTO asks for the `add_reactions` permission.

### 1.3.3
* Fix round naming.
* Fix bug with `bracket`.
* Sort matches by play order.

### 1.3.2
* Delete previous matches post when matches is called.
* Expose 404 errors on tourney creation.

### 1.3.1
* Added check if user has "TO" role or is admin.
* Added `bracket` command.

### 1.3
* Use setuptools for package.
* Use `!` as prefix to be more familiar to Twitch ~~nerds~~ users.

### 1.2
* Check that all players in in the server before starting.
* Make commands case-insensitive.

### 1.1
* Only ping for new matches.
* Add timeout between reports to avoid duplicates.
