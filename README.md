## Discord Music Ranking Bot

---

This discord.py based bot utilizes sqlite3 to store album/ep rankings for each user.
This could technically also be used for song rankings as well.

### Features

---

* Supports basic application commands
* Add, remove, or edit current entries in a users list
* Get basic statistics for a certain album/ep
* Display everyone's rankings in a channel, which updates whenever an update is performed
* Autofill suggestions based on currently established albums/eps

### CONFIG

---

There needs to be a file wherever you are hosting it in the same directory as main.py called config.py. This file needs to have variables TOKEN, GUILD, RANKING_CHANNEL, and COMMAND_CHANNEL. You can get these values by copying ids from discord itself. See config_example.py to see what it should look like

### Disclaimer

---

I am by no means good at programming, so this initial version is a very rough version of what I want the bot to be in the future. There will be features that bug that I will certainly try to fix. 

### To add list in the future

---

* /help command
* add an album changelog that specifies what changes everyone has made to their album list recently (toggleable feature)
* remove the references to me in case anyone else wants to use this for whatever reason
* add an undo feature
* add a top albums feature
* add even more error handling
* integrate with spotify api to get picture of albums as attachments for stat commands (cause it would be cool)
* MORE STATS
* implement a fix for if an artist and album have the same name or something of the like
* add channel variables and make more use of them than i currently do
* Limit rate at which commands can be used/make everything better (not necessary)
