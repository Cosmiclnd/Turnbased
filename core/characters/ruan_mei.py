import item
import target
import event
import battle
import modifier
import damage
import effect
import action
from monsters import base as monster

from characters import base

class RuanMei(base.Character):
    class BasicAtk(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_main_target()
            await battle.current.event_bus.dispatch("attack_start", self.target)
            dmg = await damage.Damage.create(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATTACK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.target, t, self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            await battle.current.event_bus.dispatch("hit", dmg)
            await battle.current.event_bus.dispatch("attack_end", self.target)
    
    class Skill(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "overtone"),
                self.get_value("duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
    
    class Ultimate(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
            battle.current.event_bus.add_member_listener(self.hit, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            self.target.cur_energy -= self.target.stats["energy"].calculate()
            self.target.ultimate_activated = False
            duration = self.get_value("duration")
            if self.target.eidolons >= 6:
                duration += self.target.config.get_skill_value("eidolon6", "duration")
            eff_add = effect.EffectAddition(self.target, self.target, self.target.effect_types.get(self.target.nameid, "zone"), duration)
            await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def hit(self, dmg):
            if not isinstance(dmg.target, monster.Monster):
                return
            if self.target.effects.has_effect(self.target.effect_types.get(self.target.nameid, "zone")) and dmg.target.weakness_broken:
                eff_add = effect.EffectAddition(self.target, dmg.target, self.target.effect_types.get(self.target.nameid, "thanatoplum_rebloom"),
                    -1)
                await battle.current.event_bus.dispatch("add_effect", eff_add)
    
    class Talent(base.Character.CharacterSkill):
        pass
    
    class OvertoneEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.mod_dead = item.DeadToggle(self.target)
                    skill = self.target.get_current_skill("skill")
                    mod_dmg_boost = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, skill.get_value("dmg_boost"))), None, self.mod_dead)
                    for c in battle.current.characters:
                        c.stats["dmg_boost"].modifiers.append(mod_dmg_boost)
                    mod_wb_eff = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, skill.get_value("wb_eff_boost"))), None, self.mod_dead)
                    for c in battle.current.characters:
                        c.stats["wb_eff"].modifiers.append(mod_wb_eff)
                elif self.old_stacks != 0 and stacks == 0:
                    self.mod_dead.dead_toggle = True
                self.old_stacks = stacks

        def __init__(self):
            super().__init__("overtone", "Overtone", effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_START, 1)
    
    class ZoneEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    mod_res_pen = modifier.Modifier(self.effect.nameid, self.effect.name,
                        modifier.StatDesc((None, None, self.target.get_current_skill("ultimate").get_value("res_pen_boost"))), None, self.eff_dead)
                    for c in battle.current.characters:
                        c.stats["res_pen"].modifiers.append(mod_res_pen)
                    if self.target.eidolons >= 1:
                        battle.current.event_bus.add_member_listener(self.deal_damage, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.PRE_PROCESS)
            async def deal_damage(self, dmg):
                if not isinstance(dmg.dealer, base.Character):
                    return
                dmg.factors[damage.DamageFactorType.DEF_BOOST] -= self.target.config.get_skill_value("eidolon1", "def_ignore")

        def __init__(self):
            super().__init__("ruan_mei_zone", "Zone", effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_START, 1)
    
    class ThanatoplumRebloomEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.old_stacks == 0 and stacks != 0:
                    self.eff_dead = item.DeadToggle(self.target)
                    battle.current.event_bus.add_member_listener(self.weakness_recover, self.eff_dead)
                elif self.old_stacks != 0 and stacks == 0:
                    self.eff_dead.dead_toggle = True
                self.old_stacks = stacks
            
            @event.member_listener(event.ListenerPriority.PRE_PROCESS + 2)
            async def weakness_recover(self, t):
                if self.target is not t or not self.target.weakness_broken:
                    return
                await self.target.effects.delete(self.effect)
                self.effect.immune_targets.append(self.target)
                ultimate = self.effect.target.get_current_skill("ultimate")
                stat_desc = modifier.StatDesc((
                    (self.effect.target.stats["break_eff"], modifier.ModifierFilter.CALCULATED, ultimate.get_value("delay_percentage")),
                    (None, None, ultimate.get_value("delay_flat"))
                ))
                action.NormalTurn.advance_target(self.target, 1)  # 回退1回合
                action.NormalTurn.delay_target(self.target, stat_desc.calculate())
                dmg = await damage.Damage.create(self.effect.target, self.target,
                    modifier.StatDesc((self.effect.target.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED,
                        ultimate.get_value("percentage"))),
                    self.effect.target.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
                await battle.current.event_bus.dispatch("additional_damage", dmg)
                battle.current.event_bus.interrupt("normal_turn")

        def __init__(self, t):
            super().__init__("thanatoplum_rebloom", "Thanatoplum Rebloom", effect.Effect.Type.DEBUFF, effect.Effect.DurationType.PERMANENT, 1)
            self.immune_targets = []
            self.target = t
            battle.current.event_bus.add_member_listener(self.weakness_recover, t)
            
        @event.member_listener(event.ListenerPriority.EXECUTE - 1)
        async def weakness_recover(self, t):
            if self.target is not t:
                return
            if t in self.immune_targets:
                self.immune_targets.remove(t)

    def __init__(self, record):
        super().__init__("ruan_mei", record)

        battle.current.event_bus.add_member_listener(self.weakness_break, self)
        if self.traces_unlocked[1]:
            battle.current.event_bus.add_member_listener(self.turn_start, self)
        if self.eidolons >= 4:
            battle.current.event_bus.add_member_listener(self.before_weakness_break, self)
    
    def set_record(self, record):
        super().set_record(record)
        
        if self.eidolons >= 3:
            self.skills["ultimate"].set_bonus_level(2)
            self.skills["talent"].set_bonus_level(2)
        if self.eidolons >= 5:
            self.skills["skill"].set_bonus_level(2)
            self.skills["basic_atk"].set_bonus_level(1)

        self.set_effect_types()
    
    def set_effect_types(self):
        self.effect_types.add_unique(self.OvertoneEffect())
        self.effect_types.add_unique(self.ZoneEffect())
        self.effect_types.add_unique(self.ThanatoplumRebloomEffect(self))

        names = self.config.get_skill_name("talent")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, self.get_current_skill("talent").get_value("spd_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT, 1, "spd", mod),
            "talent")

        names = self.config.get_skill_name("eidolon4")
        mod = modifier.Modifier(*names,
            modifier.StatDesc((None, None, self.config.get_skill_value("eidolon4", "break_eff_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END, 1,
            "break_eff", mod), "eidolon4")
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        await super().battle_start()

        for c in battle.current.characters:
            if self is not c:
                eff_add = effect.EffectAddition(self, c, self.effect_types.get(self.nameid, "talent"), -1)
                await battle.current.event_bus.dispatch("add_effect", eff_add)

        if self.traces_unlocked[0]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace1"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace1", "break_eff_boost"))), None, self)
            for c in battle.current.characters:
                c.stats["break_eff"].modifiers.append(mod)
        
        if self.traces_unlocked[2]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace3"),
                modifier.StatDesc((self.stats["break_eff"], modifier.ModifierFilter.CALCULATED,  # 经测试可以二次转化
                    modifier.StatConverter(
                        self.config.get_skill_value("bonus_trace3", "break_eff_threshold"),
                        self.config.get_skill_value("bonus_trace3", "break_eff_step"),
                        self.config.get_skill_value("bonus_trace3", "dmg_boost"),
                        self.config.get_skill_value("bonus_trace3", "dmg_boost_cap")
                    ))), None, self)
            for c in battle.current.characters:
                c.stats["dmg_boost"].modifiers.append(mod)
        
        if self.eidolons >= 2:
            mod = modifier.Modifier(*self.config.get_skill_name("eidolon2"),
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon2", "atk_boost"))), self.validator_e2, self)
            for c in battle.current.characters:
                c.stats["atk"].modifiers.append(mod)
    
    def validator_e2(self, stat, **kwargs):
        dmg = kwargs.get("damage", None)
        if dmg is None:
            return False
        return dmg.target.weakness_break
    
    @event.member_listener(event.ListenerPriority.EXECUTE - 1)
    async def weakness_break(self, tr):
        mult = self.get_current_skill("talent").get_value("percentage")
        if self.eidolons >= 6:
            mult += self.config.get_skill_value("eidolon6", "percentage")
        dmg = await damage.Damage.create(self, tr.target,
            modifier.StatDesc((self.stats["base_break_dmg"], modifier.ModifierFilter.CALCULATED, mult)),
            self.element, damage.DmgType.BREAK, damage.DmgSource.WEAKNESS_BREAK)
        await battle.current.event_bus.dispatch("additional_damage", dmg)
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn_start")
    async def turn_start(self, turn):
        if self is not turn.target:
            return
        await battle.current.event_bus.dispatch("regen_energy", self, self.config.get_skill_value("bonus_trace2", "energy"))
    
    @event.member_listener(event.ListenerPriority.EXECUTE + 1, "weakness_break")
    async def before_weakness_break(self, tr):
        eff_add = effect.EffectAddition(self, self, self.effect_types["eidolon4"], self.config.get_skill_value("eidolon4", "duration"))
        await battle.current.event_bus.dispatch("add_effect", eff_add)
