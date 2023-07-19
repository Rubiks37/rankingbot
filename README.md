## Discord Music Ranking Bot

---

This discord.py based bot utilizes sqlite3 to store album/ep rankings for each user.
This could technically also be used for song rankings as well.

### Features

---

* Creates a ranking table for every single user
* Supports basic application commands
* Add, remove, or edit entries in a users list
* Get basic statistics for a certain album/ep
* Display everyone's rankings in a channel, which updates whenever an update is performed
* Autofill suggestions based on currently established albums/eps

### CONFIG

---

There needs to be a file wherever you are hosting it in the same directory as main.py called config.py. See config_example.py to see what it should look like. The ids inside can be obtained by using developer mode within discord itself.

### Disclaimer

---

I am by no means good at programming, so this initial version is a very rough version of what I want the bot to be in the future. There will be features that bug that I will certainly try to fix. 

### Recent Additions, see all changes in commits (most recent at top)

---

* added autocomplete to edit/delete commands
* switched add choices to be autocompletes and added some methods to support
* added sync to /update, so i dont get rate limited whenever i debug
* added choices to stats and add commands

### To add list in the future

---

* /help command
* add an album changelog that specifies what changes everyone has made to their album list recently (toggleable feature)
* add an undo feature
* add a top albums feature
* add even more error handling
* integrate with spotify api to get picture of albums as attachments for stat commands (cause it would be cool)
* MORE STATS
* implement a fix for if an artist and album have the same name or something of the like

### How to get Spotify Tokens

---

You can create a spotify client id / secret here: https://developer.spotify.com/dashboard

Go to https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&scope=playlist-modify-public,playlist-modify-private,playlist-read-private,playlist-read-collaborative,user-library-modify,user-library-read&redirect_uri=http://localhost/callback/

You'll be redirected to a localhost page (that your browser can't find). Save ?code={CODE} from the URL

Take {SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET} => Convert to Base64 (e.g. https://www.base64encode.org/)

curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -H "Authorization: Basic {BASE64}" -d "grant_type=authorization_code&redirect_uri=http://localhost/callback/&code={CODE}" https://accounts.spotify.com/api/token

Save refresh token


### How to setup a dev environment

- python -m venv venv
- Activate venv (Windows: .\venv\Scripts\activate.ps1; Ubuntu: source ./venv/Scripts/activate)
- git clone https://github.com/mental32/spotify.py spotify_py
- Copy the folder "spotify" from spotify_py one layer up & delete the spotify_py folder
- cd spotify_py
- pip install -U .