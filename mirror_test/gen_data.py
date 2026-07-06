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
action_advance <target> <scale>
action_delay <target> <scale>
weakness_break <target>
break_weakness <dealer> <target> <damage_amount> [<effect_name>]
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

class Preprocessor:
    class Macro:
        def __init__(self, params, content):
            self.params = params
            self.content = content
        
        def format(self, args):
            return self.content.format(**dict(zip(self.params, args)))

    def __init__(self):
        self.macros = {}
    
    def preprocess(self, content):
        content = self.prepare(content)
        while True:
            content, modified = self.process(content)
            if not modified:
                return content
    
    def prepare(self, content):
        cur_preprocess = None
        header = []
        contents = []
        processed = []
        for line in content.splitlines():
            idx = line.find("//")
            if idx != -1:
                line = line[:idx]
            line = line.strip()
            if not line:
                continue
            if line[0] == "#":
                parts = line[1:].split()
                if parts[0] != "end":
                    cur_preprocess = parts[0]
                    header = parts[1:]
                else:
                    assert cur_preprocess == parts[1]
                    method = getattr(self, "preprocess_" + cur_preprocess)
                    method(header, "\n".join(contents))
                    cur_preprocess = None
                    header = []
                    contents = []
            elif cur_preprocess is not None:
                contents.append(line)
            else:
                processed.append(line)
        return "\n".join(processed)
    
    def process(self, content):
        modified = False
        processed = []
        for line in content.splitlines():
            parts = line.split()
            if parts[0] in self.macros:
                line = self.macros[parts[0]].format(parts[1:])
                modified = True
            processed.append(line)
        return "\n".join(processed), modified
    
    def preprocess_define(self, header, content):
        self.macros[header[0]] = self.Macro(header[1:], content)

class Generator:
    def __init__(self):
        self.process = []

    def coerce_steps(self, step_or_steps):
        if step_or_steps is None:
            return []
        if isinstance(step_or_steps, list):
            return step_or_steps
        return [step_or_steps]
    
    def parse_bool(self, text):
        return text == "true"
    
    def parse_float(self, text):
        return float(text)
    
    def parse_list(self, text):
        return text.split(",")
    
    def gen_new_wave(self):
        return {
            "message_info": {
                "type": "update",
                "name": "new_wave"
            },
            "tests": []
        }
    
    def gen_normal_turn_start(self, target):
        return {
            "message_info": {
                "type": "update",
                "name": "normal_turn_start"
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        }
    
    def gen_extra_turn(self, name, target):
        return {
            "message_info": {
                "type": "update",
                "name": name
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        }

    def gen_skill_trigger(self, target, skill_name):
        return {
            "message_info": {
                "type": "update",
                "name": "skill_trigger"
            },
            "tests": [
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
        }
    
    def gen_damage(self, dealer, target, types, amount, crit=None):
        steps = []
        if crit is not None:
            steps.extend(self.coerce_steps(self.gen_ask_random_rate(crit)))
        tests = [
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
        steps.append({
            "message_info": {
                "type": "update",
                "name": "damage"
            },
            "tests": tests
        })
        return steps if len(steps) > 1 else steps[0]
    
    def gen_reduce_toughness(self, dealer, target, amount):
        return {
            "message_info": {
                "type": "update",
                "name": "reduce_toughness"
            },
            "tests": [
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
        }
    
    def gen_character_damage(self, dealer, target, types, amount, crit=None, toughness_reduction=None):
        steps = self.coerce_steps(self.gen_damage(dealer, target, types, amount, crit))
        if toughness_reduction is not None:
            steps.extend(self.coerce_steps(self.gen_reduce_toughness(dealer, target, toughness_reduction)))
        return steps
    
    def gen_monster_damage(self, dealer, target, types, amount):
        return self.gen_damage(dealer, target, types, amount)
    
    def gen_heal(self, healer, target, amount):
        return {
            "message_info": {
                "type": "update",
                "name": "heal"
            },
            "tests": [
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
        }
    
    def gen_add_effect(self, adder, target, effect_name):
        return {
            "message_info": {
                "type": "update",
                "name": "add_effect"
            },
            "tests": [
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
        }
    
    def gen_action_advance(self, target, scale):
        return {
            "message_info": {
                "type": "update",
                "name": "action_advance"
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_scale",
                    "scale": self.parse_float(scale)
                }
            ]
        }
    
    def gen_action_delay(self, target, scale):
        return {
            "message_info": {
                "type": "update",
                "name": "action_delay"
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                },
                {
                    "$type": "assert_scale",
                    "scale": self.parse_float(scale)
                }
            ]
        }
    
    def gen_weakness_break(self, target):
        return {
            "message_info": {
                "type": "update",
                "name": "weakness_break"
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        }
    
    def gen_break_weakness(self, dealer, target, damage_amount, effect_name=None):
        steps = []
        steps.extend(self.coerce_steps(self.gen_character_damage(dealer, target, "break", damage_amount)))
        steps.extend(self.coerce_steps(self.gen_action_delay(target, "0.25")))
        if effect_name is not None:
            steps.extend(self.coerce_steps(self.gen_ask_random_rate("true")))
            steps.extend(self.coerce_steps(self.gen_add_effect(dealer, target, effect_name)))
        steps.extend(self.coerce_steps(self.gen_weakness_break(target)))
        return steps
    
    def gen_die(self, target):
        return {
            "message_info": {
                "type": "update",
                "name": "die"
            },
            "tests": [
                {
                    "$type": "assert_target",
                    "name": "target",
                    "uuid": target
                }
            ]
        }
    
    def gen_battle_win(self):
        return {
            "message_info": {
                "type": "update",
                "name": "battle_win"
            },
            "tests": []
        }
    
    def gen_battle_lose(self):
        return {
            "message_info": {
                "type": "update",
                "name": "battle_lose"
            },
            "tests": []
        }
    
    def gen_ask_ultimate(self, character=None, target=None):
        process = {
            "message_info": {
                "type": "ask",
                "name": "ultimate"
            },
            "tests": []
        }
        if character is not None:
            process["response"] = {
                "type": "ask",
                "name": "ultimate",
                "character": character
            }
            if target is not None:
                process["response"]["target"] = target
        return process
    
    def gen_ask_character_skill_option(self, option, target=None):
        step = {
            "message_info": {
                "type": "ask",
                "name": "character_skill_option"
            },
            "tests": [],
            "response": {
                "type": "ask",
                "name": "character_skill_option",
                "option": option
            }
        }
        if target is not None:
            step["response"]["target"] = target
        return step
    
    def gen_ask_random_rate(self, result):
        return {
            "message_info": {
                "type": "ask",
                "name": "random_rate"
            },
            "tests": [],
            "response": {
                "type": "ask",
                "name": "random_rate",
                "result": self.parse_bool(result)
            }
        }
    
    def gen_ask_random_monster_target(self, result):
        return {
            "message_info": {
                "type": "ask",
                "name": "random_monster_target"
            },
            "tests": [],
            "response": {
                "type": "ask",
                "name": "random_monster_target",
                "result": result
            }
        }

preprocessor = Preprocessor()
generator = Generator()

with open(input_filename, "r", encoding="utf-8") as f:
    content = preprocessor.preprocess(f.read())
    in_group = False
    for line in content.splitlines():
        parts = line.split()
        if parts[0] == "begin":
            generator.process.append([])
            in_group = True
            continue
        elif parts[0] == "end":
            in_group = False
            continue
        if parts[0] == "ask":
            method = getattr(generator, "gen_ask_" + parts[1])
            steps = method(*parts[2:])
        else:
            method = getattr(generator, "gen_" + parts[0])
            steps = method(*parts[1:])
        if in_group:
            generator.process[-1].extend(generator.coerce_steps(steps))
        else:
            for step in generator.coerce_steps(steps):
                generator.process.append([step])

with open(config_filename, "r", encoding="utf-8") as f:
    data = json.load(f)

data["process"] = generator.process

with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
