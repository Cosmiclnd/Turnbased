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

class Config:
    def __init__(self, data):
        self.data = data

class CharacterConfig(Config):
    def __init__(self, data, t):
        super().__init__(data)
        self.target = t
        self.nameid = data["nameid"]
        self.name = data["name"]
        self.base_stats = data["base_stats"]
        self.base_stats["base_break_dmg"] = [54, 3767.5533]
        self.base_stats["crt_rate"] = [0.05, 0.05]
        self.base_stats["crt_dmg"] = [0.5, 0.5]
        self.base_stats["energy_regen_rate"] = [1, 1]
        self.traces_stats = data["traces_stats"]
        self.skills = data["skills"]
    
    def init(self):
        self.target.element = enums.Element.dict_nameid[self.data["element"]]
        self.target.path = enums.Path.dict_nameid[self.data["path"]]
    
    def set_base_stats(self):
        for name, stats in self.base_stats.items():
            self.target.stats[name].base_value = target.lerp(stats[0], stats[1], (self.target.level - 1) / 79)
    
    def set_traces_stats(self):
        for i in range(len(self.traces_stats)):
            if self.target.traces_stats_unlocked[i]:
                stat = self.traces_stats[i]
                if stat["is_percentage"]:
                    stat_desc = modifier.StatDesc((self.target.stats[stat["stat_name"]], modifier.ModifierFilter.BASE, stat["value"]))
                else:
                    stat_desc = modifier.StatDesc((None, None, stat["value"]))
                mod = modifier.Modifier(stat["nameid"], stat["name"], stat_desc, None, self.target)
                self.target.stats[stat["stat_name"]].modifiers.append(mod)
    
    def get_skill_value(self, skill_name, name, **kwargs):
        value = self.skills[skill_name]["values"][name]
        if value["is_dynamic"]:
            return value["values"][kwargs[value["key"]] - 1]
        else:
            return value["value"]
    
    def get_skill_name(self, skill_name):
        skill = self.skills[skill_name]
        return skill["nameid"], skill["name"]
