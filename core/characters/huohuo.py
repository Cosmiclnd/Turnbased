import target
import skill
import battle
import event
import damage
import healing
import modifier
import enums
import effect
import item

from characters import base

class Huohuo(base.Character):
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
                modifier.StatDesc((self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage"))),
                self.target.element, damage.DmgType.NORMAL, damage.DmgSource.BASIC_ATK)
            dmg.toughness_reduction = damage.ToughnessReduction(self.get_value("toughness_reduction"), self.target.element)
            dmg.energy_regen = self.get_value("energy_regen")
            for ratio in (0.2, 0.2, 0.2, 0.4):
                dmg.hit_split_ratio = ratio
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
            duration = self.target.config.get_skill_value("talent", "duration")
            if self.target.eidolons >= 1:
                duration += self.target.config.get_skill_value("eidolon1", "duration")
            await self.target.gain_divine_provision(duration)
            t = self.get_main_target()
            await t.effects.dispel(self.get_value("num_debuffs"), lambda eff: eff.type is effect.Effect.Type.DEBUFF)
            main = healing.Healing(self.target, t,
                modifier.StatDesc((
                    (self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("main_percentage")),
                    (None, None, self.get_value("main_flat"))
                )))
            await self.target.heal_by_skill(main)
            for t in self.get_adjacent_targets():
                sub = healing.Healing(self.target, t,
                    modifier.StatDesc((
                        (self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("sub_percentage")),
                        (None, None, self.get_value("sub_flat"))
                    )))
                await self.target.heal_by_skill(sub)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
    
    class Ultimate(base.Character.CharacterUltimate):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            duration = self.target.config.get_skill_value("talent", "duration")
            if self.target.eidolons >= 1:
                duration += self.target.config.get_skill_value("eidolon1", "duration")
            await self.target.gain_divine_provision(duration)
            for t in battle.current.characters[:]:
                if t is self.target:
                    continue
                await battle.current.event_bus.dispatch("regen_energy", t, t.stats["max_energy"].calculate() * self.get_value("energy_regen_rate"),
                    True)
                eff_add = effect.EffectAddition(self.target, t, self.target.effect_types.get(self.target.nameid, "ultimate"),
                    self.get_value("duration"))
                await battle.current.event_bus.dispatch("add_effect", eff_add)
            await battle.current.event_bus.dispatch("regen_energy", self.target, self.get_value("energy_regen"))
    
    class Talent(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)
        
            battle.current.event_bus.add_member_listener(self.turn_start, t)
            battle.current.event_bus.add_member_listener(self.ultimate_turn_start, t)
            battle.current.event_bus.add_member_listener(self.revive, t)
        
        async def heal(self, t):
            heal = healing.Healing(self.target, t,
                modifier.StatDesc((
                    (self.target.stats["hp"], modifier.ModifierFilter.CALCULATED, self.get_value("percentage")),
                    (None, None, self.get_value("flat"))
                )))
            await self.target.heal_by_skill(heal)
            if self.target.dispel_count > 0:
                self.target.dispel_count -= await t.effects.dispel(min(self.get_value("num_debuffs"), self.target.dispel_count),
                    lambda eff: eff.type is effect.Effect.Type.DEBUFF)
            if self.target.traces_unlocked[2]:
                await battle.current.event_bus.dispatch("regen_energy", self.target, self.target.config.get_skill_value("bonus_trace3", "energy"))
        
        async def trigger_divine_provision(self, t):
            await self.heal(t)
            await self.heal(min(battle.current.characters, key=lambda c: c.cur_hp / c.stats["hp"].calculate()))
            for c in battle.current.characters:
                if c.cur_hp <= c.stats["hp"].calculate() * self.get_value("hp_threshold"):
                    await self.heal(c)
            
        @event.member_listener(event.ListenerPriority.EXECUTE + 1, "normal_turn_start")
        async def turn_start(self, turn):
            if not isinstance(turn, target.Target.NormalTurn) or not isinstance(turn.target, base.Character) or not self.target.has_divine_provision():
                return
            await self.trigger_divine_provision(turn.target)
        
        @event.member_listener(event.ListenerPriority.EXECUTE + 1, "ultimate_turn")
        async def ultimate_turn_start(self, turn):
            if not self.target.has_divine_provision():
                return
            await self.trigger_divine_provision(turn.target)
        
        @event.member_listener(event.ListenerPriority.PRE_PROCESS, "die")
        async def revive(self, t):
            if not isinstance(t, base.Character) or not self.target.has_divine_provision():
                return
            if self.target.eidolons >= 2 and self.target.revive_count > 0 and not t.death_state.alive:
                t.death_state.clear()
                heal = healing.Healing(self.target, t,
                    modifier.StatDesc((t.stats["hp"], modifier.ModifierFilter.CALCULATED, self.target.config.get_skill_value("eidolon2", "percentage"))))
                await battle.current.event_bus.dispatch("heal", heal)
                await self.target.effects.advance_turn(self.target.effect_types["divine_provision"])
                self.target.revive_count -= 1
    
    class Technique(base.Character.CharacterSkill):
        def __init__(self, t, skill_name):
            super().__init__(t, skill_name)

            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            for m in battle.current.monsters:
                eff_add = effect.EffectAddition(self.target, m, self.target.effect_types.get(self.target.nameid, "technique"),
                    self.get_value("duration"))
                await self.target.try_apply_debuff(eff_add, self.get_value("base_chance"))
    
    class DivineProvisionEffect(effect.Effect):
        class Instance(effect.Effect.Instance):
            async def refresh(self):
                stacks = self.target.effects.get_stacks(self.effect)
                if self.target.eidolons >= 1:
                    if self.old_stacks == 0 and stacks != 0:
                        self.eff_dead = item.DeadToggle(self.target)
                        for c in battle.current.characters:
                            eff_add = effect.EffectAddition(self.target, c, self.target.effect_types.get(self.target.nameid, "eidolon1"), -1)
                            await battle.current.event_bus.dispatch("add_effect", eff_add)
                        if self.target.eidolons >= 1:
                            mod = modifier.Modifier(*self.target.config.get_skill_name("eidolon1"),
                                modifier.StatDesc((None, None, self.target.config.get_skill_value("eidolon1", "outgoing_healing_boost"))),
                                None, self.eff_dead)
                            self.target.stats["outgoing_healing_boost"].modifiers.append(mod)
                    elif self.old_stacks != 0 and stacks == 0:
                        self.eff_dead.dead_toggle = True
                        for c in battle.current.characters:
                            await c.effects.delete(self.target.effect_types.get(self.target.nameid, "eidolon1"))
                self.old_stacks = stacks

        def __init__(self):
            super().__init__("divine_provision", "Divine Provision", effect.Effect.Type.OTHERS, effect.Effect.DurationType.TURN_END, 1)
    
    def __init__(self, record):
        super().__init__("huohuo", record)
        
        battle.current.event_bus.add_member_listener(self.battle_start, self)

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
        self.effect_types.add_unique(self.DivineProvisionEffect())

        names = self.config.get_skill_name("ultimate")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.get_current_skill("ultimate").get_value("atk_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END_CHECK_START,
            1, "atk", mod), "ultimate")

        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, self.config.get_skill_value("bonus_trace2", "atk_boost"))),
                self.validator_trace2, self)
            self.effect_types.get(self.nameid, "ultimate").modifiers.append(mod)
        
        names = self.config.get_skill_name("technique")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("atk", modifier.ModifierFilter.BASE, -self.config.get_skill_value("technique", "atk_reduction"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END, 1, "atk", mod),
            "technique")
        
        names = self.config.get_skill_name("eidolon1")
        mod = modifier.Modifier(*names,
            modifier.StatDesc(("spd", modifier.ModifierFilter.BASE, self.config.get_skill_value("eidolon1", "spd_boost"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.PERMANENT, 1, "spd", mod), "eidolon1")
        
        names = self.config.get_skill_name("eidolon6")
        mod = modifier.Modifier(*names, modifier.StatDesc((None, None, self.config.get_skill_value("eidolon6", "percentage"))))
        self.effect_types.add_unique(effect.ModifierEffect(*names, effect.Effect.Type.BUFF, effect.Effect.DurationType.TURN_END, 1, "dmg_boost", mod), "eidolon6")

    def validator_trace2(self, stat, **kwargs):
        return stat.target.stats["max_energy"].calculate() >= self.config.get_skill_value("bonus_trace2", "energy_threshold")
    
    async def gain_divine_provision(self, duration):
        eff_add = effect.EffectAddition(self, self, self.effect_types.get(self.nameid, "divine_provision"), duration)
        await battle.current.event_bus.dispatch("add_effect", eff_add)
        self.dispel_count = self.config.get_skill_value("talent", "trigger_count")
        
    def has_divine_provision(self):
        return self.effects.has_effect(self.effect_types.get(self.nameid, "divine_provision"))
    
    async def heal_by_skill(self, heal):
        if self.eidolons >= 4:
            heal.multiplier += 0.8 * (1 - heal.target.cur_hp / heal.target.stats["hp"].calculate())
        if self.eidolons >= 6:
            eff_add = effect.EffectAddition(self, heal.target, self.effect_types.get(self.nameid, "eidolon6"),
                self.config.get_skill_value("eidolon6", "duration"))
            await battle.current.event_bus.dispatch("add_effect", eff_add)
        await battle.current.event_bus.dispatch("heal", heal)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        if self.traces_unlocked[1]:
            mod = modifier.Modifier(*self.config.get_skill_name("bonus_trace2"),
                modifier.StatDesc((None, None, self.config.get_skill_value("bonus_trace2", "control_res"))),
                None, self)
            self.stats["control_res"].modifiers.append(mod)
        
        if self.traces_unlocked[0]:
            await battle.current.event_bus.dispatch("regen_energy", self, self.config.get_skill_value("bonus_trace1", "energy"))
            await self.gain_divine_provision(self.config.get_skill_value("bonus_trace1", "duration"))
        
        self.dispel_count = 0
        if self.eidolons >= 2:
            self.revive_count = self.config.get_skill_value("eidolon2", "trigger_count")
