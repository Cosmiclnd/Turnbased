'''
Syntax:

UPDATE:
new_wave
normal_turn_start <target>
extra_turn <name> <target>
skill_trigger <target> <skill_name>
damage <dealer> <target> <types> <amount> [<crit>]
reduce_toughness <dealer> <target> <amount>
character_damage <dealer> <target> <types> <amount> [<crit>] [<toughness_reduction>]
monster_damage <dealer> <target> <types> <amount>
heal <healer> <target> <amount>
add_effect <adder> <target> <effect_name>
weakness_break <target>
die <target>
battle_win
battle_lose

ASK:
ultimate [<character>] [<target>]
character_skill_option <option> [<target>]
random_rate <result>
random_monster_target <result>
'''

import sys
import json

if len(sys.argv) != 2:
    print("Usage: python gen_data.py <name>")
    sys.exit(1)

name = sys.argv[1]
input_filename = f"mirror_test/{name}/process.txt"
config_filename = f"mirror_test/{name}/config.json"
output_filename = f"mirror_test/{name}/data.json"

class Generator:
    def __init__(self):
        self.process = []
    
    def parse_bool(self, text):
        return text == "true"
    
    def parse_float(self, text):
        return float(text)
    
    def parse_list(self, text):
        return text.split(",")
    
    def gen_new_wave(self):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "new_wave"
                }
            ]
        })
    
    def gen_normal_turn_start(self, target):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "normal_turn_start"
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        })
    
    def gen_extra_turn(self, name, target):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": name,
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        })

    def gen_skill_trigger(self, target, skill_name):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "skill_trigger"
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_skill_name",
                    "name": skill_name
                }
            ]
        })
    
    def gen_damage(self, dealer, target, types, amount, crit=None):
        if crit is not None:
            self.gen_ask_random_rate(crit)
        tests = [
            {
                "$type": "assert_message_name",
                "type": "update",
                "name": "damage"
            },
            {
                "$type": "assert_target",
                "name": "dealer",
                "uuid": dealer
            },
            {
                "$type": "assert_target",
                "name": "target",
                "uuid": target
            },
            {
                "$type": "assert_damage_types",
                "types": self.parse_list(types)
            },
            {
                "$type": "assert_damage_amount",
                "amount": self.parse_float(amount)
            }
        ]
        if crit is not None:
            tests.append({
                "$type": "assert_damage_crit",
                "crit": self.parse_bool(crit)
            })
        self.process.append({
            "tests": tests
        })
    
    def gen_reduce_toughness(self, dealer, target, amount):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "reduce_toughness"
                },
                {
                    "$type": "assert_target",
                    "name": "dealer",
                    "uuid": dealer
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_toughness_amount",
                    "amount": self.parse_float(amount)
                }
            ]
        })
    
    def gen_character_damage(self, dealer, target, types, amount, crit=None, toughness_reduction=None):
        self.gen_damage(dealer, target, types, amount, crit)
        if toughness_reduction is not None:
            self.gen_reduce_toughness(dealer, target, toughness_reduction)
    
    def gen_monster_damage(self, dealer, target, types, amount):
        self.gen_damage(dealer, target, types, amount)
    
    def gen_heal(self, healer, target, amount):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "heal"
                },
                {
                    "$type": "assert_target",
                    "name": "healer",
                    "uuid": healer
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_heal_amount",
                    "amount": self.parse_float(amount)
                }
            ]
        })
    
    def gen_add_effect(self, adder, target, effect_name):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "add_effect"
                },
                {
                    "$type": "assert_target",
                    "name": "adder",
                    "uuid": adder
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_effect_name",
                    "name": effect_name
                }
            ]
        })
    
    def gen_weakness_break(self, target):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "weakness_break"
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        })
    
    def gen_die(self, target):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "update",
                    "name": "die"
                },
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        })
    
    def gen_ask_ultimate(self, character=None, target=None):
        process = {
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "ask",
                    "name": "ultimate"
                }
            ]
        }
        if character is not None:
            process["response"] = {
                "type": "ask",
                "name": "ultimate",
                "character": character
            }
        if target is not None:
            process["response"]["target"] = target
        self.process.append(process)
    
    def gen_ask_character_skill_option(self, option, target=None):
        process = {
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "ask",
                    "name": "character_skill_option"
                }
            ],
            "response": {
                "type": "ask",
                "name": "character_skill_option",
                "option": option
            }
        }
        if target is not None:
            process["response"]["target"] = target
        self.process.append(process)
    
    def gen_ask_random_rate(self, result):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "ask",
                    "name": "random_rate"
                }
            ],
            "response": {
                "type": "ask",
                "name": "random_rate",
                "result": self.parse_bool(result)
            }
        })
    
    def gen_ask_random_monster_target(self, result):
        self.process.append({
            "tests": [
                {
                    "$type": "assert_message_name",
                    "type": "ask",
                    "name": "random_monster_target"
                }
            ],
            "response": {
                "type": "ask",
                "name": "random_monster_target",
                "result": result
            }
        })

generator = Generator()

with open(input_filename, "r", encoding="utf-8") as f:
    for line in f.readlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "ask":
            method = getattr(generator, "gen_ask_" + parts[1])
            method(*parts[2:])
        else:
            method = getattr(generator, "gen_" + parts[0])
            method(*parts[1:])

with open(config_filename, "r", encoding="utf-8") as f:
    data = json.load(f)

data["process"] = generator.process

with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
