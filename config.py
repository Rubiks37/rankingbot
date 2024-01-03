from json import loads, dumps


class Config:
    def __init__(self):
        with open('config.json') as file:
            self.data = loads(file.read())
            self.token = self.data.get("TOKEN")
            self.guild = self.data.get("GUILD")
            self.ranking_channel = self.data.get("RANKING_CHANNEL")
            self.command_channel = self.data.get("COMMAND_CHANNEL")
            self.changelog_channel = self.data.get("CHANGELOG_CHANNEL")
            self.changelog_active = self.data.get("CHANGELOG_ACTIVE")
            self.mod_id = self.data.get("MOD_ID")
            self.spotify_client_id = self.data.get("SPOTIFY_CLIENT_ID")
            self.spotify_client_secret = self.data.get("SPOTIFY_CLIENT_SECRET")
            self.spotify_refresh_token = self.data.get("SPOTIFY_REFRESH_TOKEN")

    def change_config(self, attribute, new_value):
        try:
            self.data[attribute] = new_value
            with open('config.json') as file:
                file.write(dumps(self.data, indent=3))
        except KeyError:
            raise KeyError(attribute + ' is not a valid config setting')


# needs config.py to exist with already existing settings valid
def import_config_py_to_json():
    final_dict = {}

    with open("config.py") as file:
        for line in file.readlines():
            if '=' in line:
                var_name, var_value = line.split('=', 1)
                final_dict[var_name.strip()] = var_value.strip().strip('"')

    with open('config.json', 'w') as file:
        json_object = dumps(final_dict, indent=3)
        file.write(json_object)