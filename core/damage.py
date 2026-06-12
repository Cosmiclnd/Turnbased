import copy

import target
import battle
import enums
import modifier
import item

class DmgType(enums.Enum):
    NORMAL = item.Item("normal", "Normal")
    ADDITIONAL = item.Item("additional", "Additional")
    BREAK = item.Item("break", "Break")
    ALL = (NORMAL, ADDITIONAL, BREAK)
DmgType.init()

class DmgSource(enums.Enum):
    BASIC_ATTACK = item.Item("basic_attack", "Basic Attack")
    SKILL = item.Item("skill", "Skill")
    ULTIMATE = item.Item("ultimate", "Ultimate")
    FOLLOW_UP = item.Item("follow_up", "Follow-Up")
    WEAKNESS_BREAK = item.Item("weakness_break", "Weakness Break")
    MONSTER = item.Item("monster", "Monster")
    ALL = (BASIC_ATTACK, SKILL, ULTIMATE, FOLLOW_UP, WEAKNESS_BREAK, MONSTER)
DmgSource.init()

class DamageFactorType:
    def __init__(self, func, base_func):
        self.func = func
        self.base_func = base_func

def multiplier_base_func(dmg):
    if dmg.has_types(DmgType.BREAK):
        mult = dmg.target.stats["toughness"].calculate(damage=dmg) / 40 + 0.5
        if dmg.element in (enums.Element.FIRE, enums.Element.PHYSICAL):
            mult *= 2
        elif dmg.element is enums.Element.WIND:
            mult *= 1.5
        elif dmg.element in (enums.Element.QUANTUM, enums.Element.IMAGINARY):
            mult *= 0.5
        return mult
    return 1

def crit_factor_func(dmg, value):
    if battle.current.random.random() < dmg.dealer.stats["crt_rate"].calculate(damage=dmg):
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
    if isinstance(dmg.target, target.Monster) and not dmg.target.weakness_broken:
        return 0.9
    return 1

def break_eff_base_func(dmg):
    return dmg.dealer.stats["break_eff"].calculate(damage=dmg)

DamageFactorType.MULTIPLIER = DamageFactorType(lambda dmg, value: value, multiplier_base_func)  # 特指击破的倍率
DamageFactorType.CRIT = DamageFactorType(crit_factor_func, crit_factor_base_func)
DamageFactorType.DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, dmg_boost_base_func)
DamageFactorType.WEAKEN = DamageFactorType(lambda dmg, value: 1 - value, lambda dmg: 0)
DamageFactorType.DEFENCE = DamageFactorType(defence_factor_func, defence_factor_base_func)
DamageFactorType.DEF_BOOST = DamageFactorType(lambda dmg, value: 1, lambda dmg: 0)
DamageFactorType.RESISTANCE = DamageFactorType(lambda dmg, value: min(max(1 - value, 0.1), 2), resistance_base_func)
DamageFactorType.VUNERABILITY = DamageFactorType(lambda dmg, value: 1 + value, lambda dmg: 0)
DamageFactorType.MITIGATION = DamageFactorType(lambda dmg, value: max(value, 0.01), mitigation_factor_base_func)
DamageFactorType.BREAK_EFF = DamageFactorType(lambda dmg, value: 1 + value, break_eff_base_func)
DamageFactorType.BREAK_DMG_BOOST = DamageFactorType(lambda dmg, value: 1 + value, lambda dmg: 0)

class Damage:
    __slots__ = ("dealer", "target", "stat_desc", "element", "types", "source", "factors", "toughness_reduction", "hit_split", "energy_regen", "damage")

    def __init__(self, dealer, t, stat_desc, element, types, source):
        self.dealer = dealer
        self.target = t
        self.stat_desc = stat_desc
        self.element = element
        self.types = types if isinstance(types, tuple) else (types,)
        self.source = source
        self.factors = {}
        self.toughness_reduction = None
        self.hit_split = None
        self.energy_regen = None
        self.damage = None

        if self.has_types(DmgType.NORMAL, DmgType.ADDITIONAL):
            for factor in (
                DamageFactorType.DMG_BOOST,
                DamageFactorType.WEAKEN,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VUNERABILITY,
                DamageFactorType.MITIGATION
            ):
                self.new_factor(factor)
            if isinstance(self.dealer, target.Character):
                self.new_factor(DamageFactorType.CRIT)
        if self.has_types(DmgType.BREAK):
            for factor in (
                DamageFactorType.MULTIPLIER,
                DamageFactorType.DEFENCE,
                DamageFactorType.DEF_BOOST,
                DamageFactorType.RESISTANCE,
                DamageFactorType.VUNERABILITY,
                DamageFactorType.MITIGATION,
                DamageFactorType.BREAK_EFF,
                DamageFactorType.BREAK_DMG_BOOST
            ):
                self.new_factor(factor)
    
    def has_types(self, *types):
        # 只要有相同的伤害类型即可
        return any(t in self.types for t in types)

    def new_factor(self, factor):
        if factor in self.factors:
            return
        self.factors[factor] = factor.base_func(self)
    
    def calculate(self):
        damage = self.stat_desc.calculate(damage=self)
        for factor, value in self.factors.items():
            damage *= factor.func(self, value)
        self.damage = damage
        return damage
    
    async def on_attack(self):
        if self.hit_split is None:
            await battle.current.event_bus.dispatch("hit", self)
        else:
            toughness_reduction = self.toughness_reduction.base_amount if self.toughness_reduction is not None else None
            energy_regen = self.energy_regen
            for rate in self.hit_split:
                dmg = copy.copy(self)
                dmg.stat_desc = self.stat_desc.scale(rate)
                dmg.hit_split = None
                if dmg.toughness_reduction is not None:
                    dmg.toughness_reduction.base_amount = toughness_reduction * rate
                if dmg.energy_regen is not None:
                    dmg.energy_regen = energy_regen * rate
                await battle.current.event_bus.dispatch("hit", dmg)
            if toughness_reduction is not None:
                self.toughness_reduction.base_amount = toughness_reduction
            self.energy_regen = energy_regen
    
    async def on_hit(self):
        await battle.current.event_bus.dispatch("deal_damage", self)
        if self.toughness_reduction is not None:
            await battle.current.event_bus.dispatch("reduce_toughness", self.toughness_reduction)
        if self.energy_regen is not None:
            t = self.target if isinstance(self.target, target.Character) else self.dealer
            await battle.current.event_bus.dispatch("regen_energy", t, self.energy_regen)

class ToughnessReduction:
    def __init__(self, dealer, target, base_amount, element):
        self.dealer = dealer
        self.target = target
        self.base_amount = base_amount
        self.element = element
    
    def calculate(self):
        return self.base_amount if self.element is None or self.target.has_weakness(self.element) else 0
