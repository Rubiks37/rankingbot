import config
import spotify.sync as spotify

spotifyClient = spotify.Client(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET)
spotifyUser = spotify.User.from_refresh_token(spotifyClient, config.SPOTIFY_REFRESH_TOKEN)

def get_album(artist, album_name):
    results = spotifyClient.search(f"{album_name} {artist}", types=["album"], limit=1)
    album = results[2][0]

    return (album.id, album.name, album.artists[0].name, album.images[0].url)