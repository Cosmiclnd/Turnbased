from dataclasses import dataclass

from . import item
from . import enums
from . import config
from . import modifier
from . import action
from . import effect
from . import event
from . import event_types
from . import battle
from .decision import base as decision

all_targets = {}

@dataclass(slots=True, eq=False)
class DeathState:
    target: object
    alive: bool = True
    cleaned: bool = False
    killing_dmg: object = None

    def clear(self):
        self.alive = True
        self.cleaned = False
        self.killing_dmg = None
        if self.target.cur_hp < 0:
            self.target.cur_hp = 0

class Target(item.Item):
    class TargetConfig(config.SkillsConfig):
        __slots__ = ("target", "nameid", "name")

        def __init__(self, data, t):
            super().__init__(data)
            self.target = t
            self.nameid = data["nameid"]
            self.name = data["name"]
            self.skills = data["skills"]
        
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
    
    class NormalTurn(action.NormalTurn):
        def __init__(self, t):
            super().__init__(f"{t.nameid}_normal_turn", f"{t.name}'s Normal Turn", t.stats["spd"], t)
            self.target = t
            
            event.bus.add_member_listener(self.normal_turn, self, self)
            event.bus.add_member_listener(self.check_frozen, self, self)
            event.bus.add_member_listener(self.target.effects.normal_turn_start, self, self)
            event.bus.add_member_listener(self.target.effects.normal_turn_end, self, self)
        
        def get_info(self):
            return {"target": str(self.target.uuid)} | super().get_info()
    
        @event.member_listener(event_types.NormalTurn.Act.EXECUTE)
        def normal_turn(self, e):
            event.bus.dispatch(event_types.TargetAction(self.target))

        @event.member_listener(event_types.NormalTurn.End.EXECUTE)
        def check_frozen(self, e):
            frozen = self.target.effects.has_debuff(effect.Debuff.FROZEN)
            if frozen:
                self.advance(0.5)
    
    class ExtraTurn(action.ExtraTurn):
        def __init__(self, nameid, name, priority, t):
            super().__init__(nameid, name, priority, item.DeadToggle(t))
            self.target = t
    
    class ExtraNormalTurn(ExtraTurn):
        def __init__(self, t):
            super().__init__(f"{t.nameid}_extra_normal_turn", f"{t.name}'s Extra Normal Turn", action.ExtraTurn.Priority.NORMAL, t)

            event.bus.add_member_listener(self.extra_turn, self, self)
            if not battle.current.features.get("extra_normal_turn_not_reset_at_new_wave"):
                event.bus.add_member_listener(self.reset, None, self)
        
        @event.member_listener(event_types.ExtraTurn.EXECUTE)
        def extra_turn(self, e):
            decision.provider.notify({"name": "extra_normal_turn", "target": str(self.target.uuid)})
            event.bus.dispatch(event_types.TargetAction(self.target))
            self.master.dead_toggle = True
        
        @event.member_listener(event_types.NewWave.BEFORE_RESET)
        def reset(self, e):
            self.master.dead_toggle = True

    def __init__(self, uuid, nameid, name, level):
        super().__init__(nameid, name, None)
        self.uuid = uuid
        all_targets[uuid] = self
        self.level = level
        self.stats = modifier.StatDict()
        stat_names = ["hp", "atk", "def", "spd", "dmg_boost", "res_pen"]
        for e in enums.Element.ALL:
            stat_names.append(f"{e.nameid}_dmg_boost")
            stat_names.append(f"{e.nameid}_res")
            stat_names.append(f"{e.nameid}_res_pen")
        stat_names.extend(["eff_hr", "eff_res"])
        for e in effect.Debuff.ALL:
            stat_names.append(f"{e.nameid}_res")
        self.stats.new_stats(stat_names, self)
        self.cur_normal_turn = None
        self.cur_hp = 0
        self.death_state = DeathState(self)
        self.effects = effect.EffectList(self)
        self.effect_types = effect.EffectTypes(self)
        self.initial_state = {}

        event.bus.add_member_listener(self.set_initial_state, None, self)
        event.bus.add_member_listener(self.set_passives, None, self)
        event.bus.add_member_listener(self.attack_end, self, self)
        event.bus.add_member_listener(self.hit, self, self)
        event.bus.add_member_listener(self.additional_damage, self, self)
        event.bus.add_member_listener(self.calculate_damage, self, self)
        event.bus.add_member_listener(self.take_damage, None, self)
        event.bus.add_member_listener(self.cur_hp_modify, self, self)
        event.bus.add_member_listener(self.die, self, self)
        event.bus.add_member_listener(self.clean, self, self)
        event.bus.add_member_listener(self.receive_heal, None, self)
        event.bus.add_member_listener(self.add_effect, self, self)
    
    def dead(self):
        return self.death_state.cleaned
    
    def new_normal_turn(self):
        self.cur_normal_turn = self.NormalTurn(self)
        return self.cur_normal_turn
    
    def can_act(self):
        if not self.death_state.alive:
            return False
        if not self.effects.can_act():
            return False
        return True
    
    def add_modifier_hp(self, mod):
        # 生命上限变化同时改变生命值
        # 如不需要生命值变化的逻辑则不需要调用此方法
        old_hp = self.stats["hp"].calculate()
        self.stats["hp"].modifiers.append(mod)
        new_hp = self.stats["hp"].calculate()
        if new_hp > old_hp:
            self.cur_hp *= new_hp / old_hp
        elif new_hp < old_hp:
            self.cur_hp = min(self.cur_hp, new_hp)
    
    def check_death(self):
        if not self.death_state.alive:
            event.bus.dispatch(event_types.Die(self))
    
    def try_apply_debuff(self, eff_add, base_chance):
        chance = base_chance
        chance *= 1 + self.stats["eff_hr"].calculate(effect=eff_add.effect)
        chance *= max(1 - eff_add.target.stats["eff_res"].calculate(effect=eff_add.effect), 0)
        debuff_res = 0
        for debuff in effect.Debuff.ALL:
            if eff_add.effect.is_debuff_type(debuff):
                debuff_res += eff_add.target.stats[f"{debuff.nameid}_res"].calculate(effect=eff_add.effect)
        chance *= max(1 - debuff_res, 0)
        if battle.current.random.rate(chance):
            event.bus.dispatch(event_types.AddEffect(eff_add))
    
    def consume_hp(self, amount):
        # 主动消耗生命值，最多使生命值降低至1点
        event.bus.dispatch(event_types.CurHpModify(self, -amount))
        self.cur_hp = max(1, self.cur_hp)
    
    @event.member_listener(event_types.BattleStart.INIT)
    def set_initial_state(self, e):
        if "cur_hp" in self.initial_state:
            self.cur_hp = self.initial_state["cur_hp"]
        elif "cur_hp_rate" in self.initial_state:
            self.cur_hp = self.initial_state["cur_hp_rate"] * self.stats["hp"].calculate()
        else:
            self.cur_hp = self.stats["hp"].calculate()
        self.death_state.clear()
    
    @event.member_listener(event_types.BattleStart.PASSIVES)
    def set_passives(self, e):
        pass
    
    @event.member_listener(event_types.Attack.End.EXECUTE)
    def attack_end(self, e):
        for t in battle.current.all_targets():
            t.check_death()
    
    @event.member_listener(event_types.Hit.HIT)
    def hit(self, e):
        e.dmg.on_hit()
    
    @event.member_listener(event_types.AdditionalDamage.HIT)
    def additional_damage(self, e):
        e.dmg.init_hit_properties()
        event.bus.dispatch(event_types.Damage(e.dmg))
        if not event.bus.is_during(event_types.Attack):
            e.dmg.target.check_death()
    
    @event.member_listener(event_types.Damage.CALCULATE)
    def calculate_damage(self, e):
        e.dmg.calculate()
    
    @event.member_listener(event_types.Damage.TAKE)
    def take_damage(self, e):
        dmg = e.dmg
        if self is not dmg.target:
            return
        amount = dmg.get_damage()
        decision.provider.notify({"name": "damage", "dealer": str(dmg.dealer.uuid), "target": str(self.uuid),
            "damage": dmg.get_info()})
        event.bus.dispatch(event_types.CurHpModify(self, -amount))
        if self.cur_hp <= 0 and self.death_state.alive:
            self.death_state.alive = False
            self.death_state.killing_dmg = dmg
    
    @event.member_listener(event_types.CurHpModify.EXECUTE)
    def cur_hp_modify(self, e):
        self.cur_hp += e.amount
        hp = self.stats["hp"].calculate()
        if self.cur_hp > hp:
            self.cur_hp = hp
        
    @event.member_listener(event_types.Die.EXECUTE)
    def die(self, e):
        decision.provider.notify({"name": "die", "target": str(self.uuid)})
        event.bus.dispatch(event_types.Clean(self))
    
    @event.member_listener(event_types.Clean.EXECUTE)
    def clean(self, e):
        self.death_state.cleaned = True
        self.effects.clean()
        battle.current.refresh()
    
    @event.member_listener(event_types.Heal.EXECUTE)
    def receive_heal(self, e):
        if self is not e.heal.target:
            return
        amount = e.heal.calculate()
        decision.provider.notify({"name": "heal", "healer": str(e.heal.healer.uuid), "target": str(self.uuid), "amount": amount})
        event.bus.dispatch(event_types.CurHpModify(self, amount))
    
    @event.member_listener(event_types.AddEffect.EXECUTE)
    def add_effect(self, e):
        eff_add = e.eff_add
        decision.provider.notify({"name": "add_effect", "adder": str(eff_add.adder.uuid), "target": str(self.uuid),
            "effect": eff_add.effect.full_name(), "duration": eff_add.duration, "stacks": eff_add.stacks})
        self.effects.add(eff_add.effect, eff_add.adder, eff_add.duration, eff_add.stacks)

def lerp(a, b, t):
    return a + (b - a) * t

def from_uuid(id):
    return all_targets.get(id)
