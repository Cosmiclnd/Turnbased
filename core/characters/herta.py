import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect
import action
import server
from monsters import base as monster

from characters import base

class Herta(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            battle.current.event_bus.dispatch("hit", dmg)
            if self.target.eidolons >= 1:
                hp = t.stats["hp"].calculate()
                if t.cur_hp <= hp * self.target.config.get_skill_value("eidolon1", "hp_threshold"):
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.target.config.get_skill_value("eidolon1", "percentage"))),
                        self.target.element, damage.DmgType.ADDITIONAL, damage.DmgSource.BASIC_ATK, False)
                    battle.current.event_bus.dispatch("additional_damage", dmg)
            battle.current.event_bus.dispatch("attack_end", self.target)

    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            battle.current.event_bus.dispatch("attack_start", self.target)
            for ratio in (0.3, 0.7):
                for t in battle.current.monsters[:]:
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                    dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                    dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                    if t.cur_hp >= t.stats["hp"].calculate() * self.get_value("hp_threshold"):
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.get_value("dmg_boost")
                        if self.target.traces_unlocked[0]:
                            dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace1", "dmg_boost")
                    dmg.hit_split_ratio = ratio
                    battle.current.event_bus.dispatch("hit", dmg)
            battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            battle.current.event_bus.dispatch("attack_start", self.target)
            for t in battle.current.monsters[:]:
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                if self.target.traces_unlocked[2] and t.effects.has_debuff(effect.Debuff.FROZEN):
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace3", "dmg_boost")
                battle.current.event_bus.dispatch("hit", dmg)
            if self.target.eidolons >= 6:
                eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "eidolon6"),
                    self.target.config.get_skill_value("eidolon6", "duration"))
                battle.current.event_bus.dispatch("add_effect", eff_add)
            battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Talent(base.Character.CharacterSkill):
        class FollowUp(target.Target.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(f"{t.nameid}_follow_up_turn", f"{t.name}'s Follow Up Turn", action.ExtraTurn.Priority.FOLLOW_UP, t)
                self.skill = skill
                battle.current.event_bus.add_member_listener(self.extra_turn, self)

            def dead(self):
                if super().dead():
                    return True
                return self.skill.attacks == 0
            
            def on_removed(self, list):
                super().on_removed(list)
                if list is battle.current.action_list.extras:
                    self.skill.follow_up_launched = False
            
            def is_follow_up(self):
                return True
            
            @event.member_listener(event.ListenerPriority.EXECUTE)
            def extra_turn(self, turn):
                if self is not turn:
                    return
                server.handler.update_client({"name": f"{self.target.nameid}.follow_up_turn", "target": str(self.target.uuid)})
                self.skill.follow_up_launched = False
                battle.current.event_bus.dispatch("skill_trigger", self.skill)
                self.master.dead_toggle = True

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.attacks = 0
            self.follow_up_launched = False
            self.immune_targets = []

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
            battle.current.event_bus.add_member_listener(self.hit, t)
            if not battle.current.features.get("herta_follow_up_not_reset_at_new_wave"):
                battle.current.event_bus.add_member_listener(self.new_wave_start, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            battle.current.event_bus.dispatch("attack_start", self.target)
            i = 0
            while i < self.attacks:
                for t in battle.current.monsters[:]:
                    dmg = damage.Damage.create(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                        self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
                    dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                    dmg.energy_regen = self.get_value("energy_regen") / len(battle.current.monsters)
                    if self.target.eidolons >= 4:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("eidolon4", "dmg_boost")
                    battle.current.event_bus.dispatch("hit", dmg)
                if self.target.eidolons >= 2:
                    eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "eidolon2"), -1)
                    battle.current.event_bus.dispatch("add_effect", eff_add)
                i += 1
            battle.current.event_bus.dispatch("attack_end", self.target)
            self.attacks = 0
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        def hit(self, dmg):
            if dmg.target in self.immune_targets or not isinstance(dmg.target, monster.Monster):
                return
            hp_threshold = dmg.target.stats["hp"].calculate() * self.get_value("hp_threshold")
            if dmg.target.cur_hp <= hp_threshold:
                self.attacks += 1
                self.immune_targets.append(dmg.target)
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.extras.append(Herta.Talent.FollowUp(self.target, self))
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def new_wave_start(self):
            self.attacks = 0
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "technique"),
                self.get_value("duration"))
            battle.current.event_bus.dispatch("add_effect", eff_add)
        
    def __init__(self, record):
        super().__init__("herta", record)

        battle.current.event_bus.add_member_listener(self.battle_start, self)
    
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
        names = self.config.get_skill_name("technique")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("technique", "atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END,
            1, "atk", mod), "technique")

        names = self.config.get_skill_name("eidolon2")
        mod = modifier.Modifier(*names, modifier.StatDesc((None, None, self.config.get_skill_value("eidolon2", "crt_rate_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT,
            self.config.get_skill_value("eidolon2", "max_stacks"), "crt_rate", mod), "eidolon2")
        
        names = self.config.get_skill_name("eidolon6")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon6", "atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END_CHECK_START,
            1, "atk", mod), "eidolon6")
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    def battle_start(self):
        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)
