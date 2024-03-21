from discord import TextChannel, User
from dataclasses import dataclass
from typing import Callable

# the changelog is a channel where every single time an update is made to someones rankings/homework,
# it will send a message so everyone can see recent changes.
# all of this can be disabled by setting CHANGELOG_ACTIVE to False
# in an added album, the changes parameter is the album_id, followed by the rating


@dataclass
class Changelog:
    changelog_active: bool
    get_album: Callable
    changelog_channel: int
    users: set[int]
    channel: TextChannel | None = None

    async def initialize_channel(self, client):
        self.channel = await client.fetch_channel(self.changelog_channel)

    @staticmethod
    def check_decorator(inner):
        def wrapper(self, *args, **kwargs):
            if self.changelog_active:
                return inner(self, *args, **kwargs)
            return None
        return wrapper

    @check_decorator
    async def event_add_ranking(self, user: User, album_id: str, rating: float):
        if user.id not in self.users:
            await self.event_new_user(user)
        album = self.get_album(album_id=album_id)
        artist = ", ".join([artist.name for artist in album.artists])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`rated {artist} - {album.name} as a {rating}`")

    # in an edited album, the changes parameter is the album_id, the old rating, and the new rating
    @check_decorator
    async def event_edit_ranking(self, user: User, album_id: str, old_rating: float, new_rating: float):
        album = self.get_album(album_id=album_id)
        artist = ", ".join([artist.name for artist in album.artists])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`changed {artist} - {album.name} from a {old_rating}/10.0 to a {new_rating}/10.0`")

    # in a removed album, the changes parameter is the album_id
    # we need to use spotify api since it may not be in album_master after the removal
    @check_decorator
    async def event_remove_ranking(self, user: User, album_id: str):
        album = self.get_album(album_id=album_id)
        artist = ", ".join([artist.name for artist in album.artists])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`removed {artist} - {album.name} from their rankings`")

    # in an added homework album, the changes parameter is the album_id, then the user who initiated them
    @check_decorator
    async def event_add_homework(self, user: User, album_id: str, user_affected: User):
        if user not in self.users:
            await self.event_new_user(user)
        album = self.get_album(album_id=album_id)
        artist = ", ".join([artist.name for artist in album.artists])
        if user.id == user_affected.id:
            await self.channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {album.name} to their homework list`")
        else:
            await self.channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {album.name} to {user_affected.mention}'s homework list`")

    # in a finished homework album, the changes parameter is the album_id
    # we have to use spotify api because it may have been removed from album_master
    @check_decorator
    async def event_finish_homework(self, user: User, album_id: str):
        album = self.get_album(album_id=album_id)
        artist = ", ".join([artist.name for artist in album.artists])
        await self.channel.send(f"HOMEWORK - {user.mention}:\n`listened to {artist} - {album.name}`")

    # honestly i just need to get rid of this functionality, i barely ever use it anywhere
    @check_decorator
    async def event_add_bulk(self, user: User):
        await self.channel.send(f"RANKINGS - {user.mention} just added a bunch of new albums to their rankings")

    @check_decorator
    async def event_new_user(self, user: User):
        self.users.remove(user.id)
        await self.channel.send(f"{user.mention} used rankingbot for the first time lfgggg")
