## Discord Music Ranking Bot

---

This discord.py based bot utilizes sqlite3 to store album/ep rankings for each user.
This could technically also be used for song rankings as well.

### Features

---

* Creates a ranking table for every single user
* Add, remove, or edit entries in a users list
* Get basic statistics for a certain album/ep
* Display everyone's rankings in a channel, which updates whenever an update is performed (can display different years in different channels)
* Gets the top albums by rating/standard deviation for a particular year (or no year)
* Allows users to keep track of albums they want to listen to (homework)
* Displays recent changes to everyone's albums list (changelog)
* Supports application commands
* Autofill suggestions based on established albums/eps and spotify search

### CONFIG

---

PLEASE SEE CONFIG_EXAMPLE.json FOR A SAMPLE OF THE CONFIG FILE
There needs to be a file wherever you are hosting it in the same directory as main.py called config.json.
The discord ids inside can be obtained by using developer mode within discord itself. The spotify ids can be obtained using the instructions below.

Here's a helper for all of the settings in config
* Token - your discord bot token
* Guild - the id of your discord server
* Ranking_Channel - a dictionary which maps the year that albums came out in to the channel id that their associated rankings will be displayed in
* Changelog_Active - a boolean with whether you want the changelog feature enabled or not
* Changelog_Channel - the id of the channel you want to house changelog alerts
* Mod_ID - the ID of the administrator/moderator role in your server
* The spotify ones are explained below


### Disclaimer

---

This bot is designed for albums. I really have no idea how it will handle songs.
If you want to use this bot, you have to host it yourself (unfortunately).

### Recent Additions, see all changes in commits (most recent at top)

---
* added the ability for different years rankings to be displayed in different channels
* complete reorganization to increase readability
* converted settings to json
* added new app command /top_albums which gets top albums for a particular year
* added changelog
* added autocomplete with homeworkbot
* added a year filter, so only albums of the current year will be displayed
* integrated homework bot (add/remove albums for you/others to listen to)
* added autocomplete integration with spotify
* added spotify compatibility with /add and /cover commands


### To add list in the future

---
* allow for commands to change settings
* /help command
* add an undo feature
* add even more error handling

### How to get Spotify Tokens

---

You can create a spotify client here: https://developer.spotify.com/dashboard
Get the client_id and client_secret from your client.

For redirect url, you should use http://localhost/callback

Go to https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&scope=playlist-modify-public,playlist-modify-private,playlist-read-private,playlist-read-collaborative,user-library-modify,user-library-read&redirect_uri=http://localhost/callback/
Make sure to substitute {SPOTIFY_CLIENT_ID} for the id obtained from the developer dashboard

You'll be redirected to a localhost page (that your browser can't find). Save ?code={CODE} from the URL

Take your SPOTIFY_CLIENT_ID:SPOTIFY_CLIENT_SECRET => Convert to Base64 (e.g. https://www.base64encode.org/)

curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -H "Authorization: Basic {BASE64}" -d "grant_type=authorization_code&redirect_uri=http://localhost/callback/&code={CODE}" https://accounts.spotify.com/api/token
Again, making sure to substitute {BASE64} and {CODE} in for the values obtained earlier
(If on windows, you may need to use curl.exe)

Save refresh token


### How to set up a dev environment

* python -m venv venv
* Activate venv (Windows: .\venv\Scripts\activate.ps1; Ubuntu: source ./venv/Scripts/activate)
* git clone https://github.com/mental32/spotify.py spotify_py
* cd spotify_py
* pip install -U .
* Copy the folder "spotify" from spotify_py one layer up & delete the spotify_py folder
