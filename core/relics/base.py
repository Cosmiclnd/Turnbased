import item
import enums
import modifier
import config

class RelicType(enums.Enum):
    HEAD = item.Item("head", "Head")
    HANDS = item.Item("hands", "Hands")
    BODY = item.Item("body", "Body")
    FEET = item.Item("feet", "Feet")
    PLANAR_SPHERE = item.Item("planar_sphere", "Planar Sphere")
    LINK_ROPE = item.Item("link_rope", "Link Rope")
    ALL = (HEAD, HANDS, BODY, FEET, PLANAR_SPHERE, LINK_ROPE)
RelicType.init()

class RelicStatType:
    def name(self):
        return self.stat_name + ("%" if self.is_percentage else "")

    @classmethod
    def init(cls):
        cls.dict = {}
        for stat in cls.ALL:
            cls.dict[stat.name()] = stat

class RelicMainStatType(RelicStatType):
    def __init__(self, stat_name, base, step, is_percentage=False):
        self.stat_name = stat_name
        self.base = base
        self.step = step
        self.is_percentage = is_percentage
    
    def get_stat(self, t):
        return t.stats[self.stat_name]
    
    def get_modifier(self, t, level):
        value = self.base + self.step * level
        if self.is_percentage:
            mod = modifier.Modifier(self.stat_name, self.stat_name, modifier.StatDesc((self.get_stat(t), modifier.ModifierFilter.BASE, value)), None, t)
        else:
            mod = modifier.Modifier(self.stat_name, self.stat_name, modifier.StatDesc((None, None, value)), None, t)
        return mod

RelicMainStatType.SPD = RelicMainStatType("spd", 4.032, 1.4)
RelicMainStatType.HP = RelicMainStatType("hp", 112.896, 39.5136)
RelicMainStatType.ATK = RelicMainStatType("atk", 56.448, 19.7568)
RelicMainStatType.HP_PERCENT = RelicMainStatType("hp", 0.06912, 0.024192, True)
RelicMainStatType.ATK_PERCENT = RelicMainStatType("atk", 0.06912, 0.024192, True)
RelicMainStatType.DEF_PERCENT = RelicMainStatType("def", 0.0864, 0.03024, True)
RelicMainStatType.BREAK_EFFECT = RelicMainStatType("break_effect", 0.10368, 0.036288)
RelicMainStatType.EFF_HR = RelicMainStatType("eff_hr", 0.06912, 0.024192)
RelicMainStatType.ENERGY_REGEN_RATE = RelicMainStatType("energy_regen_rate", 0.031104, 0.010886)
RelicMainStatType.HEALING_BOOST = RelicMainStatType("outgoing_healing_boost", 0.055296, 0.019354)
RelicMainStatType.PHYSICAL_DMG_BOOST = RelicMainStatType("physical_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.FIRE_DMG_BOOST = RelicMainStatType("fire_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.ICE_DMG_BOOST = RelicMainStatType("ice_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.WIND_DMG_BOOST = RelicMainStatType("wind_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.LIGHTNING_DMG_BOOST = RelicMainStatType("lightning_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.QUANTUM_DMG_BOOST = RelicMainStatType("quantum_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.IMAGINARY_DMG_BOOST = RelicMainStatType("imaginary_dmg_boost", 0.062208, 0.021773)
RelicMainStatType.CRT_RATE = RelicMainStatType("crt_rate", 0.05184, 0.018144)
RelicMainStatType.CRT_DMG = RelicMainStatType("crt_dmg", 0.10368, 0.036288)
RelicMainStatType.ALL = (RelicMainStatType.SPD,
    RelicMainStatType.HP, RelicMainStatType.ATK,
    RelicMainStatType.HP_PERCENT, RelicMainStatType.ATK_PERCENT, RelicMainStatType.DEF_PERCENT,
    RelicMainStatType.BREAK_EFFECT, RelicMainStatType.EFF_HR, RelicMainStatType.ENERGY_REGEN_RATE, RelicMainStatType.HEALING_BOOST,
    RelicMainStatType.PHYSICAL_DMG_BOOST, RelicMainStatType.FIRE_DMG_BOOST, RelicMainStatType.ICE_DMG_BOOST, RelicMainStatType.WIND_DMG_BOOST,
    RelicMainStatType.LIGHTNING_DMG_BOOST, RelicMainStatType.QUANTUM_DMG_BOOST, RelicMainStatType.IMAGINARY_DMG_BOOST,
    RelicMainStatType.CRT_RATE, RelicMainStatType.CRT_DMG)
RelicMainStatType.init()

RelicMainStatType.CHOICES = {
    RelicType.HEAD: {RelicMainStatType.HP: 1},
    RelicType.HANDS: {RelicMainStatType.ATK: 1},
    RelicType.BODY: {
        RelicMainStatType.HP_PERCENT: 0.2,
        RelicMainStatType.ATK_PERCENT: 0.2,
        RelicMainStatType.DEF_PERCENT: 0.2,
        RelicMainStatType.EFF_HR: 0.1,
        RelicMainStatType.HEALING_BOOST: 0.1,
        RelicMainStatType.CRT_RATE: 0.1,
        RelicMainStatType.CRT_DMG: 0.1
    },
    RelicType.FEET: {
        RelicMainStatType.HP_PERCENT: 0.3,
        RelicMainStatType.ATK_PERCENT: 0.3,
        RelicMainStatType.DEF_PERCENT: 0.3,
        RelicMainStatType.SPD: 0.1
    },
    RelicType.PLANAR_SPHERE: {
        RelicMainStatType.HP_PERCENT: 4 / 33,
        RelicMainStatType.ATK_PERCENT: 4 / 33,
        RelicMainStatType.DEF_PERCENT: 4 / 33,
        RelicMainStatType.PHYSICAL_DMG_BOOST: 1 / 11,
        RelicMainStatType.FIRE_DMG_BOOST: 1 / 11,
        RelicMainStatType.ICE_DMG_BOOST: 1 / 11,
        RelicMainStatType.WIND_DMG_BOOST: 1 / 11,
        RelicMainStatType.LIGHTNING_DMG_BOOST: 1 / 11,
        RelicMainStatType.QUANTUM_DMG_BOOST: 1 / 11,
        RelicMainStatType.IMAGINARY_DMG_BOOST: 1 / 11
    },
    RelicType.LINK_ROPE: {
        RelicMainStatType.HP_PERCENT: 0.25,
        RelicMainStatType.ATK_PERCENT: 0.25,
        RelicMainStatType.DEF_PERCENT: 0.25,
        RelicMainStatType.BREAK_EFFECT: 0.18,
        RelicMainStatType.ENERGY_REGEN_RATE: 0.7
    }
}

class RelicSubStatType(RelicStatType):
    def __init__(self, stat_name, weight, values, is_percentage=False):
        self.stat_name = stat_name
        self.weight = weight
        self.values = values
        self.is_percentage = is_percentage

    def get_stat(self, t):
        return t.stats[self.stat_name]
    
    def get_modifier(self, t, enhancements):
        value = 0
        for i in enhancements:
            value += self.values[i]
        if self.is_percentage:
            mod = modifier.Modifier(self.stat_name, self.stat_name, modifier.StatDesc((self.get_stat(t), modifier.ModifierFilter.BASE, value)), None, t)
        else:
            mod = modifier.Modifier(self.stat_name, self.stat_name, modifier.StatDesc((None, None, value)), None, t)
        return mod

RelicSubStatType.SPD = RelicSubStatType("spd", 4, (2, 2.3, 2.6))
RelicSubStatType.HP = RelicSubStatType("hp", 10, (33.87004, 38.103795, 42.33751))
RelicSubStatType.ATK = RelicSubStatType("atk", 10, (16.935, 19.051877, 21.168754))
RelicSubStatType.DEF = RelicSubStatType("def", 10, (16.935, 19.051877, 21.168754))
RelicSubStatType.HP_PERCENT = RelicSubStatType("hp", 10, (0.0346, 0.0389, 0.0432), True)
RelicSubStatType.ATK_PERCENT = RelicSubStatType("atk", 10, (0.0346, 0.0389, 0.0432), True)
RelicSubStatType.DEF_PERCENT = RelicSubStatType("def", 10, (0.0432, 0.0486, 0.054), True)
RelicSubStatType.BREAK_EFFECT = RelicSubStatType("break_effect", 8, (0.05184, 0.05832, 0.0648))
RelicSubStatType.EFF_HR = RelicSubStatType("eff_hr", 8, (0.03456, 0.03888, 0.0432))
RelicSubStatType.EFF_RES = RelicSubStatType("eff_res", 8, (0.03456, 0.03888, 0.0432))
RelicSubStatType.CRT_RATE = RelicSubStatType("crt_rate", 6, (0.02592, 0.02916, 0.0324))
RelicSubStatType.CRT_DMG = RelicSubStatType("crt_dmg", 6, (0.05184, 0.05832, 0.0648))
RelicSubStatType.ALL = (RelicSubStatType.SPD,
    RelicSubStatType.HP, RelicSubStatType.ATK, RelicSubStatType.DEF,
    RelicSubStatType.HP_PERCENT, RelicSubStatType.ATK_PERCENT, RelicSubStatType.DEF_PERCENT,
    RelicSubStatType.BREAK_EFFECT, RelicSubStatType.EFF_HR, RelicSubStatType.EFF_RES,
    RelicSubStatType.CRT_RATE, RelicSubStatType.CRT_DMG)
RelicSubStatType.init()

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
        self.main_stat_type = RelicMainStatType.dict[record["main_stat_type"]]
        self.sub_stat_types = [RelicSubStatType.dict[s] for s in record["sub_stat_types"]]
        self.enhancements = record["enhancements"]
    
    def apply(self, t):
        self.target = t
        modifiers = []
        modifiers.append((self.main_stat_type.get_stat(t), self.main_stat_type.get_modifier(t, self.level)))
        for i, sub_stat_type in enumerate(self.sub_stat_types):
            modifiers.append((sub_stat_type.get_stat(t), sub_stat_type.get_modifier(t, self.enhancements[i])))
        for stat, mod in modifiers:
            stat.modifiers.append(mod)
