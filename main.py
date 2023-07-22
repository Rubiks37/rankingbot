import traceback

import discord
from discord import app_commands
from discord.app_commands import Choice
import sqlite3
import config
import statistics
from spotify_integration import get_album, spotify_close_conn, search_album

# set up Discord Bot with read and write message privileges, but without mentioning privileges
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions.none()
client = discord.Client(intents=intents, allowed_mentions=allowed_mentions)

# sets up command tree to have application commands run with
tree = app_commands.CommandTree(client)

# sets up guild/channel/permissions objects for later use
my_guild = discord.Object(config.GUILD)

# connect to SQLite3 Database (Just a server file)
conn = sqlite3.connect('rankings.db')


# boolean variable that will determine if the album changelog is active
# this is a future feature that i don't care enough to implement now
changelog = True


async def sync_commands():
    # Sync global & guild only commands
    await tree.sync()
    await tree.sync(guild=my_guild)

# all the following functions will be needed to help make the app commands more readable and easier to follow


# there will be an error if a final message is over 2000 characters
# this code will split it up
def split_message(content):
    if len(content) <= 2000:
        return [content]
    fragments = []
    while len(content) > 2000:
        cutoff = content[:2000].rfind('\n')
        fragments.append(content[:cutoff])
        content = content[cutoff:].lstrip()
    fragments.append(content)
    return fragments


# strips names down to alphanumeric characters - useful for people spelling things multiple ways
# if none is inputted, itll just append none
# TODO: MAKE THE RETURN A DICTIONARY RETURN MAPS INPUTS TO OUTPUTS TO INCREASE READABILITY
def strip_names(*args):
    final = []
    for arg in args:
        if arg is not None:
            arg = str(arg)
            final.append(''.join([letter.lower() for letter in arg if letter.isalnum()]))
        else:
            final.append(None)
    return final


# checks if a table exists for a given user using the sqlite master table
def table_exists(user_id):
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='user_data_{user_id}';")
    if cursor.fetchone():
        cursor.close()
        return True
    cursor.close()
    return False


# makes a table for a user if it doesn't exist and inserts them into active users (if not exists is just for redundancy)
def make_table(user_id):
    cursor = conn.cursor()
    if not table_exists(user_id):
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS users (user_ids INTEGER)''')
        cursor.execute(f'''INSERT INTO users (user_ids) VALUES ('{user_id}')''')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS user_data_{user_id} (artists TEXT, title TEXT, rating FLOAT)''')
    return


def make_album_master():
    cursor = conn.cursor()
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS album_master'''
                   f'''(artist TEXT, album TEXT, id TEXT, year INTEGER, image TEXT)''')
    cursor.close()
    return


# implementing a solution to the duplicate name problem, a master table of albums is needed.
# this uses the search functionality of spotify to find an album name, adds it to a table and returns it
# input list: list[artist, album]
async def add_to_album_master(artist: str, album: str):
    cursor = conn.cursor()
    make_album_master()
    row = get_album(artist, album)
    if row is None:
        raise LookupError(f"error: no matches found in spotify for {artist} - {album}")
    # this line will prevent duplicate albums from being added
    if get_album_master_row(album=row[1], artist=row[2], abort_early=True) is not None:
        return None
    year = row[3].split('-')[0]
    cursor.execute(f'''INSERT INTO album_master (artist, album, id, year, image) VALUES (?, ?, ?, ?, ?)''',
                   (row[2], row[1], row[0], year, row[4]))
    if cursor.rowcount < 1:
        raise LookupError("error: no rows were added, huh why what how???")
    cursor.close()
    conn.commit()
    return row


# function that removes a row from album_master (should be called on rows that are no longer in anyone's album ranking)
def remove_from_album_master(album: str, artist=None):
    row = get_album_master_row(artist=artist, album=album)
    if row is None:
        # if artist is none, then this will look weird, but whatever
        raise ValueError(f"error: could not find {artist} - {album} in album_master")
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM album_master WHERE artist = ? AND album = ?''', (row[0], row[1]))
    if cursor.rowcount < 1:
        raise LookupError("error: no rows were deleted from album_master, which is confusing idk why that happened")
    cursor.close()
    conn.commit()
    return


# gets every album stored in album_master and returns them
def get_album_master():
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM album_master''')
    output = cursor.fetchall()
    cursor.close()
    return output


# grabs the full master album list and tries to find an album stored inside of it.
# doubles as a does row exist function (set abort_early to true)
def get_album_master_row(album: str, artist=None, abort_early=False):
    final_list = []
    for row in get_album_master():
        row_album, album, row_artist, artist = strip_names(row[1], album, row[0], artist)
        if row_album in album and (artist is None or row_artist in artist):
            if abort_early:
                return row
            final_list.append(row)
    if len(final_list) > 1:
        if artist is not None:
            raise Exception("error: multiple entries of the same artist/album exist in album_master, please ping ruby")
        else:
            raise ValueError("error: duplicate albums detected in album_master, please enter an artist")
    if len(final_list) == 0:
        return None
    return final_list[0]


# this function is called via command and should refresh the master list
async def update_album_master():
    make_album_master()
    master_rows = get_album_master()
    user_rows = get_all_ranking_rows(unique=True)
    updated = 0
    for user_row in user_rows:
        # this next line is only possible since add_to_album_master does a check to
        # make sure that the inputted row is not already in album_master
        if await add_to_album_master(artist=user_row[0], album=user_row[1]) is not None:
            updated += 1
    for master_row in master_rows:
        if get_row_from_rankings(artist=master_row[0], album=master_row[1]) is None:
            remove_from_album_master(artist=master_row[0], album=master_row[1])
            updated += 1
    return updated


# gets a users ranked list in order by the rating
def get_rows_from_user(user_id):
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM user_data_{user_id} ORDER BY rating DESC''')
    rows = cursor.fetchall()
    cursor.close()
    return rows


# Gets ever single user_id, pulls all rows and returns them (yes its like a 4 dimensional list shut up)
def get_all_ranking_rows(unique=False):
    final_rows = []
    user_ids = get_users()
    for user_id in user_ids:
        rows = get_rows_from_user(user_id)
        if unique:
            [final_rows.append(row[slice(0, 2)]) for row in rows
             if (strip_names(row[0])[0] or strip_names(row[1])[0]) not in strip_names(final_rows)[0]]
        else:
            [final_rows.append(row) for row in rows]
    return final_rows


# transforms rows into nice looking string
def get_rankings(user_id):
    rows = get_rows_from_user(user_id)
    rankings_str = ''
    for i, row in enumerate(rows):
        ranking_str = f'{i + 1}. {row[0]} - {row[1]} ({row[2]})'
        rankings_str += ranking_str + '\n'
    return rankings_str


# looks through the table of users and generates a list of them
def get_users():
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM users''')
    rows = cursor.fetchall()
    cursor.close()
    user_ids = [row[0] for row in rows]
    return user_ids


# Updates the rankings channel by deleting all messages then resending them
async def display_rankings():
    conn.commit()
    channel = client.get_channel(config.RANKING_CHANNEL)
    users = get_users()
    final_message = ''
    # goes through every user who has had a table generated for them and adds their rankings to final_message
    for user_id in users:
        user = await client.fetch_user(user_id)
        rankings = get_rankings(user_id)
        final_message = final_message + f"\n\n{user.mention}'s rankings:\n{rankings}\n"
    # deletes all the messages current in the channel (that were made by the bot)
    async for message in channel.history():
        if message.author == client.user:
            await message.delete()
    # if final_message is over 2000 characters and the bot tries to send it, it will encounter an error.
    # instead, we get an array of <2000 character messages using split_message()
    fragments = split_message(final_message)
    # then we just send the fragments
    for msg in fragments:
        await channel.send(msg)
    return "i successfully updated everyone's album rankings maybe probably"


# adds a row to a table for a given user
async def add_row(user_id, artist: str, album: str, rating: float):
    cursor = conn.cursor()
    make_table(user_id)
    if get_row_from_rankings(album=album, artist=artist, user_id=user_id) is not None:
        raise ValueError("error: you cannot add 2 of the same album to your rankings")
    artist, album = [artist.strip(), album.strip()]
    # we can just call add_to_album_master since it does a check to ensure that the album is not already in album_master
    await add_to_album_master(artist=artist, album=album)
    row = get_album_master_row(artist=artist, album=album)
    # strip the message of extraneous characters, add to the table
    cursor.execute(f'''INSERT INTO user_data_{user_id} (artists, title, rating)'''
                   f'''VALUES(?, ?, ?)''', (row[0], row[1], rating))
    if cursor.rowcount < 1:
        raise LookupError("error: no rows were added, which is confusing idk why that happened")
    conn.commit()
    cursor.close()
    return f"i successfully added {row[0]} - {row[1]} to your rankings"


# this just splits a message up by new lines and calls add_row until there are no more new lines
# KNOWN BUG (not sure how to fix though) - artists/albums with commas cannot be bulk added, need to be single added
def add_row_bulk(user_id, content):
    make_table(user_id)
    rows = content.split("\n")
    # check for incorrect formatting/blank entries
    for i, row in enumerate(rows):
        if len(row) != 3:
            raise SyntaxError(f"incorrect formatting (row {i} did not have 3 entries")
        for item in row.split(',').strip():
            if item is None:
                raise SyntaxError(f"incorrect formatting (row {i} has a blank entry")
        # adds row if all checks succeed
        row_to_add = row.split(',').strip()
        add_row(user_id, row_to_add[0], row_to_add[1], row_to_add[2])
    return f"i successfully added {len(rows)} albums to your rankings"


# edits a row in a given table
def edit_row(user_id, row, rating: float):
    make_table(user_id)
    # prevent an index out of bound exception
    # update rating value in corresponding row
    cursor = conn.cursor()
    cursor.execute(f'''UPDATE user_data_{user_id} SET rating = {rating}'''
                   f''' WHERE artists = ? AND title = ?''', (row[0], row[1]))
    if cursor.rowcount < 1:
        raise LookupError("error: no rows were edited, which is confusing idk why that happened")
    conn.commit()
    return f"i successfully edited {row[0]} - {row[1]} to a {rating}/10.0"


# removes a row from a certain users table
async def remove_row(user_id, row):
    make_table(user_id)
    cursor = conn.cursor()
    # prevent an index out of bound exception
    cursor.execute(f"DELETE FROM user_data_{user_id} "f"WHERE artists = ? AND title = ?", (row[0], row[1]))
    conn.commit()
    cursor.close()
    if cursor.rowcount < 1:
        raise LookupError("error: no rows were deleted, whyy?????")
    else:
        await update_album_master()
        return f"i successfully deleted {row[0]} - {row[1]} from your list"


# takes an album and (maybe) an artist in and checks if it finds them in a ranking table
# if it finds one, it will return the full row that it was on.
# also can take a user_id to only search rows specific to that user.
# doubles as a check for exists function
def get_row_from_rankings(album: str, artist: str = None, user_id=0):
    if user_id == 0:
        rows = get_all_ranking_rows(unique=True)
    else:
        rows = get_rows_from_user(user_id=user_id)
    final_list = []
    # problem - if the user has an album twice in their album rankings, final_list will have a length greater than 1
    # solution - if artist is not entered, tell them to enter an artist
    # if artist is entered and the problem is encountered, return the first entry, it should be good enough
    for row in rows:
        row_album, album, row_artist, artist = strip_names(row[1], album, row[0], artist)
        if row_album in album and (artist is None or row_artist in artist):
            final_list.append([row[0], row[1]])
    if len(final_list) > 1 and artist is None:
        raise ValueError("error: duplicate albums detected in your list, please enter an artist")
    if len(final_list) == 0:
        return None
    return final_list[0]


# finds every rating that is associated with an album
# goes through every table and gets the alphanumeric album name and then compares
# if true, adds the rating associated to a list and returns the list
def get_album_ratings(album, artist=None):
    album, artist = strip_names(album, artist)
    ratings = []
    for row in get_all_ranking_rows(unique=False):
        row_album, row_artist = strip_names(row[1], row[0])
        if row_album in album and (artist is None or row_artist in artist):
            ratings.append(row[2])
    return ratings


# we are only given an album or an artist, so we find the full formatted title using get_row
# we can use those to get album rankings, and then run some simple statistics and print it (could add more statistics)
def get_album_stats(album, artist=None):
    row = get_album_master_row(album=album, artist=artist)
    if row is None:
        raise LookupError('error: no albums found matching the name \"' + album + '\"')
    ratings = get_album_ratings(album=album)
    num_ratings = len(ratings)
    mean = round(statistics.mean(ratings), 2)
    final_string = f"Artist: {row[0]}\nAlbum: {row[1]}\nNumber of Ratings: {num_ratings}\nMean: {mean}"
    if len(ratings) > 1:
        std_deviation = round(statistics.stdev(ratings), 2)
        final_string += f"\nStandard Deviation: {std_deviation}"
    return final_string


# AUTOCOMPLETE AND CHOICES SECTION-----------------------------------------------------------------------------------
# gets a list of artists in album_master and returns a list of choices for use in autocomplete
async def get_artist_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [row[0] for row in get_album_master()]
    return [Choice(name=artist, value=artist)
            for artist in final_list if strip_names(current)[0] in strip_names(artist)[0]]


# same as above, but it does albums with autocomplete
async def get_album_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [row[1] for row in get_album_master()]
    return [Choice(name=album, value=album)
            for album in final_list if strip_names(current)[0] in strip_names(album)[0]]


# gets a formatted list of choices of artist - album using spotify search
async def get_spotify_artist_album_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    results = search_album(current)
    return [Choice(name=f"{entry.artists[0].name} - {entry.name}",
                   value=f"{entry.artists[0].name} ----- {entry.name}") for entry in results]


# gets a formatted list of choices of artist - album using album_master
async def get_artist_album_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [[f"{row[0]} - {row[1]}", f"{row[0]} ----- {row[1]}"] for row in get_album_master()]
    return [Choice(name=entry[0], value=entry[1])
            for entry in final_list if current.lower() in entry[0].lower()]


# gets formatted choices for artist/album when editing/deleting rows from the list
async def get_artist_album_autocomplete_specific(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [[f"{row[0]} - {row[1]}", f"{row[0]} ----- {row[1]}"] for row in get_rows_from_user(interaction.user.id)]
    return [Choice(name=entry[0], value=entry[1])
            for entry in final_list if current.lower() in entry[0].lower()]


# whenever the bot is ready, it'll log this
@client.event
async def on_ready():
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="your favourite music"))


# APPLICATION COMMAND SECTION---------------------------------------------------------------------------------------
# UPDATE COMMAND - rewrites the rankings in album rankings
@tree.command(name="update", description="update the album rankings", guild=my_guild)
async def update(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(await display_rankings())
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# ADDMANUAL COMMAND - adds an album to a users ranking with no search
@tree.command(name='addmanual', description='add an album to your rankings', guild=my_guild)
@app_commands.describe(artist="the name of the artist",
                       album="the name of the album",
                       rating="the rating of the album")
@app_commands.autocomplete(artist=get_artist_autocomplete, album=get_album_autocomplete)
async def addmanual(interaction: discord.Interaction, artist: str, album: str, rating: float):
    try:
        await interaction.response.send_message(
            await add_row(user_id=interaction.user.id, artist=artist, album=album, rating=rating))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# ADD COMMAND - uses spotify + autocomplete to find albums
@tree.command(name='add', description='add an album to your rankings with the help of spotify search', guild=my_guild)
@app_commands.describe(searchkeywords="type in keywords for your search here")
@app_commands.autocomplete(searchkeywords=get_spotify_artist_album_autocomplete)
async def add(interaction: discord.Interaction, searchkeywords: str, rating: float):
    try:
        if len(searchkeywords.split("-----")) != 2:
            raise ValueError("error: improper formatting, please click on an autocomplete option or use addmanual")
        artist, album = [enter.strip() for enter in searchkeywords.split("-----")]
        await interaction.response.send_message(
        await add_row(user_id=interaction.user.id, artist=artist, album=album, rating=rating))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# BULK ADD COMMAND - add command that can be done with multiple albums at once (VERY PICKY FORMATTING)
@tree.command(name="addbulk", description='add multiple albums to your rankings', guild=my_guild)
@app_commands.describe(albums="the full list of albums you want to add. it should be in this format"
                              "\nArtist, Album Title, Rating (Next Line)")
async def addbulk(interaction: discord.Interaction, albums: str):
    try:
        await interaction.response.send_message(add_row_bulk(interaction.user.id, albums))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# EDIT COMMAND - edits the ranking of a certain album on a users list
@tree.command(name='edit', description='edit a rating on an album', guild=my_guild)
@app_commands.describe(entry="the artist - album whos rating you want to change",
                       rating="your new rating of the album (0-10)")
@app_commands.autocomplete(entry=get_artist_album_autocomplete_specific)
async def edit(interaction: discord.Interaction, entry: str, rating: float):
    try:
        if len(entry.split("-----")) != 2:
            raise ValueError("error: improper formatting, please click on an autocomplete option")
        artist, album = [enter.strip() for enter in entry.split("-----")]
        await interaction.response.send_message(edit_row(
            interaction.user.id, get_row_from_rankings(album=album, user_id=interaction.user.id), rating))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# REMOVE COMMAND - removes an album from a users list
@tree.command(name="remove", description="remove an album from your ranking", guild=my_guild)
@app_commands.describe(entry="the artist - album you want to remove (see autocomplete)")
@app_commands.autocomplete(entry=get_artist_album_autocomplete_specific)
async def remove(interaction: discord.Interaction, entry: str):
    try:
        if len(entry.split("-----")) != 2:
            raise ValueError("error: improper formatting, please click on an autocomplete option")
        artist, album = [enter.strip() for enter in entry.split("-----")]
        await interaction.response.send_message(await remove_row(
            interaction.user.id, get_row_from_rankings(album=album, artist=artist, user_id=interaction.user.id)))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# COVER COMMAND - displays the cover of the album
@tree.command(name="cover", description="displays the cover of an album", guild=my_guild)
@app_commands.describe(entry="the album - artist you want to see the cover of (see autocomplete)")
@app_commands.autocomplete(entry=get_spotify_artist_album_autocomplete)
async def cover(interaction: discord.Interaction, entry: str):
    try:
        artist, album = [enter.strip() for enter in entry.split("-----")]
        row = get_album_master_row(album=album, artist=artist)
        if row is None:
            row = get_album(artist, album)
        embed = discord.Embed(title=album, description=f"{artist} - {album}")
        embed.set_image(url=row[4])
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# STATS COMMAND - displays stats for a certain album based on current rankings
@tree.command(name='stats', description='find out stats about an album', guild=my_guild)
@app_commands.describe(entry="the artist - album you are trying to get (see autocomplete)")
@app_commands.autocomplete(entry=get_artist_album_autocomplete)
async def stats(interaction: discord.Interaction, entry: str):
    try:
        artist, album = [enter.strip() for enter in entry.split("-----")]
        row = get_album_master_row(album=album, artist=artist)
        if row is None:
            raise ValueError("error: you cannot get stats for an album that is not ranked by anyone")
        album_cover = row[4]
        embed = discord.Embed(title=album, description=get_album_stats(album=row[1], artist=row[0]))
        embed.set_image(url=album_cover)
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# SYNC COMMAND - calls tree.sync to sync new changes to application commands
@tree.command(name='sync', description='MOD ONLY: syncs the application commands')
@app_commands.checks.has_role(config.MOD_ID)
async def sync(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        await sync_commands()
        await interaction.followup.send(content="sync successful")
    except Exception as error:
        await interaction.followup.send(content=error)


# UPDATEALBUMMASTER - calls update_album_master
@tree.command(name='updatealbummaster', description='MOD ONLY: updates album master')
@app_commands.checks.has_role(config.MOD_ID)
async def updatealbummaster(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(
            content=f"successfully updated {await update_album_master()} entries in album_master")
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# DEBUG: SQLITE3 - allows mods to run SQL commands for debugging
@tree.command(name='sqlite3', description='DEBUG: FOR MODS ONLY, to execute sql statements', guild=my_guild)
@app_commands.describe(command="the command to execute, be very careful about this")
@app_commands.checks.has_role(config.MOD_ID)
async def sqlite3(interaction: discord.Interaction, command: str):
    cursor = conn.cursor()
    try:
        cursor.execute(command)
        await interaction.response.send_message(content=cursor.fetchall())
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)
    finally:
        cursor.close()


# DEBUG: GETALBUMMASTER - displays album_master,
@tree.command(name='getalbummaster', description='DEBUG: FOR MODS ONLY, to display album_master for debugging', guild=my_guild)
@app_commands.describe()
@app_commands.checks.has_role(config.MOD_ID)
async def getalbummaster(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(content=get_album_master())
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


@client.event
async def on_shutdown():
    conn.commit()
    conn.close()
    spotify_close_conn()


TOKEN = config.TOKEN
client.run(TOKEN)
