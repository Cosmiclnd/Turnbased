import item
import enums
import modifier
import config
import effect
import event
import battle

class RelicType(enums.Enum):
    HEAD = item.Item("head", "Head")
    HANDS = item.Item("hands", "Hands")
    BODY = item.Item("body", "Body")
    FEET = item.Item("feet", "Feet")
    PLANAR_SPHERE = item.Item("planar_sphere", "Planar Sphere")
    LINK_ROPE = item.Item("link_rope", "Link Rope")
    ALL = (HEAD, HANDS, BODY, FEET, PLANAR_SPHERE, LINK_ROPE)
RelicType.init()

def get_stat(name, t):
    if name[-1] == "%":
        return t.stats[name[:-1]]
    return t.stats[name]

def get_modifier(type, name, t, bases, steps):
    data = config.load_config_data("relics", "values")[type][name]
    value = data["base"] * bases + data["step"] * steps
    if name[-1] == "%":
        return modifier.Modifier(f"relic_{type}_{name}", f"Relic {type.title()} Stat",
            modifier.StatDesc((get_stat(name, t), modifier.ModifierFilter.BASE, value)), None, t)
    else:
        return modifier.Modifier(f"relic_{type}_{name}", f"Relic {type.title()} Stat",
            modifier.StatDesc((None, None, value)), None, t)

def get_main_modifier(name, t, level):
    return get_modifier("main", name, t, 1, level)

def get_sub_modifier(name, t, enhancements):
    return get_modifier("sub", name, t, len(enhancements), sum(enhancements))

class RelicSet(item.Item):
    class RelicSetConfig(config.SkillsConfig):
        def __init__(self, data, relic_set):
            super().__init__(data)
            self.relic_set = relic_set
            self.nameid = data["nameid"]
            self.name = data["name"]

    class PiecesEffect:
        def __init__(self, t, relic_set, pieces):
            self.target = t
            self.relic_set = relic_set
            self.pieces = pieces
            self.effect_types = effect.EffectTypes(relic_set)

            battle.current.event_bus.add_member_listener(self.battle_start, t)
        
        def get_value_2pc(self, name):
            return self.relic_set.config.get_skill_value("2pc", name)
        
        def get_value_4pc(self, name):
            return self.relic_set.config.get_skill_value("4pc", name)
        
        async def effect_2pc(self):
            pass
            
        async def effect_4pc(self):
            pass
            
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def battle_start(self):
            if self.pieces >= 2:
                await self.effect_2pc()
            if self.pieces >= 4:
                await self.effect_4pc()
    
    def __init__(self, nameid):
        self.config = self.RelicSetConfig(config.load_config_data("relics", nameid), self)
        if nameid != self.config.nameid:
            logging.warning(f"Relic Set nameid mismatch: {nameid} != {self.config['nameid']}")
        
        super().__init__(nameid, self.config.name, None)
    
    def get_pieces_effect(self, t, pieces):
        return self.PiecesEffect(t, self, pieces)

relic_sets = []

def register_relic_set(relic_set_class):
    id = len(relic_sets)
    relic_set_class.id = id
    relic_sets.append(relic_set_class())

class Relic(item.Item):
    def __init__(self, relic_set, type):
        super().__init__(relic_set.nameid, relic_set.name)
        self.target = None
        self.relic_set = relic_set
        self.type = type
        self.level = None
        self.main_stat_type = None
        self.sub_stat_types = []
        self.enhancements = []
    
    def get_record(self):
        return {
            "name": self.nameid,
            "level": self.level,
            "main_stat_type": self.main_stat_type.name(),
            "sub_stat_types": [s.name() for s in self.sub_stat_types],
            "enhancements": self.enhancements,
        }
    
    def set_record(self, record):
        # `name`在target中被处理
        self.level = record["level"]
        self.main_stat_type = record["main_stat_type"]
        self.sub_stat_types = record["sub_stat_types"]
        self.enhancements = record["enhancements"]
    
    def apply(self, t):
        self.target = t
        get_stat(self.main_stat_type, t).modifiers.append(get_main_modifier(self.main_stat_type, t, self.level))
        for sub_stat_type, enhancements in zip(self.sub_stat_types, self.enhancements):
            get_stat(sub_stat_type, t).modifiers.append(get_sub_modifier(sub_stat_type, t, enhancements))
