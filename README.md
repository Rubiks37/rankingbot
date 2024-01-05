## Discord Music Ranking Bot

---

This discord.py based bot utilizes sqlite3 to store album/ep rankings for each user.
This could technically also be used for song rankings as well.

### Features

---

* Creates a ranking table for every single user
* Add, remove, or edit entries in a users list
* Get basic statistics for a certain album/ep
* Display everyone's rankings in a channel, which updates whenever an update is performed
* Gets the top albums by rating and standard deviation for a particular year (or no year)
* Allows users to keep track of albums they want to listen to (homework)
* Displays recent changes to everyones albums list (changelog)
* Supports application commands
* Autofill suggestions based on established albums/eps and spotify search

### CONFIG

---

PLEASE SEE CONFIG_EXAMPLE.json FOR A SAMPLE OF THE CONFIG FILE
There needs to be a file wherever you are hosting it in the same directory as main.py called config.json.
The discord ids inside can be obtained by using developer mode within discord itself. The spotify ids can be obtained using the instructions below.
If you previously used a config.py file, there is a function in the new config.py file to convert the old file to a json.

### Disclaimer

---

I'm looking at revisitng a lot of the code here because it is kind of badly written, I'm a bit more experienced now and have a bit more riding on how well I can program things like this, so I'll revisit it in a while.

### Recent Additions, see all changes in commits (most recent at top)

---
* complete reorganization to increase readability
* convert settings to json
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
