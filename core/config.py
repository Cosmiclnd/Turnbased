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
    __slots__ = ("data",)

    def __init__(self, data):
        self.data = data

class TargetConfig(Config):
    __slots__ = ("target", "nameid", "name", "skills")

    def __init__(self, data, t):
        super().__init__(data)
        self.target = t
        self.nameid = data["nameid"]
        self.name = data["name"]
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
    
    def get_skill_desc(self, skill_name):
        skill = self.skills[skill_name]
        desc = skill["desc"].replace("{", "*{").replace("}", "}*")
        values = {}
        for name in skill["values"]:
            if skill["category"] in self.target.skills:
                for s in self.target.skills[skill["category"]].skills:
                    if s.skill_name == skill_name:
                        values[name] = s.get_value(name)
            else:
                values[name] = self.get_skill_value(skill_name, name)
        return desc.format(**values)

class CharacterConfig(TargetConfig):
    __slots__ = ("base_stats", "traces_stats")
    
    def __init__(self, data, t):
        super().__init__(data, t)
        self.base_stats = data["base_stats"]
        self.base_stats["base_break_dmg"] = [54, 3767.5533]
        self.base_stats["crt_rate"] = [0.05, 0.05]
        self.base_stats["crt_dmg"] = [0.5, 0.5]
        self.base_stats["energy_regen_rate"] = [1, 1]
        self.traces_stats = data["traces_stats"]
    
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

class MonsterConfig(TargetConfig):
    __slots__ = ()

    def __init__(self, data, t):
        super().__init__(data, t)
    
    def init(self):
        self.target.tier = enums.MonsterTier.dict_nameid[self.data["tier"]]
        self.target.base_weakness = list(map(lambda x: enums.Element.dict_nameid[x], self.data["weakness"]))
    
    def set_base_stats(self):
        for stat_name in ("hp", "atk", "def", "spd"):
            self.target.stats[stat_name].base_value = target.Monster.get_base_stat(
                stat_name, self.target.level, self.target.moc) * self.data["base_stat_scales"][stat_name]
        for stat_name in ("eff_hr", "eff_res"):
            self.target.stats[stat_name].base_value = target.Monster.get_base_stat(
                stat_name, self.target.level, self.target.moc) + self.data["base_stat_flats"][stat_name]
        for element in enums.Element.ALL:
            self.target.stats[f"{element.nameid}_res"].base_value = self.data["base_dmg_res"][element.nameid]
        self.target.stats["toughness"].base_value = self.data["toughness"]
