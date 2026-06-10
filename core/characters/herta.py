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
        def __init__(self, t):
            super().__init__("what_are_you_looking_at", "What Are You Looking At?", skill.SkillType.SINGLE, t, 1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, 0.4 + 0.1 * level)),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
            dmg.energy_regen = 20
            await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 1:
                hp = t.stats["hp"].calculate()
                if t.cur_hp <= hp * 0.5:
                    dmg = damage.Damage(self.target, t,
                        modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, 0.4)),
                        self.target.element, damage.DmgType.ADDITIONAL, damage.DmgSource.BASIC_ATTACK)
                    await battle.current.event_bus.dispatch("deal_damage", dmg)

    class Skill(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("one_time_offer", "One-Time Offer", skill.SkillType.AOE, t, -1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            mult = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8125, 0.875, 0.9375, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25)[level - 1]
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, mult)),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.SKILL)
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
                dmg.energy_regen = 30 / len(battle.current.monsters)
                dmg.hit_split = (0.3, 0.7)
                if t.cur_hp >= t.stats["hp"].calculate() * 0.5:
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.2
                    if self.target.traces_unlocked[0]:
                        dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.25
                await battle.current.event_bus.dispatch("attack", dmg)
    
    class Ultimate(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("its_magic_i_added_some_magic", "It's Magic, I Added Some Magic", skill.SkillType.AOE, t, 0)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False
            level = self.level + self.bonus_level
            mult = (1.2, 1.28, 1.36, 1.44, 1.52, 1.6, 1.7, 1.8, 1.9, 2, 2.08, 2.16, 2.24, 2.32, 2.4)[level - 1]
            for t in battle.current.monsters[:]:
                dmg = damage.Damage(self.target, t,
                    modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, mult)),
                    self.target.element, damage.DmgType.NORMAL, damage.DmgSource.ULTIMATE)
                dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 20, self.target.element)
                dmg.energy_regen = 5 / len(battle.current.monsters)
                if self.target.traces_unlocked[2] and t.frozen:
                    dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.2
                await battle.current.event_bus.dispatch("attack", dmg)
            if self.target.eidolons >= 6:
                nameid = "no_one_can_betray_me"
                name = "No One Can Betray Me"
                mod = modifier.Modifier(nameid, name, modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.BASE, 0.25)), None, self)
                eff = effect.ModifierEffect(nameid, name, self.target.effect_ids[nameid], effect.Effect.Type.BUFF, 1, effect.CommonEffect.DurationType.TURN_END, 1, mod, self.target.stats["atk"])
                await battle.current.event_bus.dispatch("add_effect", self.target, eff)
    
    class Talent(target.Character.CharacterSkill):
        class FollowUp(target.Target.FollowUpTurn):
            pass

        def __init__(self, t):
            super().__init__("fine_i_ll_do_it_myself", "Fine, I'll Do It Myself", skill.SkillType.AOE, t, 0)
            self.attacks = 0
            self.follow_up_launched = False
            battle.current.event_bus.add_member_listener(self.cur_hp_modify, t)
            battle.current.event_bus.add_member_listener(self.action_unit_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def cur_hp_modify(self, t, amount):
            if not isinstance(t, target.Monster):
                return
            hp = t.stats["hp"].calculate()
            if t.cur_hp <= hp * 0.5 and t.cur_hp - amount > hp * 0.5:
                self.attacks += 1
                if not self.follow_up_launched:
                    self.follow_up_launched = True
                    battle.current.action_list.append(Herta.Talent.FollowUp(self.target))
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def action_unit_trigger(self, action_unit):
            if isinstance(action_unit, Herta.Talent.FollowUp) and action_unit.target is self.target:
                action_unit.died = True
                level = self.level + self.bonus_level
                mult = (0.25, 0.265, 0.28, 0.295, 0.31, 0.325, 0.34375, 0.3625, 0.38125, 0.4, 0.415, 0.43, 0.445, 0.46, 0.475)[level - 1]
                i = 0
                while i < self.attacks:
                    for t in battle.current.monsters[:]:
                        dmg = damage.Damage(self.target, t,
                            modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, 1)),
                            self.target.element, damage.DmgType.NORMAL, damage.DmgSource.FOLLOW_UP)
                        dmg.factors[damage.DamageFactorType.MULTIPLIER] = mult
                        dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 5, self.target.element)
                        dmg.energy_regen = 5 / len(battle.current.monsters)
                        if self.target.eidolons >= 4:
                            dmg.factors[damage.DamageFactorType.DMG_BOOST] += 0.1
                        await battle.current.event_bus.dispatch("attack", dmg)
                    if self.target.eidolons >= 2:
                        nameid = "keep_the_ball_rolling"
                        name = "Keep the Ball Rolling"
                        mod = modifier.Modifier(nameid, name, modifier.StatDesc((None, None, 0.03)), None, self)
                        eff = effect.ModifierEffect(nameid, name, self.target.effect_ids[nameid], effect.Effect.Type.BUFF,
                            -1, effect.CommonEffect.DurationType.PERMANENT, 5, mod, self.target.stats["crt_rate"])
                        await battle.current.event_bus.dispatch("add_effect", self.target, eff)
                    i += 1
                self.attacks = 0
                self.follow_up_launched = False

    def __init__(self, record):
        super().__init__("herta", "Herta", enums.Element.ICE, enums.Path.ERUDITION)
        self.skills["basic_atk"].add(self.BasicAtk(self))
        self.skills["skill"].add(self.Skill(self))
        self.skills["ultimate"].add(self.Ultimate(self))
        self.skills["talent"].add(self.Talent(self))
        self.set_record(record)

        self.effect_ids = {
            "keep_the_ball_rolling": effect.Effect.next_id(),
            "no_one_can_betray_me": effect.Effect.next_id()
        }
    
    def set_record(self, record):
        super().set_record(record)

        t = (self.level - 1) / 79
        self.stats["hp"].base_value = target.lerp(130, 953, t)
        self.stats["atk"].base_value = target.lerp(79.2, 582.12, t)
        self.stats["def"].base_value = target.lerp(54, 396.9, t)
        self.stats["base_break_dmg"].base_value = target.lerp(54, 3767.5533, t)
        self.stats["spd"].base_value = 100
        self.stats["crt_rate"].base_value = 0.05
        self.stats["crt_dmg"].base_value = 0.5
        self.stats["taunt"].base_value = 0.75
        self.stats["energy"].base_value = 110
        self.stats["max_energy"].base_value = 110
        self.stats["energy_regen_rate"].base_value = 1

        self.update_lightcone_and_relics()

        if self.traces_stats_unlocked[0]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace0", "DEF Boost", modifier.StatDesc((self.stats["def"], modifier.ModifierFilter.BASE, 0.05)), None, self))
        if self.traces_stats_unlocked[1]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace1", "DMG Boost: Ice", modifier.StatDesc((None, None, 0.032)), None, self))
        if self.traces_stats_unlocked[2]:
            self.stats["crt_rate"].modifiers.append(modifier.Modifier(
                "herta.trace2", "CRT Rate Boost", modifier.StatDesc((None, None, 0.027)), None, self))
        if self.traces_stats_unlocked[3]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace3", "DMG Boost: Ice", modifier.StatDesc((None, None, 0.048)), None, self))
        if self.traces_stats_unlocked[4]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace4", "DEF Boost", modifier.StatDesc((self.stats["def"], modifier.ModifierFilter.BASE, 0.075)), None, self))
        if self.traces_stats_unlocked[5]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace5", "DMG Boost: Ice", modifier.StatDesc((None, None, 0.048)), None, self))
        if self.traces_stats_unlocked[6]:
            self.stats["crt_rate"].modifiers.append(modifier.Modifier(
                "herta.trace6", "CRT Rate Boost", modifier.StatDesc((None, None, 0.04)), None, self))
        if self.traces_stats_unlocked[7]:
            self.stats["def"].modifiers.append(modifier.Modifier(
                "herta.trace7", "DEF Boost", modifier.StatDesc((self.stats["def"], modifier.ModifierFilter.BASE, 0.1)), None, self))
        if self.traces_stats_unlocked[8]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace8", "DMG Boost: Ice", modifier.StatDesc((None, None, 0.032)), None, self))
        if self.traces_stats_unlocked[9]:
            self.stats["ice_dmg_boost"].modifiers.append(modifier.Modifier(
                "herta.trace9", "DMG Boost: Ice", modifier.StatDesc((None, None, 0.064)), None, self))
        if self.traces_unlocked[1]:
            self.stats["control_res"].modifiers.append(modifier.Modifier(
                "puppet", "Puppet", modifier.StatDesc((None, None, 0.35)), None, self))
        
        if self.eidolons >= 3:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
        if self.eidolons >= 5:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
