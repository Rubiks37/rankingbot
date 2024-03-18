import spotify.sync as spotify
from spotify import errors as spotify_errors
from dataclasses import dataclass


@dataclass
class Spotify:
    client_id: str
    client_secret: str
    client_refresh: str

    def __post_init__(self):
        self.spotify_client = spotify.Client(self.client_id, self.client_secret)
        self.spotify_user = spotify.User.from_refresh_token(self.spotify_client, self.client_refresh)

    # uses an id to find an album, and if no id is given, searches for the top result in spotify
    # returns tuple (artist, album, id, release date, image url)
    def get_album(self, artist_name: tuple = None, album_name=None, album_id=None) -> spotify.Album:
        if artist_name is None and album_name is None and album_id is None:
            raise ValueError("error: no artist, album, or id was entered")
        elif album_id is not None:
            try:
                album = (self.spotify_client.get_album(spotify_id=album_id))
            except spotify_errors.HTTPException:
                raise ValueError("error: an invalid id was entered. (hint: select an autocomplete option)")
        else:
            artists = " ".join(artist_name)
            results = self.spotify_client.search(f"{album_name} {artists}", types=["album"], limit=1)
            if results[2] is None:
                raise LookupError("error: no results found in spotify database")
            album = results[2][0]
        return album

    async def search_album(self, search_str: str):
        results = self.spotify_client.search(f"{search_str}", types=["album"], limit=25)
        return tuple(results[2])

    def get_playlist(self, user):
        playlist_name = f"{user.display_name}'s Homework"

        playlist = None
        for pl in self.spotify_user.get_playlists():
            if pl.name == playlist_name:
                playlist = pl
                break

        if playlist is None:
            playlist = self.spotify_user.create_playlist(playlist_name,
                                                         description="Your homework, managed by the Ranking Bot")
        return playlist

    def add_album_to_playlist(self, user, album_id):
        playlist = self.get_playlist(user)
        album = self.spotify_client.get_album(album_id)
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

    def remove_album_from_playlist(self, user, album_id):
        playlist = self.get_playlist(user)
        album = self.spotify_client.get_album(album_id)
        tracks = album.get_all_tracks()
        for track in tracks:
            playlist.remove_tracks(track)

    def close_spotify_conn(self):
        self.spotify_client.close()
