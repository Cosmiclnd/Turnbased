import item

class Enum:
    @classmethod
    def init(cls):
        cls.dict_nameid = {}
        cls.dict_name = {}
        for e in cls.ALL:
            cls.dict_nameid[e.nameid] = e
            cls.dict_name[e.name] = e

class Element(Enum):
    PHYSICAL = item.Item("physical", "Physical")
    FIRE = item.Item("fire", "Fire")
    ICE = item.Item("ice", "Ice")
    LIGHTNING = item.Item("lightning", "Lightning")
    WIND = item.Item("wind", "Wind")
    QUANTUM = item.Item("quantum", "Quantum")
    IMAGINARY = item.Item("imaginary", "Imaginary")
    ALL = (PHYSICAL, FIRE, ICE, LIGHTNING, WIND, QUANTUM, IMAGINARY)
Element.init()

class Path(Enum):
    DESTRUCTION = item.Item("destruction", "Destruction")
    THE_HUNT = item.Item("the_hunt", "The Hunt")
    ERUDITION = item.Item("erudition", "Erudition")
    HARMONY = item.Item("harmony", "Harmony")
    NIHILITY = item.Item("nihility", "Nihility")
    PRESERVATION = item.Item("preservation", "Preservation")
    ABUNDANCE = item.Item("abundance", "Abundance")
    ALL = (DESTRUCTION, THE_HUNT, ERUDITION, HARMONY, NIHILITY, PRESERVATION, ABUNDANCE)
Path.init()

class MonsterTier(Enum):
    NORMAL = item.Item("normal", "Normal")
    ELITE = item.Item("elite", "Elite")
    BOSS = item.Item("boss", "Boss")
    EOW = item.Item("eow", "Echo of War")
    ALL = (NORMAL, ELITE, BOSS, EOW)
MonsterTier.init()
