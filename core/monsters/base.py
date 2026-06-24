import json

import target
import skill
import event
import battle
import config
import enums
import effect

class Monster(target.Target):
    class MonsterConfig(target.Target.TargetConfig):
        __slots__ = ()

        def __init__(self, data, t):
            super().__init__(data, t)
        
        def init(self):
            self.target.tier = enums.MonsterTier.dict_nameid[self.data["tier"]]
            self.target.base_weakness = list(map(lambda x: enums.Element.dict_nameid[x], self.data["weakness"]))
        
        def set_base_stats(self):
            for stat_name in ("hp", "atk", "def", "spd"):
                self.target.stats[stat_name].base_value = self.get_base_stat(
                    stat_name, self.target.level, self.target.moc) * self.data["base_stat_scales"][stat_name]
            for stat_name in ("eff_hr", "eff_res"):
                self.target.stats[stat_name].base_value = self.get_base_stat(
                    stat_name, self.target.level, self.target.moc) + self.data["base_stat_flats"][stat_name]
            for element in enums.Element.ALL:
                self.target.stats[f"{element.nameid}_res"].base_value = self.data["base_dmg_res"][element.nameid]
            self.target.stats["toughness"].base_value = self.data["toughness"]
    
        @classmethod
        def get_base_stat(cls, name, level, moc):
            if name == "def":
                return 200 + min(level, 100) * 10
            if not hasattr(cls, "level_curve"):
                with open("core/config/monsters/level_curve.json", "r") as f:
                    cls.level_curve = json.load(f)
            curve = cls.level_curve["3" if moc else "1"]
            return curve[name][level - 1]

    class MonsterSkill(skill.Skill):
        def __init__(self, t, skill_name):
            self.skill_name = skill_name
            config_data = t.config.data["skills"][skill_name]
            nameid, name = t.config.get_skill_name(skill_name)
            type = skill.SkillType.dict_nameid[config_data["type"]]
            super().__init__(nameid, name, type, t)

        def get_target(self):
            taunts = [c.stats["taunt"].calculate() for c in battle.current.characters]
            return battle.current.random.choices(battle.current.characters, weights=taunts)[0]
        
        def get_value(self, name):
            return self.target.config.get_skill_value(self.skill_name, name)

    def __init__(self, nameid, level, moc):
        self.config = self.MonsterConfig(config.load_config_data("monsters", nameid), self)
        if nameid != self.config.nameid:
            logging.warning(f"Monster nameid mismatch: {nameid} != {self.config['nameid']}")

        super().__init__(nameid, self.config.name, level)
        self.config.init()
        self.moc = moc
        self.additional_weakness = []
        self.stats.new_stats(["toughness", "toughness_vulnerability"], self)
        self.skills = skill.SkillGroup(self)
        self.cur_toughness = 0
        self.weakness_broken = False

        battle.current.event_bus.add_member_listener(self.normal_turn, self)
        battle.current.event_bus.add_member_listener(self.reduce_toughness, self)
        battle.current.event_bus.add_member_listener(self.check_weakness_break, self)
        battle.current.event_bus.add_member_listener(self.weakness_break, self)
        battle.current.event_bus.add_member_listener(self.weakness_recover, self)

        self.config.set_base_stats()

    def init_skills(self, skill_classes):
        for i, skill in enumerate(skill_classes):
            self.skills.add(skill(self, f"skill{i + 1}"))
    
    def has_weakness(self, elem):
        return elem in self.base_weakness or elem in self.additional_weakness
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def battle_start(self):
        # 这个listener在Target类中已经被添加
        await super().battle_start()
        self.cur_toughness = self.stats["toughness"].calculate()
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def normal_turn(self, t):
        if self is not t:
            return
        self.frozen = self.effects.has_debuff(effect.Debuff.FROZEN)
        if self.frozen:
            target.Target.NormalTurn.advance_target(self, 0.5)
            return
        if self.weakness_broken:
            await battle.current.event_bus.dispatch("weakness_recover", self)
        await battle.current.event_bus.dispatch("skill_group_trigger", self.skills)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def reduce_toughness(self, tr):
        if self is not tr.target:
            return
        self.cur_toughness -= tr.calculate()

    @event.member_listener(event.ListenerPriority.POST_PROCESS, "reduce_toughness")
    async def check_weakness_break(self, tr):
        if self is not tr.target:
            return
        if self.cur_toughness <= 0:
            self.cur_toughness = 0
            if not self.weakness_broken:
                await battle.current.event_bus.dispatch("weakness_break", tr)
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def weakness_break(self, tr):
        if self is not tr.target:
            return
        self.weakness_broken = True
    
    @event.member_listener(event.ListenerPriority.EXECUTE)
    async def weakness_recover(self, tr):
        if self is not tr.target:
            return
        self.cur_toughness = self.stats["toughness"].calculate()
        self.weakness_broken = False
