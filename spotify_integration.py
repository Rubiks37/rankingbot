import config
import spotify.sync as spotify

spotifyClient = spotify.Client(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET)
spotifyUser = spotify.User.from_refresh_token(spotifyClient, config.SPOTIFY_REFRESH_TOKEN)

def get_album(artist_name, album_name):
    results = spotifyClient.search(f"{album_name} {artist_name}", types=["album"], limit=1)
    album = results[2][0]

    return album.artists[0].name, album.name, album.id, album.release_date, album.images[0].url

def search_album(current):
    results = spotifyClient.search(f"{current}", types=["album"], limit=10)
    return results[2]

def get_playlist(user):
    playlist_name = f"{user.display_name}'s Homework"

    playlist = None
    for pl in spotifyUser.get_playlists():
        if pl.name == playlist_name:
            playlist = pl
            break
    
    if playlist == None:
        playlist = spotifyUser.create_playlist(playlist_name, description="Your homework, managed by the Ranking Bot")
    return playlist

def add_album_to_playlist(user, album_id):
    playlist = get_playlist(user)
    album = spotifyClient.get_album(album_id)
    tracks = album.get_all_tracks()

    playlist_tracks = playlist.get_tracks()
    for track in tracks:
        exists = False
        for existing in playlist_tracks:
            if existing.id == track.id:
                exists = True
                break
        if exists:
            continue
        playlist.add_tracks(track)

def remove_album_from_playlist(user, album_id):
    playlist = get_playlist(user)
    album = spotifyClient.get_album(album_id)
    tracks = album.get_all_tracks()
    for track in tracks:
        playlist.remove_tracks(track)

def close_conn():
    spotifyUser.close()
    spotifyClient.close()
