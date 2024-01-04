from discord import Client
from spotify_integration import get_album

# the changelog is a channel where every single time an update is made to someones rankings/homework,
# it will send a message so everyone can see recent changes.
# all of this can be disabled by setting CHANGELOG_ACTIVE to False
# in an added album, the changes parameter is the album_id, followed by the rating


class Changelog:
    def __init__(self, client: Client, changelog_active):
        self.client = client
        self.changelog_active = changelog_active

        # this must be initialized after the bot has connected with discord,
        # so this is initialized with initialize_channel in on_ready in main
        self.channel = None

    async def initialize_channel(self, channel_id):
        self.channel = await self.client.fetch_channel(channel_id)

    @staticmethod
    def check_decorator(inner):
        def wrapper(self, *args, **kwargs):
            if self.changelog_active:
                return inner(self, *args, **kwargs)
        return wrapper

    @check_decorator
    async def event_add_ranking(self, user, album_id, rating, users=None):
        if user not in users:
            await self.channel.send(f"{user.mention} has just used ranking bot for the first time lfggggggg")
        row = get_album(album_id=album_id)
        artist = ", ".join(row[0])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`rated {artist} - {row[1]} as a {rating}`")

    # in an edited album, the changes parameter is the album_id, the old rating, and the new rating
    @check_decorator
    async def event_edit_ranking(self, user, album_id, old_rating, new_rating):
        row = get_album(album_id=album_id)
        artist = ", ".join(row[0])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`changed {artist} - {row[1]} from a {old_rating}/10.0 to a {new_rating}/10.0`")

    # in a removed album, the changes parameter is the album_id
    # we need to use spotify api since it may not be in album_master after the removal
    @check_decorator
    async def event_remove_ranking(self, user, album_id):
        row = get_album(album_id=album_id)
        artist = ", ".join(row[0])
        await self.channel.send(f"RANKINGS - {user.mention}:\n`removed {artist} - {row[1]} from their rankings`")

    # in an added homework album, the changes parameter is the album_id, then the user who initiated them
    @check_decorator
    async def event_add_homework(self, user, album_id, user_affected, users):
        if user not in users:
            await self.channel.send(f"{user.mention} has just used ranking bot for the first time lfggggggg")
        row = get_album(album_id=album_id)
        artist = ", ".join(row[0])
        if user.id == user_affected.id:
            await self.channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {row[1]} to their homework list`")
        else:
            await self.channel.send(f"HOMEWORK - {user.mention}:\n`added {artist} - {row[1]} to {user_affected.mention}'s homework list`")

    # in a finished homework album, the changes parameter is the album_id
    # we have to use spotify api because it may have been removed from album_master
    @check_decorator
    async def event_finish_homework(self, user, album_id):
        row = get_album(album_id=album_id)
        artist = ", ".join(row[0])
        await self.channel.send(f"HOMEWORK - {user.mention}:\n`listened to {artist} - {row[1]}`")

    @check_decorator
    async def event_add_bulk(self, user):
        await self.channel.send(f"RANKINGS - {user.mention} just added a bunch of new albums to their rankings")

    @check_decorator
    async def event_new_user(self, user):
        await self.channel.send(f"{user.mention} used rankingbot for the first time lfgggg")
