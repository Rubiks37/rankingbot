import discord
from discord import app_commands
from discord.app_commands import Choice
import sqlite3
import config
import statistics

# set up Discord Bot with read and write message privileges, but without mentioning privileges
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions.none()
client = discord.Client(intents=intents, allowed_mentions=allowed_mentions)

# sets up command tree to have application commands run with
tree = app_commands.CommandTree(client)

# sets up guild/channel/permissions objects for later use
guild = discord.Object(config.GUILD)

# connect to SQLite3 Database (Just a server file)
conn = sqlite3.connect('rankings.db')


# boolean variable that will determine if the album changelog is active
# this is a future feature that i don't care enough to implement now
changelog = True

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
def strip_names(*args):
    final = []
    for arg in args:
        arg = str(arg)
        final.append(''.join([letter.lower() for letter in arg if letter.isalnum()]))
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
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS user_data_{user_id}
        (artists TEXT, title TEXT, rating FLOAT)''')
    return


# gets the ranked list in order by the rating
def get_rows(user_id):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM user_data_{user_id} ORDER BY rating DESC")
    rows = cursor.fetchall()
    cursor.close()
    return rows


# Gets ever single user_id, pulls all rows and returns them (yes its like a 4 dimensional list shut up)
def get_every_row(unique: bool):
    final_rows = []
    user_ids = get_users()
    for user_id in user_ids:
        rows = get_rows(user_id)
        if unique:
            [final_rows.append(row[slice(0, 2)]) for row in rows
             if (strip_names(row[0])[0] or strip_names(row[1])[0]) not in strip_names(final_rows)[0]]
        else:
            [final_rows.append(row) for row in rows]
    return final_rows


# transforms rows into nice looking string
def get_rankings(user_id):
    rows = get_rows(user_id)
    rankings_str = ''
    for i, row in enumerate(rows):
        ranking_str = f'{i + 1}. {row[0]} - {row[1]} ({row[2]})'
        rankings_str += ranking_str + '\n'
    return rankings_str


# looks through the table of users and generates a list of them
def get_users():
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users")
    rows = cursor.fetchall()
    cursor.close()
    user_ids = [row[0] for row in rows]
    return user_ids


# Updates the rankings channel by deleting all messages then resending them
async def display_rankings():
    conn.commit()
    await tree.sync(guild=guild)
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
def add_row(user_id, content):
    cursor = conn.cursor()
    make_table(user_id)
    # split content and check for errors
    if len(content) != 3:
        raise SyntaxError("error: your message in incorrect format")
    for item in content:
        if item is None:
            raise SyntaxError("error: one or more of your command parameters is empty")
    # strip the message of extraneous characters, add to the table
    cursor.execute(f'''INSERT INTO user_data_{user_id} (artists, title, rating) 
                 VALUES('{content[0].strip()}', '{content[1].strip()}', '{content[2]}')''')
    conn.commit()
    cursor.close()
    return f"i successfully added {content[0]} - {content[1]} to your rankings"


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
        add_row(user_id, row)
    return f"i successfully added {len(rows)} albums to your rankings"


# edits a row in a given table
def edit_row(user_id, ranking_str, rating_str):
    make_table(user_id)
    rows = get_rows(user_id)
    # assign each variable to the row in rankings
    index = int(ranking_str) - 1
    rating = float(rating_str)
    # prevent an index out of bound exception
    if len(rows) - 1 < index or index < 0:
        raise IndexError("error: an invalid index was entered (probably because it doesn't exist)")
    # update rating value in corresponding row
    conn.execute(f"UPDATE user_data_{user_id} SET rating = {rating} "
                 f"WHERE artists = ? AND title = ? AND rating = ?",
                 (rows[index][0], rows[index][1], rows[index][2]))
    conn.commit()
    return f"i successfully edited {rows[index][0]} - {rows[index][1]} to a {rating}/10.0"


# removes a row from a certain users table
def remove_row(user_id, index):
    make_table(user_id)
    rows = get_rows(user_id)
    index = int(index) - 1
    cursor = conn.cursor()
    # prevent an index out of bound exception
    if len(rows) - 1 < index or index < 0:
        raise IndexError("error: an invalid index was entered (probably because it doesn't exist)")
    affected = cursor.execute(f"DELETE FROM user_data_{user_id} "
                              f"WHERE artists = ? AND title = ? AND rating = ?",
                              (rows[index][0], rows[index][1], rows[index][2]))
    conn.commit()
    cursor.close()
    if affected is None:
        raise LookupError("error: no rows were deleted, idk why though")
    else:
        return f"i successfully deleted {rows[index][0]} - {rows[index][1]} from your list"


# this takes an input from strip_names, usually an album name or an artist name
# and tries to find a human-readable name in one of the lists.
# if it finds one, it will return the full row that it was on. NEEDS TO BE IMPROVED ON LATER
def transform_readable(name):
    name = strip_names(name)[0]
    for row in get_every_row(True):
        for item in row:
            if strip_names(item)[0] == name:
                return row
    return None


# finds every rating that is associated with an album
# goes through every table and gets the alphanumeric album name and then compares
# if true, adds the rating associated to a list and returns the list
def get_album_ratings(album_name):
    album_name = strip_names(album_name)[0]
    ratings = []
    print("looking for " + album_name + " across all rankings")
    output = get_every_row(unique=False)
    for row in output:
        if strip_names(row[1])[0] in album_name:
            print("found a rating")
            ratings.append(row[2])
    print(ratings)
    return ratings


# we are only given an album or an artist, so we find the full formatted title using transform_readable
# we can use those to get album rankings, and then run some simple statistics and print it (could add more statistics)
def get_album_stats(content):
    title = strip_names(content)[0]
    row = transform_readable(title)
    if row is None:
        raise LookupError('error: no albums found matching the name \"' + content + '\"')
    ratings = get_album_ratings(row[1])
    num_ratings = len(ratings)
    mean = round(statistics.mean(ratings), 2)
    final_string = f"Artist: {row[0]}\nAlbum: {row[1]}\nNumber of Ratings: {num_ratings}\nMean: {mean}"
    if len(ratings) > 1:
        std_deviation = round(statistics.stdev(ratings), 2)
        final_string += f"\nStandard Deviation: {std_deviation}"
    return final_string


# returns a list of choice objects that can be used to give choices to application commands (album or artist)
# mode specifies if we need a list of artists (0) or albums (1)
def get_name_choices(mode: int):
    list_reference = [row[mode] for row in get_every_row(True)]
    final_list = []
    for row in list_reference:
        final_list.append(Choice(name=str(row), value=str(row)))
    return final_list


# same as above, but it does artists with autocomplete
async def get_artist_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [row[0] for row in get_every_row(True)]
    return [Choice(name=artist, value=artist)
            for artist in final_list if strip_names(current)[0] in strip_names(artist)[0]]


# same as above, but it does albums with autocomplete
async def get_album_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = [row[1] for row in get_every_row(True)]
    return [Choice(name=album, value=album)
            for album in final_list if current.lower() in album.lower()]


# this does index autocomplete, but it doesnt adjust to current like the other autocompletes do, (but its fine)
async def get_index_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    user_id = interaction.user.id
    return [Choice(name=str(index), value=index)
            for index in range(0, len(get_rows(user_id)))]


# whenever the bot is ready, it'll log this
@client.event
async def on_ready():
    print('hi im here to help')


# APPLICATION COMMAND SECTION
# UPDATE COMMAND
@tree.command(name="update", description="update the album rankings", guild=guild)
async def update(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(await display_rankings())
    except Exception as error:
        await interaction.response.send_message(content=error)


# ADD COMMAND (single adding only)
@tree.command(name='add', description='add an album to your rankings', guild=guild)
@app_commands.describe(artist="the name of the artist",
                       album="the name of the album",
                       rating="the rating of the album")
@app_commands.autocomplete(artist=get_artist_autocomplete, album=get_album_autocomplete)
async def add(interaction: discord.Interaction, artist: str, album: str, rating: float):
    try:
        await interaction.response.send_message(add_row(interaction.user.id, [artist, album, rating]))
        await display_rankings()
    except Exception as error:
        await interaction.response.send_message(content=error)


# BULK ADD COMMAND
@tree.command(name='add_bulk', description='add multiple albums to your rankings', guild=guild)
@app_commands.describe(albums="the full list of albums you want to add. it should be in this format"
                              "\nArtist, Album Title, Rating (Next Line)")
async def add_bulk(interaction: discord.Interaction, albums: str):
    try:
        await interaction.response.send_message(add_row_bulk(interaction.user.id, albums))
        await display_rankings()
    except Exception as error:
        await interaction.response.send_message(content=error)


# EDIT COMMAND
@tree.command(name='edit', description='edit a rating on an album', guild=guild)
@app_commands.describe(ranking=f"the ranking of the album you want to edit on your rankings "
                               f"(see albums-eps-of-2023 for rankings)",
                       rating="your new rating of the album (0-10)")
@app_commands.autocomplete(ranking=get_index_autocomplete)
async def edit(interaction: discord.Interaction, ranking: int, rating: float):
    make_table(interaction.user.id)
    try:
        await interaction.response.send_message(edit_row(interaction.user.id, ranking, rating))
        await display_rankings()
    except Exception as error:
        await interaction.response.send_message(content=error)


# REMOVE COMMAND
@tree.command(name="remove", description="remove an album from your ranking", guild=guild)
@app_commands.describe(ranking="the ranking of the album you want to remove on your rankings (see albums-eps-of-2023)")
@app_commands.autocomplete(ranking=get_index_autocomplete)
async def remove(interaction: discord.Interaction, ranking: int):
    make_table(interaction.user.id)
    try:
        await interaction.response.send_message(remove_row(interaction.user.id, ranking))
        await display_rankings()
    except Exception as error:
        await interaction.response.send_message(error)


# STATS COMMAND
@tree.command(name='stats', description='find out stats about an album', guild=guild)
@app_commands.describe(title="the title of the album you are trying to get stats for")
@app_commands.autocomplete(title=get_album_autocomplete)
async def stats(interaction: discord.Interaction, title: str):
    try:
        await interaction.response.send_message(get_album_stats(title))
    except Exception as error:
        await interaction.response.send_message(error)


# DEBUG: SQLITE3
@tree.command(name='sqlite3', description='DEBUG: FOR MODS ONLY, to execute sql statements', guild=guild)
@app_commands.describe(command="the command to execute, be very careful about this")
@app_commands.checks.has_role(config.MOD_ID)
async def sqlite3(interaction: discord.Interaction, command: str):
    try:
        cursor = conn.cursor()
        cursor.execute(command)
        await interaction.response.send_message(content=cursor.fetchall())
    except Exception as error:
        await interaction.response.send_message(content=error)
    finally:
        cursor.close()


@client.event
async def on_shutdown():
    conn.commit()
    conn.close()

TOKEN = config.TOKEN
client.run(TOKEN)
