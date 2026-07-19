import importlib
import json

from . import enums
from . import modifier

config_data_cache = {}
core_config = None

def load_config_data(category, nameid):
    name = category + "." + nameid
    if name not in config_data_cache:
        with open(f"config/{category}/{nameid}.json", "r", encoding="utf-8") as f:
            config_data_cache[name] = json.load(f)
    return config_data_cache[name]

def load_class(category, nameid):
    name = nameid.replace("_", " ").title().replace(" ", "")
    module = importlib.import_module("." + nameid, package=f"core.{category}")
    return getattr(module, name)

class Config:
    __slots__ = ("data",)

    def __init__(self, data):
        self.data = data

class SkillsConfig(Config):
    __slots__ = ("skills",)

    def __init__(self, data):
        super().__init__(data)
        self.skills = data["skills"]
        
    @classmethod
    def get_value(self, value, **kwargs):
        if value["is_dynamic"]:
            return value["values"][kwargs[value["key"]] - 1]
        else:
            return value["value"]
    
    def get_skill_value(self, skill_name, name, **kwargs):
        return self.get_value(self.skills[skill_name]["values"][name], **kwargs)
    
    def get_skill_name(self, skill_name):
        skill = self.skills[skill_name]
        return skill["nameid"], skill["name"]
