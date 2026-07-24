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
    __slots__ = ("skills", "cached_values")

    def __init__(self, data):
        super().__init__(data)
        self.skills = data["skills"]
        self.cached_values = {}
        
    @staticmethod
    def get_value(value, **kwargs):
        if value["is_dynamic"]:
            return value["values"][kwargs[value["key"]] - 1]
        else:
            return value["value"]
    
    def get_skill_value(self, skill_name, name, **kwargs):
        if skill_name not in self.cached_values:
            self.cached_values[skill_name] = {}
        if name not in self.cached_values[skill_name]:
            self.cached_values[skill_name][name] = self.get_value(self.skills[skill_name]["values"][name], **kwargs)
        return self.cached_values[skill_name][name]
    
    def get_skill_name(self, skill_name):
        skill = self.skills[skill_name]
        return skill["nameid"], skill["name"]
