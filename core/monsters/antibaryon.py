import target
import event
import skill
import battle
import damage
import enums

class Antibaryon(target.Monster):
    class Skill(target.Monster.MonsterSkill):
        def __init__(self, t):
            super().__init__("obliterate", "Obliterate", skill.SkillType.SINGLE, t)
            battle.current.event_bus.add_member_listener(self.skill_trigger, t)
        
        @event.member_listener(event.ListenerPriority.EXECUTE)
        async def skill_trigger(self, skill):
            if self is not skill:
                return
            t = self.get_target()
            dmg = damage.Damage(self.target, t,
                modifier.StatDesc((self.target.stats["atk"], modifier.ModifierFilter.CALCULATED, 2.5)),
                enums.Element.IMAGINARY, damage.DmgType.NORMAL, damage.DmgSource.MONSTER)
            dmg.energy_regen = 10
            await battle.current.event_bus.dispatch("attack", dmg)

    def __init__(self, level, moc):
        super().__init__("antibaryon", "Antibaryon", level, moc, enums.MonsterTier.NORMAL, [enums.Element.PHYSICAL, enums.Element.QUANTUM])
        self.skills.add(self.Skill(self))
        self.stats["hp"].base_value = target.Monster.get_base_stat("hp", level, moc) * 0.6
        self.stats["atk"].base_value = target.Monster.get_base_stat("atk", level, moc) * 18
        self.stats["def"].base_value = target.Monster.get_base_stat("def", level, moc)
        self.stats["spd"].base_value = target.Monster.get_base_stat("spd", level, moc) * 83
        self.stats["eff_hr"].base_value = target.Monster.get_base_stat("eff_hr", level, moc)
        self.stats["eff_res"].base_value = target.Monster.get_base_stat("eff_res", level, moc)
        self.stats["toughness"].base_value = 10
        self.stats["physical_res"].base_value = 0.2
        self.stats["fire_res"].base_value = 0.2
        self.stats["lightning_res"].base_value = 0.2
        self.stats["quantum_res"].base_value = 0.2
        self.stats["imaginary_res"].base_value = 0.2
