import spotify_integration as spotify


def create_homework_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS homework(
    album_id TEXT, user_id INTEGER, complete BIT, PRIMARY KEY("user_id","album_id"))''')
    conn.commit()


def add_homework(conn, user_id, album_id):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO homework (album_id, user_id, complete) VALUES (?, ?, 0) RETURNING *''', (album_id, user_id))
    data = cursor.fetchall()
    cursor.close()
    conn.commit()
    return f"successfully added {len(data)} row to homework"


# returns a specific users homework
# list structure: [album_id, user_id, complete, artist, album, album_id, year, image url]
def get_homework(conn, user_id, complete=0):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM homework
                   INNER JOIN album_master ON homework.album_id = album_master.id
                   WHERE user_id = ? AND complete = ?''', (user_id, complete))
    data = cursor.fetchall()
    cursor.close()
    return data


def get_all_homework_rows(conn, complete=0):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM homework
                   INNER JOIN album_master ON homework.album_id = album_master.id
                   WHERE complete = ?''', (complete,))
    data = cursor.fetchall()
    cursor.close()
    return data


def get_homework_formatted(conn, user, complete=0):
    data = get_homework(conn, user.id, complete)
    output = f'## Homework of {user.mention}\n'
    for i, row in enumerate(data):
        output += f'{i + 1}. {row[3]} - {row[4]} ({row[6]})\n'
    if len(data) == 0:
        output += f"{user.display_name} doesn't have any homework at the moment\n"
    return output + f"\nPlaylist URL: {spotify.get_playlist(user).url}"


# this is basically just making sure that an album exists for update_album_master
def get_homework_row(conn, album_id):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM homework
                   INNER JOIN album_master ON homework.album_id = album_master.id
                   WHERE album_id = ?''', (album_id,))
    data = cursor.fetchall()
    if len(data) == 0:
        return None
    cursor.close()
    return data[0]


def remove_homework(conn, user_id, album_id):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM homework WHERE album_id = ? AND user_id = ? RETURNING *''', (album_id, user_id))
    data = cursor.fetchall()
    cursor.close()
    conn.commit()
    if data is None:
        raise ValueError("error: row not found in your homework")
    return f"successfully deleted {len(data)} rows from homework"
