import sqlite3
from itertools import repeat
from spotify import Album
from datetime import datetime
from spotify_integration import get_playlist, get_album


class BaseTable:

    def __init__(self, conn: sqlite3.Connection,
                 name: str,
                 cols: tuple,
                 col_types: tuple,
                 primary_key: str = None,
                 create_table_appendix: str = ' '):
        self.conn = conn
        self.cols = cols
        self.col_types = col_types
        self.name = name
        self.primary_key = primary_key
        self.create_table(create_table_appendix)

    def __call__(self, query, input_row: tuple = tuple(), error_handle_graceful: bool = False):
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, input_row)
        except sqlite3.Error as error:
            if error_handle_graceful:
                print('ignoring exception\nquery: ' + query + '\nparams:' + str(input_row) + '\nerror: ' + str(error))
            else:
                print('query: ' + query + '\nparams:' + str(input_row) + '\nerror: ' + str(error))
                raise error
        data = cursor.fetchall()
        cursor.close()
        self.conn.commit()
        return data

    def executemany(self, query, input_rows: list):
        cursor = self.conn.cursor()
        try:
            cursor.executemany(query, input_rows)
        except sqlite3.Error as error:
            raise ValueError('error: could not properly select from table\nquery:', query, '\nerror:', str(error))
        data = cursor.fetchall()
        cursor.close()
        self.conn.commit()
        return data

    def create_table(self, appendix=' '):
        cols = tuple(f'{col} {col_type}' for col, col_type in zip(self.cols, self.col_types))
        query = f'''CREATE TABLE IF NOT EXISTS {self.name} ({', '.join(cols) + appendix})'''
        return self(query)

    def insert_single_row(self, row: tuple, appendix=' '):
        if len(row) != len(self.cols):
            raise ValueError('error, invalid row')

        # itertools repeat creates a list of '?' for each column
        query = f'''
        INSERT INTO {self.name} {self.cols}
        VALUES ({', '.join(repeat('?', len(self.cols)))}) RETURNING *''' + appendix
        return self(query, row)

    def insert_multiple_rows(self, rows: list):
        # checking each row to make sure they are all proper length
        if not all([len(row) == len(self.cols) for row in rows]):
            raise ValueError('error, invalid row included')

        # itertools repeat creates a list of '?' for each column
        query = f'''
        INSERT INTO {self.name} {self.cols} 
        VALUES ({', '.join(repeat('?', len(self.cols)))}) RETURNING *'''
        return self.executemany(query, rows)

    def get_full_table(self):
        return self(f'''SELECT * FROM {self.name}''')

    def get_ids(self):
        return {album['album_id'] for album in self(f'''SELECT album_id FROM {self.name}''')}


# ALBUM_MASTER TABLE INTERACTIONS SECTION------------------------------------------------------------------------------
# album_master is a table that has every single album that is currently in anyone's rankings/homework currently stored
# it stores properly formatted artist name (0), album name (1), the spotify album id (2),
# the release year (3) and a hyperlink to the cover image (4)
class MasterTable(BaseTable):
    def __init__(self, conn: sqlite3.Connection):
        cols = ('album_id', 'album_name', 'artist', 'year', 'album_cover_url')
        col_types = ('VARCHAR(25) PRIMARY KEY', 'VARCHAR(255)', 'JSON', 'INTEGER', 'VARCHAR(255)')
        super().__init__(conn, 'master_table', cols, col_types, primary_key='album_id')

    def insert_single_row(self, row: tuple, appendix=' '):
        if len(row) != len(self.cols):
            raise ValueError('error, invalid row')

        # itertools repeat creates a list of '?' for each column
        query = f'''
        INSERT OR IGNORE INTO {self.name} {self.cols}
        VALUES ({', '.join(repeat('?', len(self.cols)))}) RETURNING *''' + appendix
        return self(query, row)

    def add_row(self, album: Album):
        album_id = album.id
        album_name = album.name
        artist_names = [artist.name for artist in album.artists]
        year = datetime.fromisoformat(album.release_date).year
        album_cover_url = next(iter(album.images)).url

        # in this case where we are adding rows that may cause a primary key conflict, we can ignore primary key errors
        self.insert_single_row((album_id, album_name, artist_names, year, album_cover_url))

    def get_row(self, album_id):
        return self(f'''SELECT * FROM {self.name} WHERE album_id = ?''', tuple([album_id]))

    def remove_row(self, album_id):
        return self(f'''DELETE FROM {self.name} WHERE album_id = ? RETURNING *''', tuple([album_id]))

    # this function is called via command and should refresh the master list
    async def update_master_table(self, rating_table, homework_table):
        master_ids = self.get_ids()
        user_album_ids = rating_table.get_ids()
        homework_album_ids = homework_table.get_ids()

        # finding albums in master but aren't in other tables
        master_v_user_uniques = master_ids - user_album_ids
        master_v_homework_uniques = master_ids - homework_album_ids
        master_only_differences = master_v_homework_uniques & master_v_user_uniques
        for album_id in master_only_differences:
            self.remove_row(album_id)

        # finding albums in user_album or homework but not in master
        add_to_master = (user_album_ids | homework_album_ids) - master_ids
        for album_id in add_to_master:
            album = get_album(album_id=album_id)
            self.add_row(album)


class RatingTable(BaseTable):
    def __init__(self, conn: sqlite3.Connection):
        cols = ('album_id', 'user_id', 'rating')
        col_types = ('VARCHAR(25)', 'INTEGER', 'FLOAT')
        appendix = (', FOREIGN KEY (album_id) REFERENCES master_table(album_id) '
                    'PRIMARY KEY (album_id, user_id)')
        super().__init__(conn, 'rating_table', cols, col_types,
                         primary_key='album_id', create_table_appendix=appendix)

    def get_full_table(self):
        return self(f'''SELECT * FROM {self.name} INNER JOIN master_table USING(album_id)''')

    def get_users_ratings(self, user_id: int):
        return self(f'''SELECT * FROM {self.name} INNER JOIN master_table USING(album_id)
                    WHERE user_id = ? ORDER BY rating DESC''', tuple([user_id]))

    def get_single_album_ratings(self, album_id):
        return self(f'''SELECT rating FROM {self.name} WHERE album_id = ?''', tuple([album_id]))

    def get_users(self):
        user_rows = self(f'''SELECT DISTINCT user_id FROM {self.name}''')
        return [row['user_id'] for row in user_rows]

    def get_grouped_ratings(self):
        # group concatenates all the ratings together with commas so i can split later
        data = self(f'''SELECT GROUP_CONCAT(rating) AS ratings, artist, album_name, album_id, year FROM {self.name} 
        INNER JOIN master_table USING (album_id) GROUP BY album_id''')

        # splits ratings into lists for each album
        for album in data:
            # needs each rating (separated by commas) to be a float, so cast using map
            album['ratings'] = list(map(float, album['ratings'].split(',')))
        return data

    # transforms rows into nice looking string
    def get_user_ratings_formatted(self, user_id, year=datetime.now().year):
        rows = [row for row in self.get_users_ratings(user_id) if int(row['year']) == int(year) or int(year) == -1]
        rankings_str = ''
        for i, row in enumerate(rows):
            ranking_str = f'{i + 1}. ' + ", ".join(row['artist']) + f" - {row['album_name']} ({row['rating']})"
            rankings_str += ranking_str + '\n'
        return rankings_str

    def get_single_rating(self, user_id, album_id):
        return self(f'''SELECT * FROM {self.name} WHERE user_id = ? AND album_id = ?''',
                    (user_id, album_id))

    def add_row(self, album_id: str, user_id: int, rating: float):
        return self.insert_single_row((album_id, user_id, rating))

    def edit_row(self, album_id: str, user_id: int, new_rating: float):
        return self(f'''UPDATE {self.name} SET rating = ? WHERE user_id = ? AND album_id = ? 
        RETURNING *''', (new_rating, user_id, album_id))

    def remove_row(self, album_id: str, user_id: int):
        return self(f'''DELETE FROM {self.name} WHERE album_id = ? AND user_id = ? 
        RETURNING *''', (album_id, user_id))


class HomeworkTable(BaseTable):
    def __init__(self, conn: sqlite3.Connection):
        name = 'homework_table'
        cols = ('album_id', 'user_id', 'complete')
        col_types = ('VARCHAR(25)', 'INTEGER', 'BIT')
        appendix = ', PRIMARY KEY (album_id, user_id)'
        super().__init__(conn, name, cols, col_types, create_table_appendix=appendix)

    def add_homework(self, user_id, album_id):
        try:
            data = self(f'''INSERT INTO {self.name} (album_id, user_id, complete) VALUES (?, ?, 0) RETURNING *''',
                        (album_id, user_id))
        except sqlite3.Error as error:
            if error.sqlite_errorcode is sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
                raise ValueError("error: you cannot add duplicate entries into your homework list")
            else:
                raise error
        return f"successfully added {len(data)} row to homework"

    # returns a specific users homework
    def get_homework(self, user_id, complete=0):
        return self(f'''SELECT * FROM {self.name}
                       INNER JOIN master_table USING(album_id)
                       WHERE user_id = ? AND complete = ?''', (user_id, complete))

    def get_all_homework_rows(self, complete=0):
        return self(f'''SELECT * FROM {self.name}
                       INNER JOIN master_table ON homework.album_id = album_master.id
                       WHERE complete = ?''', (complete,))

    def remove_homework(self, user_id, album_id):
        data = self(f'''DELETE FROM {self.name} WHERE album_id = ? AND user_id = ? RETURNING *''',
             (album_id, user_id))
        if data is None:
            raise ValueError("error: row not found in your homework")
        return f"successfully deleted {len(data)} rows from homework"

    def get_homework_formatted(self, user, complete=0):
        data = self.get_homework(user.id, complete)
        output = f'## Homework of {user.mention}\n'
        for i, row in enumerate(data):
            output += f"{i + 1}. " + ", ".join(row['artist']) + f" - {row['album_name']} ({row['year']})\n"
        if len(data) == 0:
            output += f"{user.display_name} doesn't have any homework at the moment\n"
        return output + f"\nPlaylist URL: {get_playlist(user).url}"


# this is for sqlite3 connection to transform rows into dictionaries
def dict_factory(cursor: sqlite3.Cursor, row):
    cols = [col[0] for col in cursor.description]
    return {key: value for key, value in zip(cols, row)}
