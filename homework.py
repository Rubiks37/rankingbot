import spotify_integration as spotify

def create_homework_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS homework(album_id TEXT, user_id INTEGER, complete BIT, PRIMARY KEY("user_id","album_id"))''')
    conn.commit()

def add_homework(conn, user_id, album_id):
    try:
        create_homework_table(conn)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO homework (album_id, user_id, complete) VALUES (?, ?, 0)''', (album_id, user_id))
        cursor.close()
        conn.commit()
    except:
        pass

def get_homework(conn, user, complete=0):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT * FROM homework
                   INNER JOIN album_master ON homework.album_id = album_master.id
                   WHERE user_id = {user.id} AND complete = {complete}''')
    data = cursor.fetchall()
    cursor.close()

    output = f'## Homework of {user.mention}\n'
    for i, row in enumerate(data):
        output += f'{i + 1}. {row[3]} - {row[4]} ({row[6]})\n'
    if len(data) == 0:
        output += f"{user.display_name} doesn't have any homework at the moment\n"
    return output + f"\nPlaylist URL: {spotify.get_playlist(user).url}"

def remove_homework(conn, user_id, album_id):
    create_homework_table(conn)
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM homework WHERE album_id = ? AND user_id = ?''', (album_id, user_id))
    cursor.close()
    conn.commit()