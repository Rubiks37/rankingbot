from config import Config
import spotify.sync as spotify
from spotify import errors as spotify_errors

config = Config()

spotifyClient = spotify.Client(config.spotify_client_id, config.spotify_client_secret)
spotifyUser = spotify.User.from_refresh_token(spotifyClient, config.spotify_refresh_token)


# uses an id to find an album, and if no id is given, searches for the top result in spotify
# returns tuple (artist, album, id, release date, image url)
def get_album(artist_name: tuple = None, album_name=None, album_id=None):
    if artist_name is None and album_name is None and album_id is None:
        raise ValueError("error: no artist, album, or id was entered")
    elif album_id is not None:
        try:
            album = spotifyClient.get_album(spotify_id=album_id)
        except spotify_errors.HTTPException:
            raise ValueError("error: an invalid id was entered, maybe because you didnt select an autocomplete option")
    else:
        artists = " ".join(artist_name)
        results = spotifyClient.search(f"{album_name} {artists}", types=["album"], limit=1)
        if results[2] is None:
            raise LookupError("error: no results found in spotify database")
        album = results[2][0]
    artists = tuple(artist.name for artist in album.artists)
    return artists, album.name, album.id, album.release_date, album.images[0].url
    # return album.artists[0].name, album.name, album.id, album.release_date, album.images[0].url


async def search_album(current):
    results = spotifyClient.search(f"{current}", types=["album"], limit=25)
    return tuple(results[2])


def get_playlist(user):
    playlist_name = f"{user.display_name}'s Homework"

    playlist = None
    for pl in spotifyUser.get_playlists():
        if pl.name == playlist_name:
            playlist = pl
            break
    
    if playlist is None:
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


def close_spotify_conn():
    spotifyClient.close()
    spotifyUser.close()
