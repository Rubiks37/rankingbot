from json import loads, dumps
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    token: str
    guild: int
    ranking_channels: dict
    changelog_active: bool
    changelog_channel: int
    mod_id: int
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str

    @classmethod
    def from_file(cls, config_file_name):
        with open(config_file_name) as file:
            raw_data = loads(file.read())
        data = {key.lower(): value for key, value in raw_data.items()}

        # since json stores keys as strings, the ranking_channel dict won't load properly, so we have to change it
        ranking_channels = {int(key): value for key, value in data.get("ranking_channels").items()}
        data.update({"ranking_channels": ranking_channels})
        return cls(**data)
