from discord import Interaction
from discord.app_commands import Choice
from datetime import datetime


def strip_names(*args):
    final = []
    for arg in args:
        if arg is not None:
            arg = str(arg)
            final.append(''.join([letter.lower() for letter in arg if letter.isalnum()]))
        else:
            final.append(None)
    return final


# autocomplete names fail if a choice is over 100 characters, so this will modify names to take that into account
def autocomplete_slice_names_100(name):
    length = len(name)
    if length <= 100:
        return name
    # here's how we solve this problem. find the rightmost space character. slice there.
    # find the length of the right string. take the substring of the first string
    # so that the length of that plus and length of the right string add to 97
    r_index = 85
    cut_title = name[:r_index + 1] + "..." + name[-1 * (97 - r_index) + 1:]
    return cut_title


# some of these functions wont work properly if there aren't exact matches which is bad, so this is a search function
# it goes through each word in a string and tries to find if there are matching words in the current string
def autocomplete_search_list(current_str: str, strs_to_search: tuple):
    translate_table = str.maketrans('', '', '\'",-.!/():')
    current_words = current_str.translate(translate_table).split(' ')
    return_list = list()
    for item in strs_to_search:
        tuple_to_search = tuple(item[0].translate(translate_table).split(' '))
        if all([any([string1.lower() in string2.lower() for string2 in tuple_to_search]) for string1 in current_words]):
            return_list.append(item)
    return return_list


def filter_year(all_ratings, year):
    # filters albums by year (or does not filter if year filtering is turned off)
    return [row for row in all_ratings if year == -1 or year == row['year']]


def get_max_albums_possible(get_all_ratings,  year=datetime.now().year, minratings: int = None):
    ratings_year = filter_year(get_all_ratings(), year)
    if minratings is None:
        return len(ratings_year)
    # filters albums - if the number of ratings is greater than the min_ratings
    final_dict = {row for row in ratings_year if len(row['ratings']) >= minratings}
    return len(final_dict)


def get_min_ratings_possible(get_all_ratings, year=datetime.now().year, numalbums: int = None):
    ratings_year = filter_year(get_all_ratings(), year)

    # sort the dictionary by number of ratings,
    # then go down however many rows and return the number of ratings on that album
    final_dict = list(sorted(ratings_year, key=lambda row: len(row['ratings']), reverse=True))
    if numalbums is None:
        return len(final_dict[-1])
    return len(final_dict[numalbums - 1])


# this takes in a list of (artist, album, value) and returns that list with all entries as less than 100 characters
def autocomplete_slice_list_names(choices):
    return [tuple(autocomplete_slice_names_100(name) if len(name) > 100 else name for name in choice) for choice in choices]


# gets a list of artists in album_master and returns a list of choices for use in autocomplete
def autocomplete_artist(get_album_master):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        final_list = {", ".join(row['artist']) for row in get_album_master()}
        return [Choice(name=artist, value=artist)
                for artist in final_list if strip_names(current)[0] in strip_names(artist)[0]][:25]
    return inner


# same as above, but it does albums with autocomplete
# get_album_master is a refernece to the function in main
def autocomplete_album(get_album_master):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        albums = tuple((row['album_name']) for row in get_album_master())
        final_list = autocomplete_slice_list_names(albums)
        return [Choice(name=album[0], value=album[0])
                for album in final_list if strip_names(current)[0] in strip_names(album[0])[0]][:25]
    return inner


# gets a formatted list of choices of artist - album using spotify search
def autocomplete_spotify(search_album):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        results = await search_album(current)
        choices = [(", ".join([artist.name for artist in entry.artists]) + f" ({entry.type}) - {entry.name}", f"{entry.id}") for entry in results]
        final_choices = autocomplete_slice_list_names(choices)
        return [Choice(name=f"{choice[0]}", value=f"{choice[1]}") for choice in final_choices][:25]
    return inner


# gets a formatted list of choices of artist - album using album_master
def autocomplete_artist_album(get_album_master):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        user_albums = tuple([(", ".join(row['artist']) + f" - {row['album_name']}", f"{row['album_id']}") for row in get_album_master()])
        filtered_list = autocomplete_search_list(current, user_albums)
        final_list = autocomplete_slice_list_names(filtered_list)
        return [Choice(name=entry[0], value=entry[1]) for entry in final_list][:25]
    return inner


# gets formatted choices for artist/album when editing/deleting rows from the list
def autocomplete_artist_album_user_specific(get_rows_from_user):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        albums = [(", ".join(row['artist']) + f" - {row['album_name']}", f"{row['album_id']}")
                  for row in get_rows_from_user(interaction.user.id)]
        final_list = autocomplete_slice_list_names(albums)

        return [Choice(name=entry[0], value=entry[1])
                for entry in final_list if current.lower() in entry[0].lower()][:25]
    return inner


# gets formatted choices for artist/album when editing/deleting rows from homework
def autocomplete_artist_album_homework_specific(get_homework, conn):
    async def inner(interaction: Interaction, current: str) -> list[Choice[str]]:
        homework_list = [(", ".join(row['artist']) + f" - {row['album_name']}", f"{row['album_id']}")
                         for row in get_homework(user_id=interaction.user.id)]
        final_list = autocomplete_slice_list_names(homework_list)
        return [Choice(name=entry[0], value=entry[1])
                for entry in final_list if current.lower() in entry[0].lower()][:25]
    return inner


# gets choices for num albums as part of top_albums command
def autocomplete_top_albums_numalbums(get_all_ratings):
    async def inner(interaction: Interaction, current: str) -> list[Choice[int]]:
        min_ratings = interaction.namespace.minimumratings
        year = interaction.namespace.year if interaction.namespace.year is not None else datetime.now().year
        max_num_albums = get_max_albums_possible(get_all_ratings, year=year, minratings=min_ratings)
        return [Choice(name=str(num), value=num)
                for num in range(1, max_num_albums+1) if str(current) in str(num)]
    return inner


# gets choices for num albums as part of top_albums command
def autocomplete_top_albums_minratings(get_all_ratings):
    async def inner(interaction: Interaction, current: str) -> list[Choice[int]]:
        numalbums = interaction.namespace.numberofalbums
        year = interaction.namespace.year if interaction.namespace.year is not None else datetime.now().year
        max_min_num_ratings = get_min_ratings_possible(get_all_ratings, year=year, numalbums=numalbums)
        return [Choice(name=str(num), value=num)
                for num in range(1, max_min_num_ratings+1) if str(current) in str(num)]
    return inner
