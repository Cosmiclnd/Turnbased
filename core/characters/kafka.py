import item
import enums
import target
import event
import battle
import modifier
import damage
import effect
import action
from decision import base as decision
from monsters import base as monster

from characters import base

class Kafka(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1((t,))
            battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.5, 0.5):
                dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch("hit", dmg)
            battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1([self.get_main_target()] + self.get_adjacent_targets())
            battle.current.event_bus.dispatch("attack_start", self.target)
            t = self.get_main_target()
            dmg = damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("main_percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("main_toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.2, 0.3, 0.5):
                dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch("hit", dmg)
            for t in self.get_adjacent_targets():
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("sub_percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("sub_toughness_reduction"), self.target.element)
                battle.current.event_bus.dispatch("hit", dmg)
            battle.current.event_bus.dispatch("attack_end", self.target)
            battle.current.event_bus.dispatch("tick_dot",
                damage.DotTick(self.get_main_target(), lambda x: True, self.get_value("main_dot_tick_percentage")))
            for t in self.get_adjacent_targets():
                battle.current.event_bus.dispatch("tick_dot", damage.DotTick(t, lambda x: True, self.get_value("sub_dot_tick_percentage")))
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1(battle.current.monsters[:])
            battle.current.event_bus.dispatch("attack_start", self.target)
            for t in battle.current.monsters[:]:
                dmg = damage.Damage.create(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                battle.current.event_bus.dispatch("hit", dmg)
                self.target.inflict_shock(t, self.get_value("duration"), self.get_value("base_chance"))
            battle.current.event_bus.dispatch("attack_end", self.target)
            for t in battle.current.monsters[:]:
                battle.current.event_bus.dispatch("tick_dot", damage.DotTick(t, lambda x: True, self.get_value("dot_tick_percentage")))
            battle.current.event_bus.dispatch("energy_regen", self.target, self.get_value("energy_regen"))
            if self.target.traces_unlocked[2]:
                self.target.regain_follow_up_count()
    
    class Talent(base.Character.CharacterSkill):
        class FollowUp(target.Target.ExtraTurn):
            def __init__(self, t, skill):
                super().__init__(f"{t.nameid}_follow_up_turn", f"{t.name}'s Follow Up Turn", action.ExtraTurn.Priority.FOLLOW_UP, t)
                self.skill = skill
                battle.current.event_bus.add_member_listener(self.extra_turn, self)
                if not battle.current.features.get("kafka_follow_up_not_reset_at_new_wave"):
                    battle.current.event_bus.add_member_listener(self.new_wave_start, t)
            
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
                decision.provider.notify({"name": f"{self.target.nameid}.follow_up_turn", "target": str(self.target.uuid)})
                self.skill.follow_up_launched = False
                battle.current.event_bus.dispatch("skill_trigger", self.skill)
                self.master.dead_toggle = True
        
            @event.member_listener(event.ListenerPriority.EXECUTE)
            def new_wave_start(self):
                self.master.dead_toggle = True

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.follow_up_launched = False
            self.skill_target = None

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
            battle.current.event_bus.add_member_listener(self.attack_end, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.follow_up_count -= 1
            if self.target.eidolons >= 1:
                self.target.dot_dmg_vulnerability_eidolon1((self.skill_target,))
            battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = damage.Damage.create(self.target, self.skill_target,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.15, 0.15, 0.15, 0.15, 0.15, 0.25):
                dmg.hit_split_ratio = ratio
                battle.current.event_bus.dispatch("hit", dmg)
                self.target.inflict_shock(self.skill_target, self.get_value("duration"), self.get_value("base_chance"))
            battle.current.event_bus.dispatch("attack_end", self.target)
            if self.target.traces_unlocked[2]:
                battle.current.event_bus.dispatch("tick_dot", damage.DotTick(self.skill_target, lambda x: True,
                    self.target.config.get_skill_value("bonus_trace3", "dot_tick_percentage")))
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        def attack_end(self, t):
            if self.target is t or not isinstance(t, base.Character) or self.target.follow_up_count == 0 or self.follow_up_launched:
                return
            self.follow_up_launched = True
            battle.current.action_list.extras.append(self.FollowUp(self.target, self))
            self.skill_target = self.get_main_target() or battle.current.random.character_target()
    
    class Technique(base.Character.CharacterSkill):
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
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
                dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
                battle.current.event_bus.dispatch("hit", dmg)
                self.target.inflict_shock(t, self.get_value("duration"), self.get_value("base_chance"))
            battle.current.event_bus.dispatch("attack_end", self.target)
    
    class DotDmgVulnerabilityEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    battle.current.event_bus.add_member_listener(self.deal_damage, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.PRE_PROCESS)
            def deal_damage(self, dmg):
                if self.target is not dmg.target or not dmg.is_dot_dmg():
                    return
                dmg.factors[damage.DamageFactorType.VULNERABILITY] += self.effect.amount

        def __init__(self, nameid, name, amount):
            super().__init__(nameid, name, effect.Effect.Type.DEBUFF, effect.Effect.DurationType.TURN_END, 1)
            self.amount = amount
    
    def __init__(self, record):
        super().__init__("kafka", record)

        battle.current.event_bus.add_member_listener(self.battle_start, self)
        battle.current.event_bus.add_member_listener(self.normal_turn_end, self)
        if self.traces_unlocked[1]:
            battle.current.event_bus.add_member_listener(self.monster_cleaned, self)
        if self.eidolons >= 2:
            battle.current.event_bus.add_member_listener(self.deal_damage_eidolon2, self)
        if self.eidolons >= 4:
            battle.current.event_bus.add_member_listener(self.deal_damage_eidolon4, self)
    
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
        percentage = self.get_current_skill("ultimate").get_value("dot_percentage")
        if self.eidolons >= 6:
            percentage += self.config.get_skill_value("eidolon6", "percentage")
        dmg_desc = damage.DamageDesc(self,
            modifier.StatDesc((self.stats["atk"], modifier.ModifierFilter.CALCULATED, percentage)),
            enums.Element.LIGHTNING, damage.DmgType.DOT, damage.DmgSource.DOT)
        self.effect_types.add_unique(effect.DotEffect("shock", "Shock", dmg_desc, effect.Debuff.SHOCK, 1))

        self.effect_types.add_unique(self.DotDmgVulnerabilityEffect(*self.config.get_skill_name("eidolon1"),
            self.config.get_skill_value("eidolon1", "dot_dmg_vulnerability")), "eidolon1")
    
    def regain_follow_up_count(self):
        self.follow_up_count = min(self.follow_up_count + 1, self.get_current_skill("talent").get_value("trigger_count"))
    
    def validator_trace1(self, stat, **kwargs):
        return stat.target.stats["eff_hr"].calculate() >= self.config.get_skill_value("bonus_trace1", "eff_hr_threshold")

    @event.member_listener(event.ListenerPriority.EXECUTE)
    def battle_start(self):
        self.follow_up_count = self.get_current_skill("talent").get_value("trigger_count")

        if self.traces_unlocked[0]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace1"),
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.config.get_skill_value("bonus_trace1", "atk_boost"))),
                self.validator_trace1, self)
            for c in battle.current.characters:
                c.stats["atk"].modifiers.append(mod)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    def normal_turn_end(self, turn):
        if not isinstance(turn, target.Target.NormalTurn) or self is not turn.target:
            return
        self.regain_follow_up_count()
    
    @event.member_listener(event.ListenerPriority.EXECUTE - 1, "clean")
    def monster_cleaned(self, t):
        if not isinstance(t, monster.Monster):
            return
        context = t.death_state.killing_dmg.context
        if context.effect is not None and context.effect.is_debuff_type(effect.Debuff.SHOCK):
            battle.current.event_bus.dispatch("regen_energy", self, self.config.get_skill_value("bonus_trace2", "energy_regen"))
    
    @event.member_listener(event.ListenerPriority.PRE_PROCESS, "deal_damage")
    def deal_damage_eidolon2(self, dmg):
        if not isinstance(dmg.target, monster.Monster) or not dmg.is_dot_dmg():
            return
        dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.config.get_skill_value("eidolon2", "dot_dmg_boost")
    
    @event.member_listener(event.ListenerPriority.EXECUTE, "deal_damage")
    def deal_damage_eidolon4(self, dmg):
        if not isinstance(dmg.target, monster.Monster) or not dmg.is_dot_dmg():
            return
        context = dmg.context
        if context.effect is not None and context.effect.is_debuff_type(effect.Debuff.SHOCK) and context.effect_instance.caster is self:
            battle.current.event_bus.dispatch("regen_energy", self, self.config.get_skill_value("eidolon4", "energy_regen"))
    
    def inflict_shock(self, t, duration, base_chance):
        if self.eidolons >= 6:
            duration += self.config.get_skill_value("eidolon6", "duration")
        eff_add = effect.EffectAddition(self, t, self.effect_types.get(self.nameid, "shock"), duration)
        self.try_apply_debuff(eff_add, base_chance)
    
    def dot_dmg_vulnerability_eidolon1(self, targets):
        for t in targets:
            eff_add = effect.EffectAddition(self, t, self.effect_types.get(self.nameid, "eidolon1"),
                self.config.get_skill_value("eidolon1", "duration"))
            self.try_apply_debuff(eff_add, self.config.get_skill_value("eidolon1", "base_chance"))
