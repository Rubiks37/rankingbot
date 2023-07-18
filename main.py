import discord
from discord import app_commands
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
guild = discord.Object(config.GUILD)

# connect to SQLite3 Database (Just a server file)
conn = sqlite3.connect('rankings.db')


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
    print(user_ids)
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
def add_row(user_id, content):
    cursor = conn.cursor()
    make_table(user_id)
    # split content and check for errors
    content = content.split(',')
    if len(content) != 3:
        raise SyntaxError("error: your message in incorrect format")
    content[0] = content[0].strip('+add ')
    for cont in content:
        if cont is None:
            raise SyntaxError("error: one or more of your command parameters is empty")
    # strip the message of extraneous characters, add to the table
    content = [thing.strip() for thing in content]
    cursor.execute(f'''INSERT INTO user_data_{user_id} (artists, title, rating) 
                 VALUES('{content[0]}', '{content[1]}', '{content[2]}')''')
    conn.commit()
    cursor.close()
    return f"i successfully added {content[0]} - {content[1]} to your rankings"


# this just splits a message up by new lines and calls add_row until there are no more new lines
def add_row_bulk(user_id, content):
    make_table(user_id)
    adds = content.split("\n")
    # check for incorrect formatting/blank entries
    for i, row in enumerate(adds):
        if len(row) != 3:
            raise SyntaxError(f"incorrect formatting (row {i} did not have 3 entries")
        for item in row.split(',').strip():
            if item is None:
                raise SyntaxError(f"incorrect formatting (row {i} has a blank entry")
        # adds row if all checks succeed
        add_row(user_id, row)
    return f"i successfully added {len(adds)} albums to your rankings"


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
    users = get_users()
    for user_id in users:
        output = get_rows(user_id)
        for row in output:
            for item in row:
                if strip_names(item)[0] == name:
                    return row
    return None


# finds every rating that is associated with an album
# goes through every table and gets the alphanumeric album name and then compares
# if true, adds the rating associated to a list and returns the list
def get_album_ratings(album_name):
    album_name = strip_names(album_name)[0]
    users = get_users()
    ratings = []
    for user_id in users:
        print("looking for " + album_name + " from " + str(user_id))
        output = get_rows(user_id)
        for row in output:
            if strip_names(row[1])[0] in album_name:
                print("found a rating")
                ratings.append(row[2])
                break
    print(ratings)
    return ratings


# we are only given an album or an artist, so we find the full formatted title using transform_readable
# we can use those to get album rankings, and then run some simple statistics and print it (could add more statistics)
def get_album_stats(content):
    title = strip_names(content)[0]
    row = transform_readable(title)
    if row is None:
        raise LookupError('error: no albums found matching the name ' + content)
    ratings = get_album_ratings(row[1])
    num_ratings = len(ratings)
    mean = round(statistics.mean(ratings), 2)
    final_string = f"Artist: {row[0]}\nAlbum: {row[1]}\nNumber of Ratings: {num_ratings}\nMean: {mean}"
    if len(ratings) > 1:
        std_deviation = round(statistics.stdev(ratings), 2)
        final_string += f"\nStandard Deviation: {std_deviation}"
    return final_string


# whenever the bot is ready, it'll send this
@client.event
async def on_ready():
    await tree.sync(guild=guild)
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
async def add(interaction: discord.Interaction, artist: str, album: str, rating: float):
    try:
        await interaction.response.send_message(add_row(interaction.user.id, f"{artist}, {album}, {rating}"))
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
@app_commands.describe(ranking=f"the ranking of the album you want to edit on your rankings (see albums-eps-of-2023)",
                       rating="your new rating of the album")
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
async def remove(interaction: discord.Interaction, ranking: int):
    make_table(interaction.user.id)
    try:
        await interaction.response.send_message(remove_row(interaction.user.id, ranking))
        await display_rankings()
    except Exception as error:
        await interaction.response.send_message(error)


# STATS COMMAND
@tree.command(name='stats', description='find out stats about an album', guild=guild)
@app_commands.describe(title="the title of the artist or album you are trying to get stats for")
async def stats(interaction: discord.Interaction, title: str):
    try:
        await interaction.response.send_message(get_album_stats(title))
    except Exception as error:
        await interaction.response.send_message(error)


# DEBUG: FIND_OTHER
@tree.command(name='find_other', description='TEST - given an album(artist), finds an artist(album) associated', guild=guild)
async def find_other(interaction: discord.Interaction, title: str):
    try:
        await interaction.response.send_message(transform_readable(strip_names(title))[0])
    except Exception as error:
        await interaction.response.send_message(error)


# DEBUG: SQLITE3
@tree.command(name='sqlite3', description='DEBUG: FOR RUBY ONLY, to execute sql statements', guild=guild)
@app_commands.describe(command="the command to execute, be very careful about this")
async def sqlite3(interaction: discord.Interaction, command: str):
    if interaction.user.id == config.RUBY_ID:
        cursor = conn.cursor()
        try:
            cursor.execute(command)
            await interaction.response.send_message(content=cursor.fetchall())
        except Exception as error:
            await interaction.response.send_message(content=error)
        finally:
            cursor.close()
    else:
        await interaction.response.send_message(content="you are not ruby so you may not use this command")


@client.event
async def on_shutdown():
    conn.commit()
    conn.close()

TOKEN = config.TOKEN
client.run(TOKEN)
