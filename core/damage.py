import copy
from collections.abc import Iterable
from dataclasses import dataclass
from typing import *

from . import battle
from . import enums
from . import modifier
from . import item
from . import event
from . import event_types

class DmgType(enums.Enum):
    NORMAL = item.Item("normal", "Normal")
    ADDITIONAL = item.Item("additional", "Additional")
    BREAK = item.Item("break", "Break")
    SUPER_BREAK = item.Item("super_break", "Super Break")
    DOT = item.Item("dot", "DoT")
    ALL = (NORMAL, ADDITIONAL, BREAK, SUPER_BREAK, DOT)
DmgType.init()

class DmgSource(enums.Enum):
    BASIC_ATK = item.Item("basic_atk", "Basic ATK")
    ENHANCED_BASIC_ATK = item.Item("enhanced_basic_atk", "Enhanced Basic ATK")
    SKILL = item.Item("skill", "Skill")
    ENHANCED_SKILL = item.Item("enhanced_skill", "Enhanced Skill")
    ULTIMATE = item.Item("ultimate", "Ultimate")
    FOLLOW_UP = item.Item("follow_up", "Follow-Up")
    WEAKNESS_BREAK = item.Item("weakness_break", "Weakness Break")
    DOT = item.Item("dot", "DoT")
    MONSTER = item.Item("monster", "Monster")
    ALL = (BASIC_ATK, ENHANCED_BASIC_ATK, SKILL, ENHANCED_SKILL, ULTIMATE, FOLLOW_UP, WEAKNESS_BREAK, DOT, MONSTER)
DmgSource.init()

class DamageFactorType:
    def __init__(self, func, base_func):
        self.func = func
        self.base_func = base_func

def max_toughness_base_func(dmg):
    return dmg.target.stats["toughness"].calculate(damage=dmg) / 40 + 0.5

def multiplier_base_func(dmg):
    if dmg.element in (enums.Element.FIRE, enums.Element.PHYSICAL):
        return 2
    elif dmg.element is enums.Element.WIND:
        return 1.5
    elif dmg.element in (enums.Element.QUANTUM, enums.Element.IMAGINARY):
        return 0.5
    else:
        return 1

def crit_factor_func(dmg, value):
    if battle.current.random.rate(dmg.dealer.stats["crt_rate"].calculate(damage=dmg)):
        dmg.crit = True
        return 1 + value
    return 1

def crit_factor_base_func(dmg):
    return dmg.dealer.stats["crt_dmg"].calculate(damage=dmg)

def dmg_boost_base_func(dmg):
    value = dmg.dealer.stats["dmg_boost"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.dealer.stats[f"{dmg.element.nameid}_dmg_boost"].calculate(damage=dmg)
    return value

def defence_factor_func(dmg, value):
    value += dmg.target.stats["def"].calculate(modifier.ModifierFilter.BASE) * dmg.factors[DamageFactorType.DEF_BOOST]
    value = max(0, value)
    return 1 - value / (value + 200 + 10 * dmg.dealer.level)

def defence_factor_base_func(dmg):
    return dmg.target.stats["def"].calculate(damage=dmg)

def resistance_base_func(dmg):
    value = -dmg.dealer.stats["res_pen"].calculate(damage=dmg)
    if dmg.element is not None:
        value += dmg.target.stats[f"{dmg.element.nameid}_res"].calculate(damage=dmg)
        value -= dmg.dealer.stats[f"{dmg.element.nameid}_res_pen"].calculate(damage=dmg)
    return value

def mitigation_factor_base_func(dmg):
    from .monsters import base as monster  # TODO: Python 3.15 lazy import
    if isinstance(dmg.target, monster.Monster) and not dmg.target.weakness_broken:
        return 0.9
    return 1

def break_eff_base_func(dmg):
    return dmg.dealer.stats["break_eff"].calculate(damage=dmg)

def break_dmg_boost_base_func(dmg):
    return dmg.dealer.stats["break_dmg_boost"].calculate(damage=dmg)

DamageFactorType.MAX_TOUGHNESS = DamageFactorType(lambda dmg, value: value, max_toughness_base_func)
DamageFactorType.MULTIPLIER = DamageFactorType(lambda dmg, value: value, multiplier_base_func)  # 指击破的倍率
DamageFactorType.CRIT = DamageFactorType(crit_factor_func, crit_factor_base_func)
DamageFactorType.DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, dmg_boost_base_func)
DamageFactorType.WEAKEN = DamageFactorType(lambda dmg, value: 1 - value, None)
DamageFactorType.DEFENCE = DamageFactorType(defence_factor_func, defence_factor_base_func)
DamageFactorType.DEF_BOOST = DamageFactorType(lambda dmg, value: 1, None)
DamageFactorType.RESISTANCE = DamageFactorType(lambda dmg, value: min(max(1 - value, 0.1), 2), resistance_base_func)
DamageFactorType.VULNERABILITY = DamageFactorType(lambda dmg, value: 1 + value, None)
DamageFactorType.MITIGATION = DamageFactorType(lambda dmg, value: max(value, 0.01), mitigation_factor_base_func)
DamageFactorType.BREAK_EFF = DamageFactorType(lambda dmg, value: 1 + value, break_eff_base_func)
DamageFactorType.BREAK_DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, break_dmg_boost_base_func)
DamageFactorType.SUPER_BREAK_MAX_TOUGHNESS = DamageFactorType(lambda dmg, value: value, None)
DamageFactorType.SUPER_BREAK_DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, None)

@dataclass(slots=True, eq=False)
class DamageContext:
    source: DmgSource
    effect: object | None = None
    effect_instance: object | None = None

@dataclass(slots=True, eq=False)
class DamageDesc:
    dealer: object
    stat_desc: modifier.StatDesc
    element: enums.Element
    types: Set[DmgType]
    context: DamageContext
    
    def summon(self, t, effect_instance=None):
        self.context.effect_instance = effect_instance
        return Damage.create(self.dealer, t, self.stat_desc, self.element, self.types, self.context)

class Damage:
    __slots__ = ("dealer", "target", "stat_desc", "element", "types", "context", "factors", "toughness_reduction", "hit_split_ratio",
        "energy_regen", "damage", "crit")

    def __init__(self, dealer, t, stat_desc, element, types, context):
        if context in DmgSource.ALL:
            context = DamageContext(context)
        self.dealer = dealer
        self.target = t
        self.stat_desc = stat_desc
        self.element = element
        self.types = set(types) if isinstance(types, Iterable) else {types}
        self.context = context
        self.factors = {}
        self.toughness_reduction = None
        self.hit_split_ratio = 1
        self.energy_regen = None
    
    def init_hit_properties(self):
        self.damage = None
        self.crit = False
    
    @classmethod
    def create(cls, dealer, t, stat_desc, element, types, context):
        dmg = cls(dealer, t, stat_desc, element, types, context)
        dmg.init_factors()
        return dmg

    def init_factors(self):
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
                self.new_factor(factor)
            from .characters import base as character  # TODO: Python 3.15 lazy import
            if isinstance(self.dealer, character.Character):
                self.new_factor(DamageFactorType.CRIT)
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
                self.new_factor(factor)
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
                self.new_factor(factor)
        elif self.types == {DmgType.DOT}:
            for factor in (
                DamageFactorType.DMG_BOOST,
                DamageFactorType.WEAKEN,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VULNERABILITY,
                DamageFactorType.MITIGATION
            ):
                self.new_factor(factor)
        elif self.types == {DmgType.SUPER_BREAK}:
            for factor in (
                DamageFactorType.MAX_TOUGHNESS,
                DamageFactorType.MULTIPLIER,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VULNERABILITY,
                DamageFactorType.MITIGATION,
                DamageFactorType.BREAK_EFF,
                DamageFactorType.BREAK_DMG_BOOST,
                DamageFactorType.SUPER_BREAK_MAX_TOUGHNESS,
                DamageFactorType.SUPER_BREAK_DMG_BOOST
            ):
                self.new_factor(factor)

    def new_factor(self, factor):
        if factor in self.factors:
            return
        func = factor.base_func
        if func is None:
            self.factors[factor] = 0
        else:
            self.factors[factor] = func(self)
    
    def set_toughness_reduction(self, tr):
        tr.damage = self
        tr.dealer = self.dealer
        tr.target = self.target
        self.toughness_reduction = tr
    
    def calculate(self):
        damage = self.stat_desc.calculate(damage=self) * self.hit_split_ratio
        for factor, value in self.factors.items():
            damage *= factor.func(self, value)
        self.damage = damage
    
    def get_damage(self):
        return self.damage
    
    def on_hit(self):
        self.init_hit_properties()
        event.bus.dispatch(event_types.Damage(self))
        if self.toughness_reduction is not None and self.target.weaknesses.has_weakness(self.toughness_reduction.element):
            event.bus.dispatch(event_types.ReduceToughness(self.toughness_reduction))
        if self.energy_regen is not None:
            from .characters import base as character  # TODO: Python 3.15 lazy import
            t = self.target if isinstance(self.target, character.Character) else self.dealer
            event.bus.dispatch(event_types.RegenEnergy(t, self.energy_regen * self.hit_split_ratio))
    
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
    
    def is_break_dmg(self):
        return self.types in ({DmgType.BREAK}, {DmgType.ADDITIONAL, DmgType.BREAK}, {DmgType.SUPER_BREAK})
    
    def is_dot_dmg(self):
        return self.types in ({DmgType.DOT}, {DmgType.DOT, DmgType.BREAK})
    
    def is_super_break_dmg(self):
        return self.types == {DmgType.SUPER_BREAK}
    
    def is_from_basic_atk(self):
        return self.context.source in (damage.DmgSource.BASIC_ATK, damage.DmgSource.ENHANCED_BASIC_ATK)
    
    def is_from_skill(self):
        return self.context.source in (damage.DmgSource.SKILL, damage.DmgSource.ENHANCED_SKILL)

@dataclass(slots=True, eq=False)
class ToughnessReduction:
    base_amount: float
    element: enums.Element
    damage: Damage = None
    dealer: object = None
    target: object = None
    reduction_increase: float = 0
    
    def calculate(self):
        value = self.base_amount
        if self.damage is not None:
            value *= self.damage.hit_split_ratio
        if self.element is not None:
            value *= (1 + min(self.dealer.stats["wb_eff"].calculate(toughness_reduction=self), 3) +
                self.target.stats["toughness_vulnerability"].calculate(toughness_reduction=self))
        value *= 1 + self.reduction_increase
        return value
    
    def scale(self, scale):
        tr = copy.copy(self)
        tr.base_amount = self.base_amount * scale
        return tr
    
    def to_super_break_dmg(self, multiplier):
        dmg = Damage(self.dealer, self.target,
            modifier.StatDesc((self.dealer.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, multiplier)), self.element, {DmgType.SUPER_BREAK}, self.damage.context, False)
        dmg.factors[DamageFactorType.SUPER_BREAK_MAX_TOUGHNESS] = self.calculate() / 10
        return dmg

@dataclass(slots=True, eq=False)
class DotTick:
    target: object
    filter: Callable
    percentage: float
