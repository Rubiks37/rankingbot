import config
import spotify.sync as spotify

spotifyClient = spotify.Client(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET)
spotifyUser = spotify.User.from_refresh_token(spotifyClient, config.SPOTIFY_REFRESH_TOKEN)


def get_album(artist_name, album_name):
    results = spotifyClient.search(f"{album_name} {artist_name}", types=["album"], limit=1)
    album = results[2][0]

    return album.id, album.name, album.artists[0].name, album.release_date, album.images[0].url


def search_album(current):
    results = spotifyClient.search(f"{current}", types=["album"], limit=10)
    return results[2]


def spotify_close_conn():
    spotifyUser.close()
    spotifyClient.close()
