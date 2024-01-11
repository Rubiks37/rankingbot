from json import loads, dumps


class Config:
    def __init__(self):
        with open('config.json') as file:
            self.data = loads(file.read())

    def __getattr__(self, name: str):
        attribute = self.data.get(name.upper())
        if not attribute:
            raise AttributeError("error: config does not have a value called " + name)
        return attribute

    def __setattr__(self, name, value):
        if name == 'data':
            self.__dict__['data'] = value
            return
        try:
            self.data[name.upper()] = value
            with open('config.json', 'w') as file:
                file.write(dumps(self.data, indent=3))
        except KeyError:
            raise KeyError(name + ' is not a valid config setting')


# needs config.py to exist with already existing settings valid
def import_config_py_to_json():
    final_dict = {}

    with open("old_config.py") as file:
        for line in file.readlines():
            if '=' in line:
                var_name, var_value = line.split('=', 1)
                final_dict[var_name.strip()] = var_value.strip().strip('"')

    with open('config.json', 'w') as file:
        json_object = dumps(final_dict, indent=3)
        file.write(json_object)
