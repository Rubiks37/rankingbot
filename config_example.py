# config_example.py

# discord bot token, should be a string
TOKEN = "YOUR_BOT_TOKEN"

# guild id should be an int and should be the id of the server you want the bot to send messages in
GUILD = 123123123123

# ranking channel should be an int and should be the id of the channel you want the bot to display album rankings in
RANKING_CHANNEL = 456456456456

# changelog_active is a boolean. change this to false if you dont want to have the changelog feature enabled
CHANGELOG_ACTIVE = True

# changelog channel should be the channel you want to display the changelog in
CHANGELOG_CHANNEL = 234590345

# if you want to use it on your server, it should be the owner's id
# (this allows the mods to run mod commands)
MOD_ID = 123456789

# see README for instructions on how to obtain these 3 elements to allow for interaction with spotify
SPOTIFY_CLIENT_ID = "SPOTIFY_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "SPOTIFY_CLIENT_SECRET"
SPOTIFY_REFRESH_TOKEN = "SPOTIFY_REFRESH_TOKEN"
