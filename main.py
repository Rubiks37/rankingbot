from datetime import datetime
import traceback
import discord
from discord import app_commands
from discord.app_commands import Choice
import sqlite3
import config
import statistics
import spotify_integration as spotify
import homework


# set up Discord Bot with read and write message privileges, but without mentioning privileges
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions.none()
client = discord.Client(intents=intents, allowed_mentions=allowed_mentions)

# sets up command tree to have application commands run with
tree = app_commands.CommandTree(client)

# sets up guild/channel/permissions objects for later use
my_guild = discord.Object(config.GUILD)
changelog_channel = discord.Object

# connect to SQLite3 Database (just a server file)
conn = sqlite3.connect('rankings.db')


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


def split_message_rough(content):
    if len(content) <= 2000:
        return [content]
    fragments = []
    while len(content) > 2000:
        fragments.append(content[:2000])
        content = content[2000:].lstrip()
    fragments.append(content)
    return fragments


# strips names down to alphanumeric characters - useful for people doing things with different symbols/capitalization
# if none is inputted, itll just append none
def strip_names(*args):
    final = []
    for arg in args:
        if arg is not None:
            arg = str(arg)
            final.append(''.join([letter.lower() for letter in arg if letter.isalnum()]))
        else:
            final.append(None)
    return final


# CHANGELOG SECTION----------------------------------------------------------------------------------------------------
# the changelog is a channel where every single time an update is made to someones rankings/homework,
# it will send a message so everyone can see recent changes.
# all of this can be disabled by setting CHANGELOG_ACTIVE to False
# in an added album, the changes parameter is the album_id, followed by the rating


def get_changelog_channel():
    return client.get_channel(config.CHANGELOG_CHANNEL)


async def changelog_add_ranking(user, album_id, rating):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    row = spotify.get_album(album_id=album_id)
    artist = ", ".join(row[0])
    await channel.send(f"RANKINGS - {user.mention}:\n`rated {artist} - {row[1]} as a {rating}`")
    return


# in an edited album, the changes parameter is the album_id, the old rating, and the new rating
async def changelog_edit_ranking(user, album_id, old_rating, new_rating):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    row = spotify.get_album(album_id=album_id)
    artist = ", ".join(row[0])
    await channel.send(f"RANKINGS - {user.mention}:\n`changed {artist} - {row[1]} from a {old_rating}/10.0 to a {new_rating}/10.0`")
    return


# in a removed album, the changes parameter is the album_id
# we need to use spotify api since it may not be in album_master after the removal
async def changelog_remove_ranking(user, album_id):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    row = spotify.get_album(album_id=album_id)
    artist = ", ".join(row[0])
    await channel.send(f"RANKINGS - {user.mention}:\n`removed {artist} - {row[1]} from their rankings`")
    return


# in an added homework album, the changes parameter is the album_id, then the user who initiated them
async def changelog_add_homework(user, album_id, user_affected):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    row = spotify.get_album(album_id=album_id)
    artist = ", ".join(row[0])
    if user.id == user_affected.id:
        await channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {row[1]} to their homework list`")
    else:
        await channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {row[1]} to {user_affected.mention}'s homework list`")
    return


# in a finished homework album, the changes parameter is the album_id
# we have to use spotify api because it may have been removed from album_master
async def changelog_finish_homework(user, album_id):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    row = spotify.get_album(album_id=album_id)
    artist = ", ".join(row[0])
    await channel.send(f"HOMEWORK - {user.mention}:\n`listened to {artist} - {row[1]}`")
    return


async def changelog_new_user(user):
    channel = get_changelog_channel()
    if not config.CHANGELOG_ACTIVE:
        return
    await channel.send(f"{user.mention} used rankingbot for the first time lfgggg")
    return


# ALBUM_MASTER TABLE INTERACTIONS SECTION------------------------------------------------------------------------------
# album_master is a table that has every single album that is currently in anyone's rankngs/homework currently stored
# it stores properly formatted artist name (0), album name (1), the spotify album id (2),
# the release year (3) and a hyperlink to the cover image (4)
# this function will create that table
def make_album_master():
    cursor = conn.cursor()
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS album_master'''
                   f'''(artist TEXT, album TEXT, id TEXT, year INTEGER, image TEXT)''')
    cursor.close()
    return


# implementing a solution to the duplicate name problem, a master table of albums is needed.
# this uses the search functionality of spotify to find an album name, adds it to a table and returns it
async def add_to_album_master(artist: tuple, album: str, album_id=None):
    cursor = conn.cursor()
    make_album_master()
    row = spotify.get_album(artist, album, album_id)
    if row is None:
        raise LookupError(f"error: no matches found in spotify for {artist} - {album}")
    # this line will prevent duplicate albums from being added
    if get_album_master_row(album=row[1], artists=row[0], album_id=album_id, abort_early=True) is not None:
        return None
    year = row[3].split('-')[0]
    artists = ".-....".join(row[0])
    cursor.execute(f'''INSERT INTO album_master (artist, album, id, year, image) VALUES (?, ?, ?, ?, ?) RETURNING *''',
                   (artists, row[1], row[2], year, row[4]))
    data = cursor.fetchall()
    cursor.close()
    if data is None:
        raise LookupError("error: no rows were added, huh why what how???")
    conn.commit()
    return row


# function that removes a row from album_master (should be called on rows that are no longer in anyone's album ranking/homework)
async def remove_from_album_master(album: str, artist=None):
    row = get_album_master_row(artists=artist, album=album)
    artists = ".-....".join(artist)
    if row is None:
        # if artist is none, then this will look weird, but whatever
        raise ValueError(f"error: could not find {album} in album_master")
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM album_master WHERE artist = ? AND album = ? RETURNING *''', (artists, row[1]))
    data = cursor.fetchall()
    cursor.close()
    if data is None:
        raise LookupError("error: no rows were deleted from album_master, which is confusing idk why that happened")
    conn.commit()
    return "ok"


# gets every album stored in album_master and returns them
def get_album_master():
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM album_master''')
    output = cursor.fetchall()
    cursor.close()
    ret = [(tuple(row[0].split(".-....")), row[1], row[2], row[3], row[4]) for row in output]
    return ret


# grabs the full master album list and tries to find an album stored inside of it.
# this can be used in 2 ways, either with the album id, or with the albun name (and maybe artist)
# album_id is the best way to use it, so it will check if it can do this first
# doubles as a does row exist function (set abort_early to true)
def get_album_master_row(album: str = None, artists: tuple = None, album_id: int = None, abort_early=False):
    if album is None and album_id is None:
        raise ValueError("error: no value entered for either album or album_id")
    # if album_id is defined, we just use that to search through the list.
    # we also don't need to consider abort early because it literally cannot put duplicate album ids in the masterlist
    if album_id is not None:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM album_master WHERE id = ?''', (album_id,))
        data = cursor.fetchall()
        if len(data) != 0:
            ret = (tuple(data[0][0].split(".-....")), data[0][1], data[0][2], data[0][3], data[0][4])
            return ret

    # if album_id is not defined or album ids don't match, we can still use the album names to find the row
    final_list = []
    for row in get_album_master():
        row_album, album, row_artist, artists = strip_names(row[1], album, row[0], "".join(artists))
        if (row_album == album) and (row_artist in artists):
            if abort_early:
                return row
            final_list.append(row)

    if len(final_list) > 1:
        raise Exception("error: multiple entries of the same artist/album exist in album_master, please ping ruby")
    elif len(final_list) == 0:
        return None
    else:
        return final_list[0]


# this function is called via command and should refresh the master list
async def update_album_master():
    make_album_master()
    master_rows = get_album_master()
    user_albums = {(row[0], row[1]) for row in get_all_ranking_rows(unique=True)}
    homework_album_ids = {row[2] for row in homework.get_all_homework_rows(conn)}
    updated = 0
    # checks for new albums in user_albums that havent been added and adds them to album_master
    for user_row in user_albums:
        if user_row not in {(row[0], row[1]) for row in master_rows}:
            await add_to_album_master(artist=user_row[0], album=user_row[1])
            updated += 1
    for master_row in master_rows:
        if (master_row[0], master_row[1]) not in user_albums and master_row[2] not in homework_album_ids:
            if homework.get_homework_row(conn=conn, album_id=master_row[2]) is None:
                await remove_from_album_master(artist=master_row[0], album=master_row[1])
                updated += 1
    return updated


# RANKINGS TABLE SECTION----------------------------------------------------------------------------------------------
# makes a table for a user if it doesn't exist and inserts them into active users
async def make_table(user_id):
    cursor = conn.cursor()
    cursor.execute(f'''SELECT name FROM sqlite_master WHERE type='table' AND name='user_data_{user_id}';''')
    if cursor.fetchone() is None:
        # CHANGELOG - NEW USER
        user = await client.fetch_user(user_id)
        await changelog_new_user(user)
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS user_data_{user_id} (artists TEXT, title TEXT, rating FLOAT)''')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS users (user_ids INTEGER)''')
        cursor.execute(f'''INSERT INTO users (user_ids) VALUES ('{user_id}')''')
        conn.commit()
    return


# gets a users ranked list in order by the rating
# list return structure:
# returns [artist, album, rating, id, year, image_link]
def get_rows_from_user(user_id):
    cursor = conn.cursor()
    cursor.execute(f'''SELECT album_master.artist, album_master.album, user_data_{user_id}.rating, album_master.id, album_master.year, album_master.image FROM user_data_{user_id} INNER JOIN album_master ON user_data_{user_id}.artists = album_master.artist AND user_data_{user_id}.title = album_master.album ORDER BY rating DESC''')
    rows = cursor.fetchall()
    cursor.close()
    return [(tuple(row[0].split(".-....")), row[1], row[2], row[3], row[4], row[5]) for row in rows]


# gets ever single user_id, pulls all rows and returns them
# if unique, will use a set since sets cant have duplicate items
# returns [artist, album, rating, id, year, image_link]
def get_all_ranking_rows(unique=False):
    final_rows = set() if unique else []
    user_ids = get_users()
    for user_id in user_ids:
        rows = get_rows_from_user(user_id)
        if unique:
            final_rows.update({(row[0], row[1]) for row in rows})
        else:
            final_rows.extend(rows)
    return final_rows


# transforms rows into nice looking string
def get_user_rankings_formatted(user_id, year=datetime.now().year):
    rows = [row for row in get_rows_from_user(user_id) if row[4] == year]
    rankings_str = ''
    for i, row in enumerate(rows):
        ranking_str = f'{i + 1}. ' + ", ".join(row[0]) + f' - {row[1]} ({row[2]})'
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


async def get_rankings_message(year=datetime.now().year):
    users = get_users()
    final_message = f'# Ratings of {year}\n'
    # goes through every user who has had a table generated for them and adds their rankings to final_message
    for user_id in users:
        user = await client.fetch_user(user_id)
        rankings = get_user_rankings_formatted(user_id, year)
        if len(rankings.strip()) == 0:
            continue
        final_message = final_message + f"## {user.mention}'s rankings:\n{rankings}\n"
    return final_message


# Updates the rankings channel by deleting all messages then resending them
async def display_rankings(year=datetime.now().year):
    conn.commit()
    channel = client.get_channel(config.RANKING_CHANNEL)
    final_message = await get_rankings_message(year)
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
async def add_row(user_id: int, artist: tuple, album: str, rating: float, album_id: int = 0):
    cursor = conn.cursor()
    await make_table(user_id)
    artist, album = (artist, album.strip())
    # we can just call add_to_album_master since it does a check to ensure that the album is not already in album_master
    await add_to_album_master(artist=artist, album=album, album_id=album_id)
    # now we get the formatted row from album_master
    artist, album, album_id, year, image = get_album_master_row(artists=artist, album=album, album_id=album_id)
    if get_row_from_rankings(album=album, artist=artist, user_id=user_id) is not None:
        raise ValueError("error: you cannot add 2 of the same album to your rankings")
    # add to the table
    artists = ".-....".join(artist)
    cursor.execute(f'''INSERT INTO user_data_{user_id} (artists, title, rating)'''
                   f'''VALUES(?, ?, ?)''', (artists, album, rating))
    data = cursor.fetchall()
    cursor.close()
    if data is None:
        raise LookupError("error: no rows were added, which is confusing idk why that happened")
    conn.commit()
    artist = ", ".join(artist)
    return f"i successfully added {artist} - {album} to your rankings"


# this just splits a message up by new lines and calls add_row until there are no more new lines
# KNOWN BUG (not sure how to fix though) - artists/albums with commas cannot be bulk added, need to be single added
async def add_row_bulk(user_id, content):
    await make_table(user_id)
    rows = content.split("\n")
    # check for incorrect formatting/blank entries
    for i, row in enumerate(rows):
        row_to_add = row.split(',').strip()
        if len(row_to_add) != 3:
            raise SyntaxError(f"incorrect formatting (row {i} did not have 3 entries")
        if "" == row_to_add:
            raise SyntaxError(f"incorrect formatting (row {i} has a blank entry")
        # adds row if all checks succeed
        await add_row(user_id, row_to_add[0], row_to_add[1], row_to_add[2])
    return f"i successfully added {len(rows)} albums to your rankings"


# edits a row in a given table
async def edit_row(user_id, row, rating: float):
    await make_table(user_id)
    # update rating value in corresponding row
    cursor = conn.cursor()
    cursor.execute(f'''UPDATE user_data_{user_id} SET rating = {rating}'''
                   f''' WHERE artists = ? AND title = ? RETURNING *''', (".-....".join(row[0]), row[1]))
    data = cursor.fetchall()
    cursor.close()
    if data is None:
        raise LookupError("error: no rows were edited, which is confusing idk why that happened")
    conn.commit()
    artist = ", ".join(row[0])
    return f"i successfully edited {artist} - {row[1]} to a {rating}/10.0"


# removes a row from a certain users table
async def remove_row(user_id, row):
    await make_table(user_id)
    cursor = conn.cursor()
    # prevent an index out of bound exception
    cursor.execute(f"DELETE FROM user_data_{user_id} WHERE artists = ? AND title = ? RETURNING *", (".-....".join(row[0]), row[1]))
    data = cursor.fetchall()
    cursor.close()
    conn.commit()
    if data is None:
        raise LookupError("error: no rows were deleted, whyy?????")
    else:
        await update_album_master()
        artist = ", ".join(row[0])
        return f"i successfully deleted {artist} - {row[1]} from your list"


# ALBUM STATS SECTION---------------------------------------------------------------------------------------------------
# takes an album and (maybe) an artist in and checks if it finds them in a ranking table
# if it finds one, it will return the full row that it was on.
# also can take a user_id to only search rows specific to that user.
# doubles as a check for exists function
# row return structure - [artist, album, ratings, id, year, image_link]
def get_row_from_rankings(album: str, artist: str = None, user_id=0):
    if user_id == 0:
        rows = get_all_ranking_rows(unique=True)
    else:
        rows = get_rows_from_user(user_id=user_id)
    final_list = []
    for row in rows:
        row_album, album, row_artist, artist = strip_names(row[1], album, row[0], artist)
        if album == row_album and (artist is None or artist == row_artist):
            final_list.append(row)
    if len(final_list) == 0:
        return None
    return final_list[0]


# finds every rating that is associated with an album
# goes through every table and gets the alphanumeric album name and then compares
# if true, adds the rating associated to a list and returns the list
def get_album_ratings(album, artist=None):
    album, artist = strip_names(album, artist)
    ratings = tuple()
    for row in get_all_ranking_rows(unique=False):
        row_album, row_artist = strip_names(row[1], "".join(row[0]))
        if row_album in album and (artist is None or row_artist in "".join(artist)):
            ratings += (row[2],)
    return ratings


# we are only given an album or an artist, so we find the full formatted title using get_row
# we can use those to get album rankings, and then run some simple statistics and print it (could add more statistics)
def get_album_stats(album, artist=None, album_id=None):
    row = get_album_master_row(album=album, artists=artist, album_id=album_id)
    if row is None:
        raise LookupError('error: no albums found matching the name \"' + album + '\"')
    ratings = get_album_ratings(album=album, artist=artist)
    num_ratings = len(ratings)
    if num_ratings == 0:
        return "This album has no ratings"
    mean = round(statistics.mean(ratings), 2)
    artist = ", ".join(row[0])
    final_string = f"Artist: {artist}\nAlbum: {row[1]}\nNumber of Ratings: {num_ratings}\nMean: {mean}"
    if len(ratings) > 1:
        std_deviation = round(statistics.stdev(ratings), 2)
        final_string += f"\nStandard Deviation: {std_deviation}"
    return final_string


# this will get the ratings of every single album and return a dcitionary - tuple (artist, album) : tuple (ratings)
def get_all_ratings():
    # using a dictionary for this to map a tuple containing the artist and album titles to a tuple of ratings
    ratedict = dict()
    for artist, album, rating, album_id, year, image_link in get_all_ranking_rows(unique=False):
        ratings = ratedict.get((artist, album, year))
        if ratings is None:
            ratings = (rating,)
        else:
            ratings += (rating,)
        ratedict.update({(artist, album, year): ratings})
    return ratedict


def get_top_albums(top_number: int, min_ratings: int, year: int, sortby: str):
    all_ratings = {key: value for key, value in get_all_ratings().items() if len(value) >= min_ratings and
                   (year == -1 or year == key[2])}
    # error raising for invalid parameters
    if len(all_ratings) == 0:
        raise ValueError("error: no albums found that meet the conditions required")
    if 0 < top_number and top_number > len(all_ratings):
        raise ValueError("error: not enough albums to rank (or you entered a negative value)")

    if "avg" in sortby:
        sortdict = dict(sorted({key: round(statistics.mean(value), 2) for key, value in all_ratings.items()}.items(), key=lambda ratings: ratings[1], reverse=True))
    else:
        if min_ratings < 2:
            raise Exception("error: you cannot sort by standard deviation if minimum ratings is set to less than 2")
        sortdict = dict(sorted({key: round(statistics.stdev(value), 2) for key, value in all_ratings.items()}.items(), key=lambda ratings: ratings[1]))
    ret = sortdict.copy()
    for i, album in enumerate(sortdict):
        if i > top_number-1:
            ret.pop(album)
    return ret


def get_top_albums_formatted(top_number: int = 5, min_ratings: int = 2, year: int = -1, sortby: str = "avg"):
    rankings = get_top_albums(top_number, min_ratings, year, sortby)
    if 'avg' in sortby:
        final_string = f"## Top {top_number} albums with at least {min_ratings} rating(s) according to average:"
    else:
        final_string = f"## Top {top_number} albums with at least {min_ratings} rating(s) according to standard deviation:"
    for key, value in rankings.items():
        artist = ", ".join(key[0])
        final_string += f"\n{artist} - {key[1]}: {value}"
    return final_string


# takes in year, minratings, and numalbums and returns the missing one (either minratings or numalbums)
def top_albums_autocomplete_helper(whoscallin: str, year=datetime.now().year, minratings: int = None, numalbums: int = None):
    ratings_year = {key: value for key, value in get_all_ratings().items() if year == -1 or year == key[2]}
    if "maxalbums" in whoscallin:
        if minratings is None:
            return len(ratings_year)
        final_dict = {key: value for key, value in ratings_year.items() if len(value) >= minratings}
        return len(final_dict)
    if "minrating" in whoscallin:
        # sort the dictionary by number of ratings,
        # then go down however many rows and return the number of ratings on that album
        final_dict = dict(sorted(ratings_year.items(), key=lambda row: len(row[1]), reverse=True))
        if numalbums is None:
            return len(list(final_dict.values())[len(final_dict)-1])
        return len(list(final_dict.values())[numalbums-1])
    return


# AUTOCOMPLETE AND CHOICES SECTION-----------------------------------------------------------------------------------
# autocomplete names fail if a choice is over 100 characters, so this will modify names to take that into account
def autocomplete_slice_names_100(name):
    length = len(name)
    if length <= 100:
        return name
    # heres how we solve this problem. find the rightmost space character. slice there.
    # find the length of the right string. take the substring of the first string
    # so that the length of that plus and length of the right string add to 97
    r_index = name.rfind(" ")
    if r_index == -1:
        r_index = 97
    cut_title = name[:97 - (length - r_index) + 1] + "..." + name[r_index + 1:]
    return cut_title


# this takes in a list of (artist, album, value) and returns that list with all entries as less than 100 characters
def autocomplete_slice_list_names(choices):
    return [tuple(autocomplete_slice_names_100(name) if len(name) > 100 else name for name in choice) for choice in choices]


# gets a list of artists in album_master and returns a list of choices for use in autocomplete
async def autocomplete_artist(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    final_list = {", ".join(row[0]) for row in get_album_master()}
    return [Choice(name=artist, value=artist)
            for artist in final_list if strip_names(current)[0] in strip_names(artist)[0]]


# same as above, but it does albums with autocomplete
async def autocomplete_album(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    albums = tuple((row[1],) for row in get_album_master())
    final_list = autocomplete_slice_list_names(albums)
    return [Choice(name=album[0], value=album[0])
            for album in final_list if strip_names(current)[0] in strip_names(album[0])[0]]


# gets a formatted list of choices of artist - album using spotify search
async def autocomplete_spotify(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    results = await spotify.search_album(current)
    choices = [(", ".join(tuple(artist.name for artist in entry.artists)) + f" - {entry.name}", f"{entry.id}") for entry in results]
    final_choices = autocomplete_slice_list_names(choices)
    return [Choice(name=f"{choice[0]}", value=f"{choice[1]}") for choice in final_choices]


# gets a formatted list of choices of artist - album using album_master
async def autocomplete_artist_album(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    user_albums = [(", ".join (row[0]) + f" - {row[1]}", f"{row[2]}") for row in get_album_master()]
    final_list = autocomplete_slice_list_names(user_albums)
    return [Choice(name=entry[0], value=entry[1])
            for entry in final_list if current.lower() in entry[0].lower()]


# gets formatted choices for artist/album when editing/deleting rows from the list
async def autocomplete_artist_album_user_specific(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    albums = [(", ".join (row[0]) + f" - {row[1]}", f"{row[3]}") for row in get_rows_from_user(interaction.user.id)]
    final_list = autocomplete_slice_list_names(albums)
    return [Choice(name=entry[0], value=entry[1])
            for entry in final_list if current.lower() in entry[0].lower()]


# gets formatted choices for artist/album when editing/deleting rows from homework
async def autocomplete_artist_album_homework_specific(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    homework_list = [(", ".join(row[3]) + f" - {row[4]}", f"{row[5]}")
                     for row in homework.get_homework(conn=conn, user_id=interaction.user.id)]
    final_list = autocomplete_slice_list_names(homework_list)
    return [Choice(name=entry[0], value=entry[1])
            for entry in final_list if current.lower() in entry[0].lower()]


# gets choices for num albums as part of top_albums command
async def autocomplete_top_albums_numalbums(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    min_ratings = interaction.namespace.minimumratings
    year = interaction.namespace.year if interaction.namespace.year is not None else datetime.now().year
    max_num_albums = top_albums_autocomplete_helper("maxalbums", year=year, minratings=min_ratings)
    return [Choice(name=str(num), value=num)
            for num in range(1, max_num_albums+1) if str(current) in str(num)]


# gets choices for num albums as part of top_albums command
async def autocomplete_top_albums_minratings(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    numalbums = interaction.namespace.numberofalbums
    year = interaction.namespace.year if interaction.namespace.year is not None else datetime.now().year
    max_min_num_ratings = top_albums_autocomplete_helper("minrating", year=year, numalbums=numalbums)
    return [Choice(name=str(num), value=num)
            for num in range(1, max_min_num_ratings+1) if str(current) in str(num)]


# whenever the bot is ready, it'll log this
@client.event
async def on_ready():
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="your favourite music"))


# APPLICATION COMMAND SECTION---------------------------------------------------------------------------------------
# UPDATE COMMAND - rewrites the rankings in album rankings
@tree.command(name="update_ratings", description="update the album rankings", guild=my_guild)
async def update(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(await display_rankings())
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# SHOW RANKINGS COMMAND - prints the ratings of the given year (default == current year)
@tree.command(name="get_ratings", description="shows the ratings of a specific year", guild=my_guild)
@app_commands.describe(year="the year of which you want the ratings")
async def get_ratings(interaction: discord.Interaction, year: int = datetime.now().year):
    try:
        await interaction.response.send_message(await get_rankings_message(year=year))
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# ADDMANUAL COMMAND - adds an album to a users ranking with no search
@tree.command(name='add_rating_manual', description='add an album to your rankings', guild=my_guild)
@app_commands.describe(artist="the name of the artist",
                       album="the name of the album",
                       rating="the rating of the album")
@app_commands.autocomplete(artist=autocomplete_artist, album=autocomplete_album)
async def addmanual(interaction: discord.Interaction, artist: str, album: str, rating: float):
    try:
        artist = tuple(artist.split(","))
        await interaction.response.send_message(
            await add_row(user_id=interaction.user.id, artist=artist, album=album, rating=rating))
        await display_rankings()
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# ADD COMMAND - uses spotify + autocomplete to find albums
@tree.command(name='add_rating', description='add an album to your rankings with the help of spotify search', guild=my_guild)
@app_commands.describe(searchkeywords="type in keywords for your search here")
@app_commands.autocomplete(searchkeywords=autocomplete_spotify)
async def add(interaction: discord.Interaction, searchkeywords: str, rating: float):
    try:
        artist, album, album_id, date, album_cover = spotify.get_album(album_id=searchkeywords)
        await interaction.response.send_message(await add_row(artist=artist, album=album, user_id=interaction.user.id,
                                                              album_id=album_id, rating=rating))
        # Remove from the homework, if it exists there
        homework.remove_homework(conn, interaction.user.id, album_id)
        spotify.remove_album_from_playlist(interaction.user, album_id)
        if int(date[:4]) == datetime.now().year:
            await display_rankings()
        await changelog_add_ranking(interaction.user, album_id, rating)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# BULK ADD COMMAND - add command that can be done with multiple albums at once (VERY PICKY FORMATTING)
# this command it probably broken
@tree.command(name="add_rating_bulk", description='add multiple albums to your rankings', guild=my_guild)
@app_commands.describe(albums="the full list of albums you want to add. it should be in this format"
                              "\nArtist, Album Title, Rating (Next Line)")
async def addbulk(interaction: discord.Interaction, albums: str):
    try:
        await interaction.response.send_message(await add_row_bulk(interaction.user.id, albums))
        await display_rankings()
        # i figured this was useless as a changelog method so i just put it here
        if config.CHANGELOG_ACTIVE:
            await changelog_channel.send(f"{interaction.user.mention} just added a bunch of new albums to their rankings")
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# EDIT COMMAND - edits the ranking of a certain album on a users list
@tree.command(name='edit_rating', description='edit a rating on an album', guild=my_guild)
@app_commands.describe(entry="the artist - album whos rating you want to change",
                       rating="your new rating of the album (0-10)")
@app_commands.autocomplete(entry=autocomplete_artist_album_user_specific)
async def edit(interaction: discord.Interaction, entry: str, rating: float):
    try:
        artist, album, album_id, date, image = spotify.get_album(album_id=entry)
        user_row = get_row_from_rankings(album=album, artist=artist, user_id=interaction.user.id)
        if user_row is None:
            raise ValueError("error: you cannot edit a rating that isnt on your list")
        await interaction.response.send_message(await edit_row(
            interaction.user.id, (artist, album), rating))
        await display_rankings()
        await changelog_edit_ranking(user=interaction.user, album_id=album_id, old_rating=user_row[2], new_rating=rating)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


# REMOVE COMMAND - removes an album from a users list
@tree.command(name="remove_rating", description="remove an album from your ranking", guild=my_guild)
@app_commands.describe(entry="the artist - album you want to remove (see autocomplete)")
@app_commands.autocomplete(entry=autocomplete_artist_album_user_specific)
async def remove(interaction: discord.Interaction, entry: str):
    try:
        artist, album, album_id, date, image = spotify.get_album(album_id=entry)
        if get_row_from_rankings(album=album, artist=artist, user_id=interaction.user.id) is None:
            raise ValueError("error, you cannot remove a row that doesnt exist in your rankings")
        await interaction.response.send_message(await remove_row(interaction.user.id, (artist, album)))
        await display_rankings()
        await changelog_remove_ranking(interaction.user, album_id)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# COVER COMMAND - displays the cover of the album
@tree.command(name="album_cover", description="displays the cover of an album", guild=my_guild)
@app_commands.describe(entry="the album - artist you want to see the cover of (see autocomplete)")
@app_commands.autocomplete(entry=autocomplete_spotify)
async def cover(interaction: discord.Interaction, entry: str):
    try:
        artist, album, album_id, date, album_cover = spotify.get_album(album_id=entry)
        embed = discord.Embed(title=album, description=f"by " + ", ".join(artist) + f" - {date}")
        embed.set_image(url=album_cover)
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# STATS COMMAND - displays stats for a certain album based on current rankings
@tree.command(name='stats', description='find out stats about an album', guild=my_guild)
@app_commands.describe(entry="the artist - album you are trying to get (see autocomplete)")
@app_commands.autocomplete(entry=autocomplete_artist_album)
async def stats(interaction: discord.Interaction, entry: str):
    try:
        artist, album, album_id, date, image = spotify.get_album(album_id=entry)
        if get_row_from_rankings(album=album, artist=artist) is None:
            raise ValueError("error: you cannot get stats for an album that is not ranked by anyone")
        album_cover = image
        embed = discord.Embed(title=album, description=get_album_stats(album=album, artist=artist, album_id=album_id))
        embed.set_image(url=album_cover)
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


@tree.command(name='top_albums', description='find the top albums of the year (or any year) (refresh autocomplete by changing text channels)', guild=my_guild)
@app_commands.describe(numberofalbums="how many albums do you want to see ranked? (default: 5)",
                       minimumratings="how many rankings do you want the album to have minimum (default: 1)",
                       year="the year you want to filter by, -1 for no filtering")
@app_commands.autocomplete(numberofalbums=autocomplete_top_albums_numalbums, minimumratings=autocomplete_top_albums_minratings)
@app_commands.choices(sortby=[Choice(name='average', value='avg'), Choice(name='standard deviation', value='std')])
async def top_albums(interaction: discord.Interaction, numberofalbums: int = 5, minimumratings: int = 1, sortby: str = 'avg', year: int = datetime.now().year):
    try:
        await interaction.response.send_message(get_top_albums_formatted(numberofalbums, minimumratings, year, sortby))
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# ADD HOMEWORK - adds homework for a certain user
@tree.command(name='add_homework', description='Add homework to someone\'s list', guild=my_guild)
@app_commands.describe(entry="the artist - album you are trying to add (select an autocomplete option)",
                       user='the user whose homework list you\'re adding to')
@app_commands.autocomplete(entry=autocomplete_spotify)
async def add_homework(interaction: discord.Interaction, entry: str, user: discord.User = None):
    try:
        await interaction.response.defer()
        artist, album, album_id, date, album_cover = spotify.get_album(album_id=entry)
        if user is None:
            user = interaction.user
        await add_to_album_master(artist=artist, album=album, album_id=album_id)
        # Don't add it if user has already rated it
        artists = ", ".join(artist)
        if get_row_from_rankings(artist=artist, album=album, user_id=user.id) is not None:
            raise ValueError(f"error: {user.mention} has already listened to {artists} - {album}")
        homework.add_homework(conn, user.id, album_id)
        spotify.add_album_to_playlist(user, album_id)
        await interaction.followup.send(f"i successfully added {artists} - {album} to {user.mention}'s homework")
        await changelog_add_homework(interaction.user, album_id, user)
    except Exception as error:
        traceback.print_exc()
        await interaction.followup.send(error)


# GET HOMEWORK - lists homework for a certain user
@tree.command(name='get_homework', description='View someone\'s homework', guild=my_guild)
@app_commands.describe(user='the user whose homework list you\'re looking at')
async def get_homework(interaction: discord.Interaction, user: discord.User = None):
    try:
        await interaction.response.defer()
        if user is None:
            user = interaction.user
        fragments = split_message(homework.get_homework_formatted(conn, user))
        await interaction.followup.send(fragments[0], suppress_embeds=True)
        for msg in fragments[1:]:
            await interaction.channel.send(msg, suppress_embeds=True)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# REMOVE_HOMEWORK: deletes homework from a users list
@tree.command(name='remove_homework', description='remove homework from your list', guild=my_guild)
@app_commands.describe(entry="the artist - album you are trying to remove from your list (see autocomplete)")
@app_commands.autocomplete(entry=autocomplete_artist_album_homework_specific)
async def remove_homework(interaction: discord.Interaction, entry: str):
    try:
        # fetches album from album_master and deletes it from the users homework table
        await interaction.response.send_message(content=homework.remove_homework(conn, interaction.user.id, entry), suppress_embeds=True)
        await update_album_master()
        await changelog_finish_homework(interaction.user, entry)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(error)


# ADD ALL HOMEWORK - adds homework to everyones homework
@tree.command(name='add_all_homework', description='add homework to everyones list', guild=my_guild)
@app_commands.describe(entry="the artist - album you are trying to add to everyones list (see autocomplete)")
@app_commands.autocomplete(entry=autocomplete_spotify)
async def add_all_homework(interaction: discord.Interaction, entry: str):
    try:
        await interaction.response.defer()
        row = spotify.get_album(album_id=entry)
        await add_to_album_master(artist=row[0], album=row[1], album_id=entry)
        # gets all users and adds a specific album to their homework
        added = 0
        for user in get_users():
            try:
                homework.add_homework(conn, user, entry)
                added += 1
                user_obj = await client.fetch_user(user)
                spotify.add_album_to_playlist(user_obj, entry)
                await changelog_add_homework(user_obj, entry, user_obj)
            except ValueError:
                pass
            except Exception as error:
                raise error
        artists = ", ".join(row[0])
        await interaction.followup.send(content=f"i successfully added {artists} - {row[1]} to {added} users homework")
        await update_album_master()
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
@tree.command(name='albummaster_update', description='MOD ONLY: updates album master')
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
@tree.command(name='albummaster_get', description='DEBUG: FOR MODS ONLY, to display album_master for debugging', guild=my_guild)
@app_commands.describe()
@app_commands.checks.has_role(config.MOD_ID)
async def getalbummaster(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        data = str(get_album_master())
        result = split_message_rough(data)
        await interaction.followup.send(content=result[0])
        for msg in result[1:]:
            await interaction.channel.send(msg)
    except Exception as error:
        traceback.print_exc()
        await interaction.response.send_message(content=error)


@client.event
async def on_shutdown():
    conn.commit()
    conn.close()
    spotify.close_spotify_conn()


TOKEN = config.TOKEN
client.run(TOKEN)
