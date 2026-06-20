import item
import enums
import config
import modifier
import action
import effect
import event
import battle
import server

class DeathState:
    def __init__(self, t):
        self.target = t
        self.clear()

    def clear(self):
        self.alive = True
        self.need_clean = False
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
    
    class NormalTurn(action.ActionUnit):
        def __init__(self, target):
            super().__init__("normal_turn", "Normal Turn", action.ActionPriority.NORMAL_TURN, target)
            self.target = target
            self.start_action_value = 0
            self.scale = 1
        
        def action_value(self):
            return self.start_action_value + max(self.scale * 10000 / self.target.stats["spd"].calculate(), 0)
        
        def advance(self, scale):
            self.scale -= scale
        
        def delay(self, scale):
            self.advance(-scale)
        
        @classmethod
        def advance_target(cls, t, scale):
            for unit in battle.current.action_list:
                if isinstance(unit, Target.NormalTurn) and t is unit.target:
                    unit.advance(scale)
                    break
        
        @classmethod
        def delay_target(cls, t, scale):
            cls.advance_target(t, -scale)
    
    class ExtraTurn(action.ActionUnit):
        def __init__(self, target, priority):
            super().__init__("extra_turn", "Extra Turn", priority, item.DeadToggle(target))
            self.target = target
        
        def action_value(self):
            return 0
    
    class FollowUpTurn(ExtraTurn):
        def __init__(self, target):
            super().__init__(target, action.ActionPriority.FOLLOW_UP)

    def __init__(self, nameid, name, level):
        super().__init__(nameid, name, None)
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
        self.cur_hp = 0
        self.frozen = False
        self.death_state = DeathState(self)
        self.effects = effect.EffectList(self)

        battle.current.event_bus.add_member_listener(self.battle_start, self)
        battle.current.event_bus.add_member_listener(self.action_unit_trigger, self)
        battle.current.event_bus.add_member_listener(self.normal_turn_message, self)
        battle.current.event_bus.add_member_listener(self.attack, self)
        battle.current.event_bus.add_member_listener(self.hit, self)
        battle.current.event_bus.add_member_listener(self.additional_damage, self)
        battle.current.event_bus.add_member_listener(self.receive_damage, self)
        battle.current.event_bus.add_member_listener(self.cur_hp_modify, self)
        battle.current.event_bus.add_member_listener(self.die, self)
        battle.current.event_bus.add_member_listener(self.receive_heal, self)
        battle.current.event_bus.add_member_listener(self.add_effect, self)
    
    def dead(self):
        return self.death_state.need_clean
    
    def get_stats_info(self):
        return {name: (stat.calculate(modifier.ModifierFilter.BASE), stat.calculate()) for name, stat in self.stats.items()}
    
    async def check_death(self):
        if not self.death_state.alive:
            await battle.current.event_bus.dispatch("die", self)
    
    async def try_apply_debuff(self, eff_add, base_chance):
        chance = base_chance
        chance *= 1 + self.stats["eff_hr"].calculate(effect=eff_add.effect)
        chance *= max(1 - eff_add.target.stats["eff_res"].calculate(effect=eff_add.effect), 0)
        debuff_res = 0
        for debuff in effect.Debuff.ALL:
            debuff_res += eff_add.target.stats[f"{debuff.nameid}_res"].calculate(effect=eff_add.effect)
        chance *= max(1 - debuff_res, 0)
        if battle.current.random.random() < chance:
            await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        self.cur_hp = self.stats["hp"].calculate()
        self.death_state.clear()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def action_unit_trigger(self, action_unit):
        if isinstance(action_unit, Target.NormalTurn) and action_unit.target is self:
            battle.current.current_action_value = action_unit.action_value()
            action_unit.start_action_value = battle.current.current_action_value
            action_unit.order = action.ActionUnit.next_order()
            action_unit.scale = 1
            await battle.current.event_bus.dispatch("normal_turn", self)
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn")
    async def normal_turn_message(self, t):
        if self is not t:
            return
        message = {"type": "start_normal_turn"} | self.get_info()
        await server.send_and_recv(message)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def attack(self, damage):
        if self is not damage.dealer:
            return
        await damage.on_attack()
        await damage.target.check_death()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def hit(self, damage):
        if self is not damage.target:
            return
        await damage.on_hit()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def additional_damage(self, damage):
        if self is not damage.dealer:
            return
        await battle.current.event_bus.dispatch("deal_damage", damage)
        await damage.target.check_death()
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "deal_damage")
    async def receive_damage(self, damage):
        if self is not damage.target:
            return
        dmg = damage.calculate()
        message = {"type": "deal_damage", "dealer": damage.dealer.get_info(), "target": self.get_info(), "amount": dmg, "dmg_type": damage.types[0].get_info()}
        await server.send_and_recv(message)
        await battle.current.event_bus.dispatch("cur_hp_modify", self, -dmg)
        if self.cur_hp <= 0 and self.death_state.alive:
            self.death_state.alive = False
            self.death_state.killing_dmg = damage
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def cur_hp_modify(self, t, amount):
        if self is not t:
            return
        self.cur_hp += amount
        hp = self.stats["hp"].calculate()
        if self.cur_hp > hp:
            self.cur_hp = hp
        
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def die(self, t):
        if self is not t:
            return
        if not self.death_state.alive:
            message = {"type": "die"} | self.get_info()
            await server.send_and_recv(message)
            self.death_state.need_clean = True
            await self.effects.die()
            battle.current.refresh()
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "heal")
    async def receive_heal(self, heal):
        if self is not heal.target:
            return
        amount = heal.calculate()
        message = {"type": "heal", "healer": heal.healer.get_info(), "target": self.get_info(), "amount": amount}
        await server.send_and_recv(message)
        await battle.current.event_bus.dispatch("cur_hp_modify", self, amount)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def add_effect(self, eff_add):
        if self is not eff_add.target:
            return
        await self.effects.add(eff_add.effect, eff_add.duration, eff_add.stacks)

def lerp(a, b, t):
    return a + (b - a) * t
