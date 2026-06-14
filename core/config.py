import importlib

import json
import target
import enums
import modifier
import skill

config_data_cache = {}

def load_config_data(category, nameid):
    name = category + "." + nameid
    if name not in config_data_cache:
        with open(f"core/config/{category}/{nameid}.json", "r") as f:
            config_data_cache[name] = json.load(f)
    return config_data_cache[name]

def load_class(category, nameid):
    name = nameid.replace("_", " ").title().replace(" ", "")
    module = importlib.import_module(category + "." + nameid)
    return getattr(module, name)

class Config:
    __slots__ = ("data",)

    def __init__(self, data):
        self.data = data
