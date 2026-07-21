import copy
from collections.abc import Iterable
from dataclasses import dataclass

from . import item
from . import event
from . import event_types
from . import battle
from . import target
from . import enums
from . import damage

class Debuff(enums.Enum):
    # 在需要时指定
    BLEED = item.Item("bleed", "Bleed")
    BURN = item.Item("burn", "Burn")
    FROZEN = item.Item("frozen", "Frozen")
    SHOCK = item.Item("shock", "Shock")
    WIND_SHEER = item.Item("wind_sheer", "Wind Sheer")
    ENTANGLEMENT = item.Item("entanglement", "Entanglement")
    IMPRISONMENT = item.Item("imprisonment", "Imprisonment")
    CONTROL = item.Item("control", "Control")
    ALL = (BLEED, BURN, FROZEN, SHOCK, WIND_SHEER, ENTANGLEMENT, IMPRISONMENT, CONTROL)
Debuff.init()

# 表示一种状态效果类型
# 不同的Effect实例是不同的状态效果类型
class Effect(item.Item):
    class Type(enums.Enum):
        BUFF = item.Item("buff", "Buff")
        DEBUFF = item.Item("debuff", "Debuff")
        OTHERS = item.Item("others", "Others")
        ALL = (BUFF, DEBUFF, OTHERS)
    Type.init()
    
    class DurationType(enums.Enum):
        PERMANENT = item.Item("permanent", "Permanent")
        TURN_START = item.Item("turn_start", "Turn Start")
        TURN_END = item.Item("turn_end", "Turn End")
        TURN_END_CHECK_START = item.Item("turn_end_check_start", "Turn End (Check Start)")
        ALL = (PERMANENT, TURN_START, TURN_END, TURN_END_CHECK_START)
    DurationType.init()
    
    # 表示已经应用到某个target的状态效果
    class Instance:
        def __init__(self, eff, caster, t):
            self.effect = eff
            self.caster = caster
            self.target = t
            self.old_stacks = 0
        
        # 有关状态效果的信息改变后调用
        # 要求多次调用无副作用
        # 不要通过super()调用父类的refresh
        # 初始状态的设置也应该在refresh中进行
        def refresh(self):
            self.old_stacks = self.target.effects.get_stacks(self.effect)

    def __init__(self, nameid, name, type, duration_type, max_stacks, dispellable=True):
        super().__init__(nameid, name)
        self.type = type
        self.duration_type = duration_type
        # max_stacks=0表示无限制
        self.max_stacks = max_stacks
        self.dispellable = dispellable
        self.group_name = None
    
    def print(self, indent=0):
        print(" " * indent + f"{self.name} ({self.nameid}) "
            f"<type={self.type.name}, duration_type={self.duration_type.name}, max_stacks={self.max_stacks}, dispellable={self.dispellable}>")
    
    def full_name(self):
        return f"{self.group_name}.{self.nameid}" if self.group_name is not None else self.nameid
    
    def new_instance(self, caster, t):
        return self.Instance(self, caster, t)
    
    def is_debuff_type(self, type):
        return False
    
    def is_dot(self, t):
        return False
    
    def is_immune(self, t):
        return False
    
    def can_act(self, t):
        return True

class ModifierEffect(Effect):
    class Instance(Effect.Instance):
        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            stat = self.target.stats[self.effect.stat_name]
            if self.old_stacks == 0 and stacks != 0:
                self.modifiers = [copy.copy(m) for m in self.effect.modifiers]
                stat.modifiers.extend(self.modifiers)
                self.mod_dead = item.DeadToggle(self.target)
                for mod in self.modifiers:
                    mod.master = self.mod_dead
            elif self.old_stacks != 0 and stacks == 0:
                self.mod_dead.dead_toggle = True
            for i in range(len(self.modifiers)):
                self.modifiers[i].stat_desc = self.effect.modifiers[i].stat_desc.scale(stacks)
            self.old_stacks = stacks

    def __init__(self, nameid, name, type_, duration_type, max_stacks, stat_name, modifiers, dispellable=True):
        super().__init__(nameid, name, type_, duration_type, max_stacks, dispellable)
        self.stat_name = stat_name
        self.modifiers = list(modifiers) if isinstance(modifiers, Iterable) else [modifiers]

class FrozenEffect(Effect):
    class Instance(Effect.Instance):
        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.listener_dead = item.DeadToggle(self.target)
                battle.current.event_bus.add_member_listener_legacy(self.normal_turn_start, self.listener_dead)
            elif self.old_stacks != 0 and stacks == 0:
                self.listener_dead.dead_toggle = True
            self.old_stacks = stacks
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def normal_turn_start(self, turn):
            if not isinstance(turn, target.Target.NormalTurn) or self.target is not turn.target:
                return
            if self.effect.dmg_desc is not None:
                battle.current.event_bus.dispatch_legacy("additional_damage", self.effect.dmg_desc.summon(self.target, effect_instance=self))

    def __init__(self, dmg_desc=None, dispellable=True):
        super().__init__("frozen", "Frozen", Effect.Type.DEBUFF, Effect.DurationType.TURN_END, 1, dispellable)
        self.dmg_desc = dmg_desc
        self.dmg_desc.context.effect = self

    def is_debuff_type(self, type):
        return type in (Debuff.FROZEN, Debuff.CONTROL)
    
    def can_act(self, t):
        return False

class DotEffect(Effect):
    class Instance(Effect.Instance):
        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.listener_dead = item.DeadToggle(self.target)
                battle.current.event_bus.add_member_listener_legacy(self.tick_dot, self.listener_dead)
            elif self.old_stacks != 0 and stacks == 0:
                self.listener_dead.dead_toggle = True
            self.old_stacks = stacks
        
        @event.member_listener_legacy(event.ListenerPriority.EXECUTE)
        def tick_dot(self, dot):
            if self.target is not dot.target or not dot.filter(self.effect):
                return
            battle.current.event_bus.dispatch_legacy("additional_damage",
                (self.effect.dmg_desc.summon(self.target, effect_instance=self)).scale(dot.percentage * self.old_stacks))

    def __init__(self, nameid, name, dmg_desc, debuff_type, max_stacks, dispellable=True):
        super().__init__(nameid, name, Effect.Type.DEBUFF, Effect.DurationType.TURN_END, max_stacks, dispellable)
        self.dmg_desc = dmg_desc
        self.dmg_desc.context.effect = self
        self.debuff_type = debuff_type
    
    def is_dot(self, t):
        return True
    
    def is_debuff_type(self, type):
        return type is self.debuff_type

class AdditionalWeaknessEffect(Effect):
    class Instance(Effect.Instance):
        def refresh(self):
            stacks = self.target.effects.get_stacks(self.effect)
            if self.old_stacks == 0 and stacks != 0:
                self.eff_dead = item.DeadToggle(self.target)
                from .monsters import base as monster  # TODO: Python 3.15 lazy import
                self.target.weaknesses.additions.append(monster.AdditionalWeakness(self.effect.nameid, self.effect.name, self.caster,
                    self.target, self.effect.element, self.eff_dead))
            elif self.old_stacks != 0 and stacks == 0:
                self.eff_dead.dead_toggle = True
            self.old_stacks = stacks

    def __init__(self, nameid, name, duration_type, element, dispellable=True):
        super().__init__(nameid, name, Effect.Type.DEBUFF, duration_type, 1, dispellable)
        self.element = element

class EffectTypes:
    def __init__(self, t=None):
        self.target = t
        self.groups = {}
    
    def add(self, group_name, eff, alias=None):
        if group_name not in self.groups:
            self.groups[group_name] = {}
        if alias is not None:
            self.groups[group_name][alias] = eff
        else:
            self.groups[group_name][eff.nameid] = eff
        eff.group_name = group_name
    
    def add_unique(self, eff, alias=None):
        self.add(self.target.nameid, eff, alias)
    
    def get(self, group_name, nameid):
        return self.groups[group_name][nameid]

@dataclass(slots=True, eq=False)
class EffectInfo:
    # duration=-1表示永久持续
    duration: int
    stacks: int
    
    def refresh_duration(self, duration):
        if duration == -1 or self.duration != -1 and duration > self.duration:
            self.duration = duration

class EffectList:
    def __init__(self, t):
        self.target = t
        self.effects = {}
        # instance一旦被添加就不会被删除
        # effect.Instance的实现保证没有副作用
        self.instances = {}
        self.start_effects = []

        battle.current.event_bus.add_member_listener_legacy(self.normal_turn_start, t)
        battle.current.event_bus.add_member_listener_legacy(self.normal_turn_end, t)
    
    def print(self, indent=0):
        print(" " * indent + f"{self.target.nameid}.effects:")
        for eff in self.effects.keys():
            eff.print(indent + 2)
            for duration, stacks in self.effects[eff].items():
                if duration == -1:
                    print(" " * (indent + 4) + f"Permanent: {stacks}")
                else:
                    print(" " * (indent + 4) + f"{duration} turn(s): {stacks}")
    
    def add(self, eff, adder, duration, stacks=1):
        if eff.is_immune(self.target):
            return False
        if eff not in self.instances:
            self.instances[eff] = eff.new_instance(adder, self.target)
        if eff not in self.effects:
            self.effects[eff] = EffectInfo(duration, stacks)
        else:
            if eff.max_stacks != 0:
                self.effects[eff].stacks = min(self.effects[eff].stacks + stacks, eff.max_stacks)
            else:
                self.effects[eff].stacks += stacks
            self.effects[eff].refresh_duration(duration)
        self.instances[eff].refresh()
        return True
    
    def remove(self, eff, stacks):
        if eff in self.effects:
            self.effects[eff].stacks -= stacks
            if self.effects[eff].stacks <= 0:
                del self.effects[eff]
            self.instances[eff].refresh()
    
    def delete(self, eff):
        if eff in self.effects:
            del self.effects[eff]
            self.instances[eff].refresh()
    
    def advance_turn(self, eff):
        if self.effects[eff].duration != -1:
            self.effects[eff].duration -= 1
            if self.effects[eff].duration == 0:
                self.delete(eff)
        self.instances[eff].refresh()
    
    def has_effect(self, eff):
        return eff in self.effects
    
    def count_effect(self, f=None):
        count = 0
        for eff in self.effects.keys():
            if f is None or f(eff):
                count += 1
        return count
    
    def get_stacks(self, eff):
        if not self.has_effect(eff):
            return 0
        return self.effects[eff].stacks
    
    def has_debuff(self, debuff):
        for eff in self.effects.keys():
            if eff.is_debuff_type(debuff):
                return True
        return False
    
    def can_act(self):
        for eff in self.effects.keys():
            if not eff.can_act(self.target):
                return False
        return True
    
    def dispel(self, count, f=None):
        # count=0表示全部驱散
        dispelled = 0
        while True:
            if count != 0:
                if count <= 0:
                    return dispelled
                count -= 1
            effects = list(filter(lambda eff: eff.dispellable and (f is None or f(eff)), self.effects.keys()))
            if not effects:
                return dispelled
            import random  # TODO: battle.current.random
            eff = random.choice(effects)
            self.delete(eff)
            dispelled += 1
        return dispelled
    
    def die(self):
        for eff in list(self.effects.keys()):
            self.delete(eff)
    
    @event.member_listener_legacy(event.ListenerPriority.PRE_PROCESS)
    def normal_turn_start(self, turn):
        if not isinstance(turn, target.Target.NormalTurn) or self.target is not turn.target:
            return
        battle.current.event_bus.dispatch_legacy("tick_dot", damage.DotTick(self.target, lambda x: True, 1))
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_START:
                self.advance_turn(eff)
        self.start_effects = list(self.effects.keys())
    
    @event.member_listener_legacy(event.ListenerPriority.POST_PROCESS)
    def normal_turn_end(self, turn):
        if not isinstance(turn, target.Target.NormalTurn) or self.target is not turn.target:
            return
        for eff in list(self.effects.keys()):
            if eff.duration_type == Effect.DurationType.TURN_END:
                self.advance_turn(eff)
            elif eff.duration_type == Effect.DurationType.TURN_END_CHECK_START and eff in self.start_effects:
                self.advance_turn(eff)

@dataclass(slots=True, eq=False)
class EffectAddition:
    adder: object
    target: object
    effect: object
    duration: int
    stacks: int = 1
