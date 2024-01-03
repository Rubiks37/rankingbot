# import useful modules
import asyncio
from datetime import datetime
from traceback import print_exc
from json import dumps, loads
import sqlite3
import statistics

# import discord things
import discord
from discord import app_commands
from discord.app_commands import Choice

# import other files
import spotify_integration as spotify
import autocomplete as ac
from changelog import Changelog
from config import Config
import tables


# sets up config object to access settings
config = Config()

# sets up Discord Bot with read and write message privileges, but without mentioning privileges
intents = discord.Intents.default()
intents.message_content = True
allowed_mentions = discord.AllowedMentions.none()
client = discord.Client(intents=intents, allowed_mentions=allowed_mentions)

# sets up command tree to have application commands run with
tree = app_commands.CommandTree(client)

# sets up guild/channel/permissions objects for later use
my_guild = discord.Object(config.guild)
changelog = Changelog(client, config.changelog_active)

# configure sqlite3 settings (custom JSON datatype)
sqlite3.register_adapter(dict, dumps)
sqlite3.register_adapter(list, dumps)
sqlite3.register_converter('JSON', loads)

# connect to SQLite3 Database (just a server file)
conn = sqlite3.connect('rankings.db', detect_types=sqlite3.PARSE_DECLTYPES)

# set conn return to dictionary mapping row names to values
conn.row_factory = tables.dict_factory

# create both table objects for interacting with master table and ranking table
master_table = tables.MasterTable(conn)
rating_table = tables.RatingTable(conn)
homework_table = tables.HomeworkTable(conn)


# Sync global & guild only commands
async def sync_commands():
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
# if none is inputted, it'll just append none
def strip_names(*args):
    final = []
    for arg in args:
        if arg is not None:
            arg = str(arg)
            final.append(''.join([letter.lower() for letter in arg if letter.isalnum()]))
        else:
            final.append(None)
    return final


# RANKINGS TABLE SECTION----------------------------------------------------------------------------------------------
async def get_rankings_message(year=datetime.now().year):
    users = rating_table.get_users()
    final_message = f'# Ratings of {year}\n'

    # goes through every user who is in rating table  and adds their rankings to final_message
    for user_id in users:
        user = await client.fetch_user(user_id)
        rankings = rating_table.get_user_ratings_formatted(user_id, year)
        if len(rankings.strip()) == 0:
            continue
        final_message += f"## {user.mention}'s rankings:\n{rankings}\n"

    return final_message


# Updates the rankings channel by deleting all messages then resending them
async def display_rankings(year=datetime.now().year):
    channel = client.get_channel(config.ranking_channel)
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
async def add_row(user_id: int, album_id: str, rating: float):
    album = spotify.get_album(album_id=album_id)
    master_table.add_row(album)
    try:
        data = rating_table.add_row(album_id, user_id, rating)

    # checking if any errors are due to primary key constraint,
    # meaning a user tried to add an album to their ratings twice.
    except sqlite3.IntegrityError as error:
        raise ValueError('error: you cannot have the same album in your rankings more than once')

    if len(data) == 0:
        raise LookupError("error: no rows were added, which is confusing idk why that happened")
    album_id = next(iter(data))['album_id']
    album = next(iter(master_table.get_row(album_id)))
    artist = ", ".join(album['artist'])
    album = album['album_name']
    return f"i successfully added {artist} - {album} to your rankings"


# edits a row in a given table
async def edit_row(user_id: int, album_id: str, rating: float):
    data = rating_table.edit_row(album_id, user_id, rating)
    if len(data) == 0:
        raise LookupError("error: no rows were edited, which is confusing idk why that happened")
    album_id = next(iter(data))['album_id']
    album = next(iter(master_table.get_row(album_id)))
    artist = ", ".join(album['artist'])
    album = album['album_name']
    return f"i successfully edited {artist} - {album} to a {rating}/10.0"


# removes a row from a certain users table
async def remove_row(user_id, album_id):
    data = rating_table.remove_row(album_id, user_id)
    if data is None:
        raise LookupError("error: no rows were deleted, whyy?????")
    album_id = next(iter(data))['album_id']
    album = next(iter(master_table.get_row(album_id)))
    artist = ", ".join(album['artist'])
    album = album['album_name']
    return f"i successfully deleted {artist} - {album} from your list"


# ALBUM STATS SECTION---------------------------------------------------------------------------------------------------
# finds every rating that is associated with an album
# goes through every table and gets the alphanumeric album name and then compares
# if true, adds the rating associated to a list and returns the list
def get_album_ratings(album_id):
    ratings = tuple([rating['rating'] for rating in rating_table.get_single_album_ratings(album_id)])
    return ratings


# get album rankings, and then run some simple statistics and embed it (could add more statistics)
def get_album_stats(album_id):
    row = master_table.get_row(album_id)
    if row is None:
        raise LookupError("error: no albums found, potentially because you didn't select an autocomplete option")

    ratings = get_album_ratings(album_id)
    num_ratings = len(ratings)
    if num_ratings == 0:
        raise ValueError("error: This album has no ratings")

    mean = round(statistics.mean(ratings), 2)
    artist = ", ".join(row[0])
    final_string = f"Artist: {artist}\nAlbum: {row[1]}\nNumber of Ratings: {num_ratings}\nMean: {mean}"
    if len(ratings) > 1:
        std_deviation = round(statistics.stdev(ratings), 2)
        final_string += f"\nStandard Deviation: {std_deviation}"
    return final_string


# this will get the ratings of every single album and return a dictionary - tuple (artist, album) : tuple (ratings)


def get_top_albums(top_number: int, min_ratings: int, year: int, sort_by: str):
    all_ratings = [album for album in rating_table.get_grouped_ratings()
                   if len(album['ratings']) >= min_ratings and (year == -1 or year == album['year'])]

    # error raising for invalid parameters
    if len(all_ratings) == 0:
        raise ValueError("error: no albums found that meet the conditions required")
    if 0 < top_number and top_number > len(all_ratings):
        raise ValueError("error: not enough albums to rank (or you entered a negative value)")

    if "avg" in sort_by:
        ratings_with_stat = [{**album, 'statistic': statistics.mean(album['ratings'])} for album in all_ratings]
        sorted_list = list(sorted(ratings_with_stat, key=lambda x: x['statistic'], reverse=True))
    else:
        if min_ratings < 2:
            raise Exception("error: you cannot sort by standard deviation if minimum ratings is set to less than 2")
        ratings_with_stat = [{**album, 'statistic': statistics.stdev(album['ratings'])} for album in all_ratings]
        sorted_list = list(sorted(ratings_with_stat, key=lambda x: x['statistic']))

    return sorted_list[:top_number]


def get_top_albums_formatted(top_number: int = 5, min_ratings: int = 2, year: int = -1, sortby: str = "avg"):
    rankings = get_top_albums(top_number, min_ratings, year, sortby)
    if 'avg' in sortby:
        final_string = f"## Top {top_number} albums with at least {min_ratings} rating(s) according to average:"
    else:
        final_string = f"## Top {top_number} albums with at least {min_ratings} rating(s) according to standard deviation:"
    for album in rankings:
        final_string += f"\n{', '.join(album['artist'])} - {album['album_name']}: {album['statistic']}"
    return final_string


# whenever the bot is ready, it'll log this
@client.event
async def on_ready():
    await changelog.initialize_channel(config.changelog_channel)
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="your favourite music"))


# APPLICATION COMMAND SECTION---------------------------------------------------------------------------------------
# UPDATE COMMAND - rewrites the rankings in album rankings
@tree.command(name="update", description="update the album rankings", guild=my_guild)
async def update(interaction: discord.Interaction):
    try:
        await master_table.update_master_table(rating_table, homework_table)
        await interaction.response.send_message(await display_rankings())
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)


# SHOW RANKINGS COMMAND - prints the ratings of the given year (default == current year)
@tree.command(name="get-ratings", description="shows the ratings of a specific year", guild=my_guild)
@app_commands.describe(year="the year of which you want the ratings")
async def get_ratings(interaction: discord.Interaction, year: int = datetime.now().year):
    try:
        await interaction.response.defer()
        message = await get_rankings_message(year=year)
        messages = split_message(message)
        await interaction.followup.send(messages[0])
        [await interaction.channel.send(content=i) for i in messages[1:]]
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)


# ADD COMMAND - uses spotify + autocomplete to find albums
@tree.command(name='add-rating', description='add an album to your rankings with the help of spotify search', guild=my_guild)
@app_commands.describe(album_id="the artist - album you're searching for")
@app_commands.autocomplete(album_id=ac.autocomplete_spotify(spotify.search_album))
@app_commands.rename(album_id='entry')
async def add(interaction: discord.Interaction, album_id: str, rating: float):
    try:
        album = spotify.get_album(album_id=album_id)
        await interaction.response.send_message(await add_row(album_id=album_id, user_id=interaction.user.id,
                                                              rating=rating))
        # Remove from the homework, if it exists there
        homework_table.remove_homework(interaction.user.id, album_id)
        spotify.remove_album_from_playlist(interaction.user, album_id)
        if datetime.fromisoformat(album.release_date).year == datetime.now().year:
            await display_rankings()
        await changelog.event_add_ranking(interaction.user, album_id, rating)
        await master_table.update_master_table(rating_table, homework_table)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)


# EDIT COMMAND - edits the ranking of a certain album on a users list
@tree.command(name='edit-rating', description='edit a rating on an album', guild=my_guild)
@app_commands.describe(album_id="the artist - album whos rating you want to change",
                       rating="your new rating of the album (0-10)")
@app_commands.rename(album_id='entry')
@app_commands.autocomplete(album_id=ac.autocomplete_artist_album_user_specific(rating_table.get_users_ratings))
async def edit(interaction: discord.Interaction, album_id: str, rating: float):
    try:
        old_rating = rating_table.get_single_rating(interaction.user.id, album_id)
        if old_rating is None:
            raise ValueError("error: you cannot edit a rating that isnt on your list")

        await interaction.response.send_message(await edit_row(interaction.user.id, album_id, rating))
        await display_rankings()
        await changelog.event_edit_ranking(user=interaction.user, album_id=album_id, old_rating=old_rating['rating'], new_rating=rating)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)


# REMOVE COMMAND - removes an album from a users list
@tree.command(name="remove-rating", description="remove an album from your ranking", guild=my_guild)
@app_commands.describe(album_id="the artist - album you want to remove (see autocomplete)")
@app_commands.rename(album_id='entry')
@app_commands.autocomplete(album_id=ac.autocomplete_artist_album_user_specific(rating_table.get_users_ratings))
async def remove(interaction: discord.Interaction, album_id: str):
    try:
        if rating_table.get_single_rating(interaction.user.id, album_id) is None:
            raise ValueError("error, you cannot remove a row that doesnt exist in your rankings")
        await interaction.response.send_message(await remove_row(interaction.user.id, album_id))
        await display_rankings()
        await changelog.event_remove_ranking(interaction.user, album_id)
        await master_table.update_master_table(rating_table, homework_table)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# COVER COMMAND - displays the cover of the album
@tree.command(name="album-cover", description="displays the cover of an album", guild=my_guild)
@app_commands.describe(album_id="the album - artist you want to see the cover of (see autocomplete)")
@app_commands.rename(album_id='entry')
@app_commands.autocomplete(album_id=ac.autocomplete_spotify(spotify.search_album))
async def cover(interaction: discord.Interaction, album_id: str):
    try:
        album = spotify.get_album(album_id=album_id)
        artists = [artist.name for artist in album.artists]
        embed = discord.Embed(title=album, description=f"by " + ", ".join(artists) + f" - {album.release_date}")
        embed.set_image(url=album.images[0].url)
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# STATS COMMAND - displays stats for a certain album based on current rankings
@tree.command(name='stats', description='find out stats about an album', guild=my_guild)
@app_commands.describe(album_id="the artist - album you are trying to get (see autocomplete)")
@app_commands.rename(album_id='entry')
@app_commands.autocomplete(album_id=ac.autocomplete_artist_album(master_table.get_full_table))
async def stats(interaction: discord.Interaction, album_id: str):
    try:
        artist, album, album_id, date, image = spotify.get_album(album_id=album_id)
        if rating_table.get_single_rating(interaction.user.id, album_id) is None:
            raise ValueError("error: you cannot get stats for an album that is not ranked by anyone")
        album_cover = image
        embed = discord.Embed(title=album, description=get_album_stats(album_id=album_id))
        embed.set_image(url=album_cover)
        await interaction.response.send_message(embed=embed)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


@tree.command(name='top-albums', description='find the top albums of the year (or any year) '
                                             '(refresh autocomplete by changing text channels)', guild=my_guild)
@app_commands.describe(numberofalbums="how many albums do you want to see ranked? (default: 5)",
                       minimumratings="how many rankings do you want the album to have minimum (default: 1)",
                       year="the year you want to filter by, -1 for no filtering")
@app_commands.autocomplete(numberofalbums=ac.autocomplete_top_albums_numalbums(rating_table.get_full_table),
                           minimumratings=ac.autocomplete_top_albums_minratings(rating_table.get_full_table))
@app_commands.choices(sortby=[Choice(name='average', value='avg'), Choice(name='standard deviation', value='std')])
async def top_albums(interaction: discord.Interaction, numberofalbums: int = 5, minimumratings: int = 1, sortby: str = 'avg', year: int = datetime.now().year):
    try:
        await interaction.response.send_message(get_top_albums_formatted(numberofalbums, minimumratings, year, sortby))
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# ADD HOMEWORK - adds homework for a certain user
@tree.command(name='add-homework', description='Add homework to someone\'s list', guild=my_guild)
@app_commands.describe(album_id="the artist - album you are trying to add (select an autocomplete option)",
                       user="the user whose homework list you're adding to")
@app_commands.rename(album_id='entry')
@app_commands.autocomplete(album_id=ac.autocomplete_spotify(spotify.search_album))
async def add_homework(interaction: discord.Interaction, album_id: str, user: discord.User = None):
    try:
        await interaction.response.defer()
        album = spotify.get_album(album_id=album_id)
        if user is None:
            user = interaction.user
        # Don't add it if user has already rated it
        artists = ", ".join([artist.name for artist in album.artists])
        if rating_table.get_single_rating(user.id, album_id) is not None:
            raise ValueError(f"error: {user.mention} has already listened to {artists} - {album.name}")
        homework_table.add_homework(user.id, album_id)
        spotify.add_album_to_playlist(user, album_id)
        await interaction.followup.send(f"i successfully added {artists} - {album.name} to {user.mention}'s homework")
        await changelog.event_add_homework(interaction.user, album_id, user)
    except Exception as error:
        print_exc()
        await interaction.followup.send(error)


# GET HOMEWORK - lists homework for a certain user
@tree.command(name='get-homework', description="View someone's homework", guild=my_guild)
@app_commands.describe(user="the user whose homework list you're looking at")
async def get_homework(interaction: discord.Interaction, user: discord.User = None):
    try:
        await interaction.response.defer()
        if user is None:
            user = interaction.user
        fragments = split_message(homework_table.get_homework_formatted(user))
        await interaction.followup.send(fragments[0], suppress_embeds=True)
        for msg in fragments[1:]:
            await interaction.channel.send(msg, suppress_embeds=True)
        await master_table.update_master_table(rating_table, homework_table)

    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# REMOVE_HOMEWORK: deletes homework from a users list
@tree.command(name='remove-homework', description='remove homework from your list', guild=my_guild)
@app_commands.rename(album_id='entry')
@app_commands.describe(album_id="the artist - album you are trying to remove from your list (see autocomplete)")
@app_commands.autocomplete(album_id=ac.autocomplete_artist_album_homework_specific(homework_table.get_homework, conn))
async def remove_homework(interaction: discord.Interaction, album_id: str):
    try:
        # fetches album from album_master and deletes it from the users homework table
        await interaction.response.send_message(content=homework_table.remove_homework(interaction.user.id, album_id), suppress_embeds=True)
        await master_table.update_master_table(rating_table, homework_table)
        await changelog.event_finish_homework(interaction.user, album_id)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# ADD ALL HOMEWORK - adds homework to everyones homework
@tree.command(name='add-all-homework', description='add homework to everyones list', guild=my_guild)
@app_commands.rename(album_id='entry')
@app_commands.describe(album_id="the artist - album you are trying to add to everyones list (see autocomplete)")
@app_commands.autocomplete(album_id=ac.autocomplete_spotify(spotify.search_album))
async def add_all_homework(interaction: discord.Interaction, album_id: str):
    try:
        await interaction.response.defer()
        album = spotify.get_album(album_id=album_id)
        await master_table.add_row(album)
        # gets all users and adds a specific album to their homework
        added = 0
        for user in rating_table.get_users():
            try:
                homework_table.add_homework(user.id, album_id)
                added += 1
                user_obj = await client.fetch_user(user)
                spotify.add_album_to_playlist(user_obj, album_id)
                await changelog.event_add_homework(user_obj, album_id, user_obj)
            except ValueError:
                pass
            except Exception as error:
                raise error
        artists = ", ".join([artist.name for artist in album.artists])
        await interaction.followup.send(content=f"i successfully added {artists} - {album.name} to {added} users homework")
        await master_table.update_master_table(rating_table, homework_table)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(error)


# SYNC COMMAND - calls tree.sync to sync new changes to application commands
@tree.command(name='sync', description='MOD ONLY: syncs the application commands')
@app_commands.checks.has_role(config.mod_id)
async def sync(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        await sync_commands()
        await master_table.update_master_table(rating_table, homework_table)
        await interaction.followup.send(content="sync successful")
    except Exception as error:
        await interaction.followup.send(content=error)


# DEBUG: SQLITE3 - allows mods to run SQL commands for debugging
@tree.command(name='sqlite', description='DEBUG: FOR MODS ONLY, to execute sql statements', guild=my_guild)
@app_commands.describe(command="the command to execute, be very careful about this")
@app_commands.checks.has_role(config.mod_id)
async def sqlite(interaction: discord.Interaction, command: str):
    cursor = conn.cursor()
    try:
        cursor.execute(command)
        await interaction.response.send_message(content=cursor.fetchall())
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)
    finally:
        cursor.close()


# DEBUG: GETALBUMMASTER - displays album_master,
@tree.command(name='get-master-table', description='DEBUG: FOR MODS ONLY, to display album_master for debugging', guild=my_guild)
@app_commands.describe()
@app_commands.checks.has_role(config.mod_id)
async def get_master_table(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        data = str(master_table.get_full_table())
        result = split_message_rough(data)
        await interaction.followup.send(content=result[0])
        for msg in result[1:]:
            await interaction.channel.send(msg)
    except Exception as error:
        print_exc()
        await interaction.response.send_message(content=error)


@client.event
async def on_shutdown():
    conn.commit()
    conn.close()
    spotify.close_spotify_conn()


TOKEN = config.token
client.run(TOKEN)
