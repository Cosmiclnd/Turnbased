import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect
import action
from monsters import base as monster

from characters import base

class Herta(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 1:
                hp = t.stats["hp"].calculate()
                if t.cur_hp <= hp * self.target.config.get_skill_value("eidolon1", "hp_threshold"):
                    dmg = damage.Damage(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.target.config.get_skill_value("eidolon1", "percentage"))),
                        self.target.element, damage.DmgType.ADDITIONAL, damage.DmgSource.BASIC_ATTACK)
                    await battle.current.event_bus.dispatch("additional_damage", dmg)

    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
                dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                dmg.hit_split = (0.3, 0.7)
                if t.cur_hp >= t.stats["hp"].calculate() * self.get_value("hp_threshold"):
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.get_value("dmg_boost")
                    if self.target.traces_unlocked[0]:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace1", "dmg_boost")
                await battle.current.event_bus.dispatch("attack", dmg)
    
    class Ultimate(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
                dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                if self.target.traces_unlocked[2] and t.effects.has_debuff(effect.Debuff.FROZEN):
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace3", "dmg_boost")
                await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 6:
                eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types["eidolon6"],
                    self.target.config.get_skill_value("eidolon6", "duration"))
                await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class Talent(base.Character.CharacterSkill):
        class FollowUp(action.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(t, action.ExtraTurn.Priority.FOLLOW_UP)
                self.skill = skill
                battle.current.event_bus.add_member_listener(self.extra_turn, self)

            def dead(self):
                if super().dead():
                    return True
                if self.skill.attacks == 0:
                    self.skill.follow_up_launched = False
                    return True
            
            def is_followup(self):
                return True
            
            @event.member_listener(event.ListenerPriority.EXECUTE)
            async def extra_turn(self, turn):
                if self is not turn:
                    return
                self.master.dead_toggle = True
                self.skill.follow_up_launched = False
                await self.skill.trigger_follow_up()

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.attacks = 0
            self.follow_up_launched = False

            battle.current.event_bus.add_member_listener(self.cur_hp_modify, t)
            battle.current.event_bus.add_member_listener(self.new_wave_start, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def cur_hp_modify(self, t, amount):
            if not isinstance(t, monster.Monster):
                return
            hp_threshold = t.stats["hp"].calculate() * self.get_value("hp_threshold")
            if t.cur_hp <= hp_threshold and t.cur_hp - amount > hp_threshold:
                self.attacks += 1
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.extras.append(Herta.Talent.FollowUp(self.target, self))
        
        async def trigger_follow_up(self):
            i = 0
            while i < self.attacks:
                for t in battle.current.monsters[:]:
                    dmg = damage.Damage(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
                    dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
                    dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                    if self.target.eidolons >= 4:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("eidolon4", "dmg_boost")
                    await battle.current.event_bus.dispatch("attack", dmg)
                if self.target.eidolons >= 2:
                    eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types["eidolon2"], -1)
                    await battle.current.event_bus.dispatch("add_effect", eff_add)
                i += 1
            self.attacks = 0
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def new_wave_start(self):
            self.attacks = 0
        
    def __init__(self, record):
        super().__init__("herta", record)
    
    def set_record(self, record):
        super().set_record(record)
        
        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        
        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types = {}

        names = self.config.get_skill_name("eidolon2")
        mod = modifier.Modifier(*names, modifier.StatDesc((None, None, self.config.get_skill_value("eidolon2", "crt_rate_boost"))), None, self)
        self.effect_types["eidolon2"] = effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT,
            self.config.get_skill_value("eidolon2", "max_stacks"), "crt_rate", mod)
        
        names = self.config.get_skill_name("eidolon6")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon6", "atk_boost"))), None, self)
        self.effect_types["eidolon6"] = effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END,
            1, "atk", mod)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        await super().battle_start()
        
        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)
