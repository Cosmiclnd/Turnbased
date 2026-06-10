import target
import skill
import battle
import event
import damage
import modifier
import enums
import effect

class Huohuo(target.Character):
    class BasicAtk(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("banner_stormcaller", "Banner: Stormcaller", skill.SkillType.SINGLE, t, 1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            dmg = damage.Damage(self.target, t, self.target.stats["hp"], self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.factors[damage.DamageFactorType.MULTIPLIER] = 0.2 + 0.05 * level
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, 10, self.target.element)
            dmg.energy_regen = 20
            await battle.current.event_bus.dispatch("attack", dmg)
    
    class Skill(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("tailsman_protection", "Tailsman: Protection", skill.SkillType.RESTORE, t, -1)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            level = self.level + self.bonus_level
            t = self.get_main_target()
            # TODO
    
    class Ultimate(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("tail_spiritual_domination", "Tail: Spiritual Domination", skill.SkillType.SUPPORT, t, 0)
    
    class Talent(target.Character.CharacterSkill):
        def __init__(self, t):
            super().__init__("possession_ethereal_metaflow", "Possession: Ethereal Metaflow", skill.SkillType.RESTORE, t, 0)

    def __init__(self, record):
        super().__init__("huohuo", "Huohuo", enums.Element.WIND, enums.Path.ABUNDANCE)
        self.skills["basic_atk"].add(self.BasicAtk(self))
        self.skills["skill"].add(self.Skill(self))
        self.skills["ultimate"].add(self.Ultimate(self))
        self.skills["talent"].add(self.Talent(self))
        self.set_record(record)
    
    def set_record(self, record):
        super().set_record(record)

        t = (self.level - 1) / 79
        self.stats["hp"].base_value = target.lerp(185, 1358, t)
        self.stats["atk"].base_value = target.lerp(81.84, 601.52, t)
        self.stats["def"].base_value = target.lerp(69.3, 509.36, t)
        self.stats["base_break_dmg"].base_value = target.lerp(54, 3767.5533, t)
        self.stats["spd"].base_value = 98
        self.stats["crt_rate"].base_value = 0.05
        self.stats["crt_dmg"].base_value = 0.5
        self.stats["taunt"].base_value = 1
        self.stats["energy"].base_value = 140
        self.stats["max_energy"].base_value = 140
        self.stats["energy_regen_rate"].base_value = 1

        self.update_lightcone_and_relics()

        if self.traces_stats_unlocked[0]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace1", "Effect RES Boost", modifier.StatDesc((None, None, 0.04)), None, self))
        if self.traces_stats_unlocked[1]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace2", "HP Boost", modifier.StatDesc((self.stats["hp"], modifier.ModifierFilter.BASE, 0.04)), None, self))
        if self.traces_stats_unlocked[2]:
            self.stats["spd"].modifiers.append(modifier.Modifier(
                "huohuo.trace3", "SPD Boost", modifier.StatDesc((None, None, 2)), None, self))
        if self.traces_stats_unlocked[3]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace4", "HP Boost", modifier.StatDesc((self.stats["hp"], modifier.ModifierFilter.BASE, 0.06)), None, self))
        if self.traces_stats_unlocked[4]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace5", "Effect RES Boost", modifier.StatDesc((None, None, 0.06)), None, self))
        if self.traces_stats_unlocked[5]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace6", "HP Boost", modifier.StatDesc((self.stats["hp"], modifier.ModifierFilter.BASE, 0.06)), None, self))
        if self.traces_stats_unlocked[6]:
            self.stats["spd"].modifiers.append(modifier.Modifier(
                "huohuo.trace7", "SPD Boost", modifier.StatDesc((None, None, 3)), None, self))
        if self.traces_stats_unlocked[7]:
            self.stats["eff_res"].modifiers.append(modifier.Modifier(
                "huohuo.trace8", "Effect RES Boost", modifier.StatDesc((None, None, 0.08)), None, self))
        if self.traces_stats_unlocked[8]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace9", "HP Boost", modifier.StatDesc((self.stats["hp"], modifier.ModifierFilter.BASE, 0.04)), None, self))
        if self.traces_stats_unlocked[9]:
            self.stats["hp"].modifiers.append(modifier.Modifier(
                "huohuo.trace10", "HP Boost", modifier.StatDesc((self.stats["hp"], modifier.ModifierFilter.BASE, 0.08)), None, self))
        if self.traces_unlocked[1]:
            self.stats["control_res"].modifiers.append(modifier.Modifier(
                "the_cursed_one", "The Cursed One", modifier.StatDesc((None, None, 0.35)), None, self))
        
        if self.eidolons >= 3:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        if self.eidolons >= 5:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)
