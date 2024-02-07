from json import loads, dumps


class Config:
    def __init__(self):
        with open('config.json') as file:
            self._config = loads(file.read())

    def __getattr__(self, name: str):
        try:
            return self._config[name.upper()]
        except KeyError:
            raise AttributeError(name + ' is not a valid config setting')

    def set_attribute(self, name: str, value):
        try:
            self._config[name] = value
            data = dumps(self._config, indent=3)
            # i don't actually know if this will ever be called
            if not data:
                raise AttributeError('config settings are empty, cannot set attribute')
            with open('config.json', 'w') as file:
                file.write(data)
        except KeyError:
            raise AttributeError(name + ' is not a valid config setting')
