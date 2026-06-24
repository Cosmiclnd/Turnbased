import item
import config
import enums
import target

class LightCone(item.Item):
    class LightConeConfig(config.SkillsConfig):
        __slots__ = ("lightcone", "nameid", "name", "base_stat_scales")

        def __init__(self, data, lightcone):
            super().__init__(data)
            self.lightcone = lightcone
            self.nameid = data["nameid"]
            self.name = data["name"]
            self.base_stat_scales = data["base_stat_scales"]
        
        def init(self):
            self.lightcone.rarity = self.data["rarity"]
            self.lightcone.path = enums.Path.dict_nameid[self.data["path"]]
        
        def set_base_stats(self):
            scale = 21.05 * (self.lightcone.level - 1) / 79 + 1
            self.lightcone.base_stats["hp"] = self.base_stat_scales["hp"] * scale * 4.8
            self.lightcone.base_stats["atk"] = self.base_stat_scales["atk"] * scale * 2.4
            self.lightcone.base_stats["def"] = self.base_stat_scales["def"] * scale * 3

    def __init__(self, nameid, record):
        self.config = self.LightConeConfig(config.load_config_data("lightcones", nameid), self)
        if nameid != self.config.nameid:
            logging.warning(f"Light Cone nameid mismatch: {nameid} != {self.config['nameid']}")
        
        super().__init__(nameid, self.config.name, None)
        self.config.init()
        self.base_stats = {}
        self.target = None
        self.valid = None
        self.level = None
        self.stacks = None

        self.set_record(record)
    
    def apply(self, t):
        self.target = t
        self.valid = self.target.path is self.path
        for stat_name, value in self.base_stats.items():
            self.target.stats[stat_name].base_value += value
    
    def get_record(self):
        return {
            "name": self.nameid,
            "level": self.level,
            "stacks": self.stacks
        }
    
    def set_record(self, record):
        self.level = record["level"]
        self.stacks = record["stacks"]
        self.config.set_base_stats()
    
    def get_value(self, name):
        return self.config.get_skill_value("skill", name, stacks=self.stacks)
