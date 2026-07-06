import copy
from collections.abc import Iterable

import battle
import enums
import modifier
import item

class DmgType(enums.Enum):
    NORMAL = item.Item("normal", "Normal")
    ADDITIONAL = item.Item("additional", "Additional")
    BREAK = item.Item("break", "Break")
    DOT = item.Item("dot", "DoT")
    ALL = (NORMAL, ADDITIONAL, BREAK)
DmgType.init()

class DmgSource(enums.Enum):
    BASIC_ATK = item.Item("basic_atk", "Basic ATK")
    SKILL = item.Item("skill", "Skill")
    ULTIMATE = item.Item("ultimate", "Ultimate")
    FOLLOW_UP = item.Item("follow_up", "Follow-Up")
    WEAKNESS_BREAK = item.Item("weakness_break", "Weakness Break")
    MONSTER = item.Item("monster", "Monster")
    ALL = (BASIC_ATK, SKILL, ULTIMATE, FOLLOW_UP, WEAKNESS_BREAK, MONSTER)
DmgSource.init()

class DamageFactorType:
    def __init__(self, func, base_func):
        self.func = func
        self.base_func = base_func

async def max_toughness_base_func(dmg):
    return dmg.target.stats["toughness"].calculate(damage=dmg) / 40 + 0.5

async def multiplier_base_func(dmg):
    if dmg.element in (enums.Element.FIRE, enums.Element.PHYSICAL):
        return 2
    elif dmg.element is enums.Element.WIND:
        return 1.5
    elif dmg.element in (enums.Element.QUANTUM, enums.Element.IMAGINARY):
        return 0.5
    else:
        return 1

async def crit_factor_func(dmg, value):
    if await battle.current.random.rate(dmg.dealer.stats["crt_rate"].calculate(damage=dmg)):
        dmg.crit = True
        return 1 + value
    return 1

async def crit_factor_base_func(dmg):
    return dmg.dealer.stats["crt_dmg"].calculate(damage=dmg)

async def dmg_boost_base_func(dmg):
    value = dmg.dealer.stats["dmg_boost"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.dealer.stats[f"{dmg.element.nameid}_dmg_boost"].calculate(damage=dmg)
    return value

async def defence_factor_func(dmg, value):
    value += dmg.target.stats["def"].calculate(modifier.ModifierFilter.BASE) * dmg.factors[DamageFactorType.DEF_BOOST]
    value = max(0, value)
    return 1 - value / (value + 200 + 10 * dmg.dealer.level)

async def defence_factor_base_func(dmg):
    return dmg.target.stats["def"].calculate(damage=dmg)

async def resistance_base_func(dmg):
    value = -dmg.dealer.stats["res_pen"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.target.stats[f"{dmg.element.nameid}_res"].calculate(damage=dmg)
        value -= dmg.dealer.stats[f"{dmg.element.nameid}_res_pen"].calculate(damage=dmg)
    return value

async def mitigation_factor_base_func(dmg):
    from monsters import base as monster  # TODO: Python 3.15 lazy import
    if isinstance(dmg.target, monster.Monster) and not dmg.target.weakness_broken:
        return 0.9
    return 1

async def break_eff_base_func(dmg):
    return dmg.dealer.stats["break_eff"].calculate(damage=dmg)

def async_func(func):
    async def wrapper(*args):
        return func(*args)
    return wrapper

DamageFactorType.MAX_TOUGHNESS = DamageFactorType(async_func(lambda dmg, value: value), max_toughness_base_func)
DamageFactorType.MULTIPLIER = DamageFactorType(async_func(lambda dmg, value: value), multiplier_base_func)  # 指击破的倍率
DamageFactorType.CRIT = DamageFactorType(crit_factor_func, crit_factor_base_func)
DamageFactorType.DMG_BOOST = DamageFactorType(async_func(lambda dmg, value: 1 + value), dmg_boost_base_func)
DamageFactorType.WEAKEN = DamageFactorType(async_func(lambda dmg, value: 1 - value), async_func(lambda dmg: 0))
DamageFactorType.DEFENCE = DamageFactorType(defence_factor_func, defence_factor_base_func)
DamageFactorType.DEF_BOOST = DamageFactorType(async_func(lambda dmg, value: 1), async_func(lambda dmg: 0))
DamageFactorType.RESISTANCE = DamageFactorType(async_func(lambda dmg, value: min(max(1 - value, 0.1), 2)), resistance_base_func)
DamageFactorType.VULNERABILITY = DamageFactorType(async_func(lambda dmg, value: 1 + value), async_func(lambda dmg: 0))
DamageFactorType.MITIGATION = DamageFactorType(async_func(lambda dmg, value: max(value, 0.01)), mitigation_factor_base_func)
DamageFactorType.BREAK_EFF = DamageFactorType(async_func(lambda dmg, value: 1 + value), break_eff_base_func)
DamageFactorType.BREAK_DMG_BOOST = DamageFactorType(async_func(lambda dmg, value: 1 + value), async_func(lambda dmg: 0))

class DamageDesc:
    __slots__ = ("dealer", "stat_desc", "element", "types", "source", "can_kill")

    def __init__(self, dealer, stat_desc, element, types, source, can_kill=True):
        self.dealer = dealer
        self.stat_desc = stat_desc
        self.element = element
        self.types = types
        self.source = source
        self.can_kill = can_kill
    
    async def summon(self, t):
        return await Damage.create(self.dealer, t, self.stat_desc, self.element, self.types, self.source, self.can_kill)

class Damage:
    __slots__ = ("dealer", "target", "stat_desc", "element", "types", "source", "factors", "toughness_reduction", "hit_split_ratio",
        "energy_regen", "damage", "crit", "can_kill")

    def __init__(self, dealer, t, stat_desc, element, types, source, can_kill=True):
        self.dealer = dealer
        self.target = t
        self.stat_desc = stat_desc
        self.element = element
        self.types = set(types) if isinstance(types, Iterable) else {types}
        self.source = source
        self.can_kill = can_kill
        self.factors = {}
        self.toughness_reduction = None
        self.hit_split_ratio = 1
        self.energy_regen = None
        self.damage = None
        self.crit = False
    
    @classmethod
    async def create(cls, dealer, t, stat_desc, element, types, source, can_kill=True):
        dmg = cls(dealer, t, stat_desc, element, types, source, can_kill)
        await dmg.init()
        return dmg

    async def init(self):
        if self.types in ({DmgType.NORMAL}, {DmgType.ADDITIONAL}):
            for factor in (
                DamageFactorType.DMG_BOOST,
                DamageFactorType.WEAKEN,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VULNERABILITY,
                DamageFactorType.MITIGATION
            ):
                await self.new_factor(factor)
            from characters import base as character  # TODO: Python 3.15 lazy import
            if isinstance(self.dealer, character.Character):
                await self.new_factor(DamageFactorType.CRIT)
        elif self.types == {DmgType.BREAK}:
            for factor in (
                DamageFactorType.MAX_TOUGHNESS,
                DamageFactorType.MULTIPLIER,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VULNERABILITY,
                DamageFactorType.MITIGATION,
                DamageFactorType.BREAK_EFF,
                DamageFactorType.BREAK_DMG_BOOST
            ):
                await self.new_factor(factor)
        elif self.types == {DmgType.ADDITIONAL, DmgType.BREAK}:  # 击破造成的附加伤害
            for factor in (
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VULNERABILITY,
                DamageFactorType.MITIGATION,
                DamageFactorType.BREAK_EFF,
                DamageFactorType.BREAK_DMG_BOOST
            ):
                await self.new_factor(factor)

    async def new_factor(self, factor):
        if factor in self.factors:
            return
        self.factors[factor] = await factor.base_func(self)
    
    async def calculate(self):
        damage = self.stat_desc.calculate(damage=self)
        for factor, value in self.factors.items():
            damage *= await factor.func(self, value)
        self.damage = damage
        return damage
    
    async def on_hit(self):
        if self.hit_split_ratio == 1:
            dmg = self
        else:
            dmg = self.scale(self.hit_split_ratio)
        await battle.current.event_bus.dispatch("deal_damage", dmg)
        if self.toughness_reduction is not None and self.target.has_weakness(self.toughness_reduction.element):
            await battle.current.event_bus.dispatch("reduce_toughness", dmg.toughness_reduction)
        if self.energy_regen is not None:
            from characters import base as character  # TODO: Python 3.15 lazy import
            t = self.target if isinstance(self.target, character.Character) else self.dealer
            await battle.current.event_bus.dispatch("regen_energy", t, dmg.energy_regen)
    
    def scale(self, scale):
        dmg = copy.copy(self)
        dmg.stat_desc = self.stat_desc.scale(scale)
        if self.toughness_reduction is not None:
            dmg.toughness_reduction = self.toughness_reduction.scale(scale)
        if self.energy_regen is not None:
            dmg.energy_regen = self.energy_regen * scale
        return dmg
    
    def get_info(self):
        return {"amount": self.damage, "crit": self.crit, "types": [t.nameid for t in self.types]}

class ToughnessReduction:
    __slots__ = ("dealer", "target", "base_amount", "element", "reduction_increase")

    def __init__(self, dealer, target, base_amount, element):
        self.dealer = dealer
        self.target = target
        self.base_amount = base_amount
        self.element = element
        self.reduction_increase = 0
    
    def calculate(self):
        value = self.base_amount
        if self.element is not None:
            value *= (1 + min(self.dealer.stats["wb_eff"].calculate(toughness_reduction=self), 3) +
                self.target.stats["toughness_vulnerability"].calculate(toughness_reduction=self))
        value *= 1 + self.reduction_increase
        return value
    
    def scale(self, scale):
        tr = copy.copy(self)
        tr.base_amount = self.base_amount * scale
        return tr

class DotTick:
    __slots__ = ("target", "filter", "percentage")

    def __init__(self, target, filter, percentage):
        self.target = target
        self.filter = filter
        self.percentage = percentage
