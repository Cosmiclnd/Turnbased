import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect

class Herta(target.Character):
    class BasicAtk(target.Character.CharacterSkill):
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
                    await battle.current.event_bus.dispatch("deal_damage", dmg)

    class Skill(target.Character.CharacterSkill):
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
    
    class Ultimate(target.Character.CharacterSkill):
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
                if self.target.traces_unlocked[2] and t.frozen:
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += self.target.config.get_skill_value("bonus_trace3", "dmg_boost")
                await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 6:
                name = self.target.config.get_skill_name("eidolon6")
                mod = modifier.Modifier(*name,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.BASE, self.target.config.get_skill_value("eidolon6", "atk_boost"))),
                    None, self)
                eff = effect.ModifierEffect(*name, self.target.effect_ids[name[0]], effect.Effect.Type.BUFF, self.target.config.get_skill_value("eidolon6", "duration"), effect.CommonEffect.DurationType.TURN_END, 1, mod, self.target.stats["atk"])
                await battle.current.event_bus.dispatch("add_effect", self.target, eff)
    
    class Talent(target.Character.CharacterSkill):
        class FollowUp(target.Target.FollowUpTurn):
            pass

        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            self.attacks = 0
            self.follow_up_launched = False

            battle.current.event_bus.add_member_listener(self.cur_hp_modify, t)
            battle.current.event_bus.add_member_listener(self.action_unit_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def cur_hp_modify(self, t, amount):
            if not isinstance(t, target.Monster):
                return
            hp_threshold = t.stats["hp"].calculate() * self.get_value("hp_threshold")
            if t.cur_hp <= hp_threshold and t.cur_hp - amount > hp_threshold:
                self.attacks += 1
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.append(Herta.Talent.FollowUp(self.target))
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def action_unit_trigger(self, action_unit):
            if isinstance(action_unit, Herta.Talent.FollowUp) and action_unit.target is self.target:
                action_unit.died = True
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
                        name = self.target.config.get_skill_name("eidolon2")
                        mod = modifier.Modifier(*name,
                            modifier.StatDesc((None, None, self.target.config.get_skill_value("eidolon2", "crt_rate_boost"))), None, self)
                        eff = effect.ModifierEffect(*name, self.target.effect_ids[name[0]], effect.Effect.Type.BUFF,
                            -1, effect.CommonEffect.DurationType.PERMANENT, self.target.config.get_skill_value("eidolon2", "max_stacks"), mod, self.target.stats["crt_rate"])
                        await battle.current.event_bus.dispatch("add_effect", self.target, eff)
                    i += 1
                self.attacks = 0
                self.follow_up_launched = False
    
    def set_record(self, record):
        super().set_record(record)

        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)
        
        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)

        self.effect_ids = {
            self.config.get_skill_name("eidolon2")[0]: effect.Effect.next_id(),
            self.config.get_skill_name("eidolon6")[0]: effect.Effect.next_id()
        }
