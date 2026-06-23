import asyncio
import aioconsole
import websockets
import json
from termcolor import cprint

port = 55716

async def send_message(websocket, message):
    await websocket.send(json.dumps(message))

def print_stats(stats):
    for name, values in stats.items():
        if name == "base_break_dmg":
            continue
        cprint(f"  {name}: ", "cyan", end="")
        if name in ("hp", "atk", "def", "spd", "energy", "max_energy", "toughness"):
            cprint(f"{round(values[1], 2)}", "green", end="")
            print(f" ({round(values[0], 2)})")
        else:
            cprint(f"{round(values[1] * 100, 2)}%", "green", end="")
            print(f" ({round(values[0] * 100, 2)}%)")

def print_skills(skills):
    translate_category = {"basic_atk": "Basic ATK", "skill": "Skill", "ultimate": "Ultimate", "talent": "Talent", "trace": "Trace", "eidolon": "Eidolon"}
    translate_type = {"single": "Single Target", "blast": "Blast", "bounce": "Bounce", "aoe": "AoE", "restore": "Restore", "support": "Support", "others": "Others"}
    for category in skills:
        for skill in skills[category]:
            title = skill["name"] + " - " + translate_category[category]
            if "type" in skill:
                title += " | " + translate_type[skill["type"]]
            cprint(title, "light_blue")
            colored = False
            for char in skill["desc"]:
                if char == "*":
                    colored = not colored
                elif colored:
                    cprint(char, "light_yellow", end="")
                else:
                    print(char, end="")
            print()

async def handle_query(websocket, words):
    if len(words) < 2:
        cprint("Unknown query type.", "red")
        return
    query_type = words[1]
    match query_type:
        case "monsters":
            if len(words) == 2:
                await send_message(websocket, {"type": "query_monsters", "subtype": "base"})
                response = json.loads(await websocket.recv())
                for i, t in enumerate(response["monsters"]):
                    cprint(f"[{i}] {t['name']} HP: {round(t['cur_hp'])}/{round(t['hp'])} ({t['nameid']})", "cyan")
            elif len(words) == 4:
                subtype = words[2]
                idx = int(words[3])
                await send_message(websocket, {"type": "query_monsters", "subtype": subtype, "monster": idx})
                response = json.loads(await websocket.recv())
                if subtype == "stats":
                    cprint(f"Stats of [{idx}] {response['monster']['name']} ({response['monster']['nameid']})", "cyan")
                    print_stats(response["monster"]["stats"])
        case "characters":
            if len(words) == 2:
                await send_message(websocket, {"type": "query_characters", "subtype": "base"})
                response = json.loads(await websocket.recv())
                for i, t in enumerate(response["characters"]):
                    cprint(f"[{i}] {t['name']} "
                        f"HP: {round(t['cur_hp'])}/{round(t['hp'])} "
                        f"Energy: {round(t['cur_energy'])}/{round(t['energy'])} "
                        f"({t['nameid']})", "cyan")
            elif len(words) == 4:
                subtype = words[2]
                idx = int(words[3])
                await send_message(websocket, {"type": "query_characters", "subtype": subtype, "character": idx})
                response = json.loads(await websocket.recv())
                if subtype == "stats":
                    cprint(f"Stats of [{idx}] {response['character']['name']} ({response['character']['nameid']})", "cyan")
                    print_stats(response["character"]["stats"])
                elif subtype == "skills":
                    cprint(f"Skills of [{idx}] {response['character']['name']} ({response['character']['nameid']})", "cyan")
                    print_skills(response["character"]["skills"])
            else:
                cprint("Unknown query type.", "red")

async def handle_command(websocket, command):
    words = command.split()
    if words[0] in ("exit", "e"):
        await websocket.close()
        raise SystemExit
    elif words[0] in ("query", "q"):
        await handle_query(websocket, words)
    elif words[0] == "exec":
        await send_message(websocket, {"type": "exec", "code": command[5:]})
        response = json.loads(await websocket.recv())
        print("return = " + response["result"])
        print(response["output"])
    else:
        cprint("Unknown command.", "red")

async def handle_input(websocket, allow_empty=False):
    while True:
        cprint("> ", "light_green", end="")
        raw = (await aioconsole.ainput()).strip()
        if not raw:
            if allow_empty:
                return ""
            continue
        if raw[0] == "/":
            await handle_command(websocket, raw[1:])
            continue
        return raw

async def respond_prepare_next_action_unit(websocket, message):
    if message["verbose"]:
        print("-" * 50)
        cprint(f"New action unit is about to start.", "yellow")
    while True:
        option = await handle_input(websocket, True)
        if not option:
            return {"type": "empty"}
        words = option.split()
        if len(words) != 2:
            cprint("Option format: <option> <index>", "light_red")
            continue
        opt, index = words
        if not index.isdigit():
            cprint("Option format: <option> <index>", "light_red")
            continue
        if opt not in ("u", "ultimate"):
            cprint("Can only use ultimate.", "light_red")
            continue
        return {"type": "prepare_ultimate", "index": int(index)}

async def respond_start_normal_turn(websocket, message):
    cprint(f"{message['name']} takes a Normal Turn.", "light_yellow")
    return {"type": "empty"}

async def respond_character_normal_turn_option(websocket, message):
    match message["info"]:
        case "bad_option":
            cprint("Options: basic_atk(a/b/q), skill(s/e)", "light_red")
        case "not_enough_skillpoints":
            cprint("Not enough skillpoints.", "light_red")
        case "invalid_target":
            cprint("Invalid target.", "light_red")
        case _:
            if message["info"] is not None:
                cprint(message["info"], "light_red")
    while True:
        option = await handle_input(websocket)
        words = option.split()
        if len(words) != 2:
            cprint("Option format: <option> <index>", "light_red")
            continue
        opt, index = words
        if not index.isdigit():
            cprint("Option format: <option> <index>", "light_red")
            continue
        break
    if opt in ("a", "b", "q"):
        opt = "basic_atk"
    if opt in ("s", "e"):
        opt = "skill"
    if opt in ("u", "ultimate"):
        return {"type": "character_prepare_ultimate"}
    return {"type": "character_normal_turn_option", "option": opt, "index": int(index)}

async def respond_start_ultimate_turn(websocket, message):
    cprint(f"{message['name']} takes an Ultimate Turn.", "light_yellow")
    return {"type": "empty"}

async def respond_deal_damage(websocket, message):
    cprint(f"{message['dealer']['name']} deals {round(message['amount'])} {message['dmg_type']['name']} DMG to {message['target']['name']}.", "light_blue")
    return {"type": "empty"}

async def respond_heal(websocket, message):
    cprint(f"{message['healer']['name']} heals {round(message['amount'])} HP to {message['target']['name']}.", "light_blue")
    return {"type": "empty"}

async def respond_die(websocket, message):
    cprint(f"{message['name']} dies.", "light_red")
    return {"type": "empty"}

async def respond_battle_win(websocket, message):
    cprint(f"Battle completed.", "green")
    raise SystemExit

async def respond_battle_lose(websocket, message):
    cprint(f"Battle failed.", "red")
    raise SystemExit

async def handle_message(websocket, message):
    type = message["type"]
    if type == "prepare_next_action_unit":
        return await respond_prepare_next_action_unit(websocket, message)
    elif type == "start_normal_turn":
        return await respond_start_normal_turn(websocket, message)
    elif type == "character_normal_turn_option":
        return await respond_character_normal_turn_option(websocket, message)
    elif type == "start_ultimate_turn":
        return await respond_start_ultimate_turn(websocket, message)
    elif type == "deal_damage":
        return await respond_deal_damage(websocket, message)
    elif type == "heal":
        return await respond_heal(websocket, message)
    elif type == "die":
        return await respond_die(websocket, message)
    elif type == "battle_win":
        return await respond_battle_win(websocket, message)
    elif type == "battle_lose":
        return await respond_battle_lose(websocket, message)

async def main():
    async with websockets.connect(f'ws://localhost:{port}') as websocket:
        await send_message(websocket, {"type": "init_battle"})
        record_herta = {
            "level": 80,
            "eidolons": 6,
            "basic_atk_level": 6,
            "skill_level": 10,
            "ultimate_level": 10,
            "talent_level": 10,
            "technique_level": 1,
            "traces_stats_unlocked": (True,) * 10,
            "traces_unlocked": (True, True, True),
            "lightcone": {
                "name": "the_birth_of_the_self",
                "level": 80,
                "stacks": 5
            },
            "relics": {
                "head": {
                    "name": "hunter_of_glacial_forest",
                    "level": 15,
                    "main_stat_type": "hp",
                    "sub_stat_types": ["crt_rate", "crt_dmg", "atk%", "spd"],
                    "enhancements": [(1, 2), (1, 2, 1), (1, 2, 2), (2,)]
                },
                "hands": {
                    "name": "hunter_of_glacial_forest",
                    "level": 15,
                    "main_stat_type": "atk",
                    "sub_stat_types": ["crt_rate", "atk%", "crt_dmg", "spd"],
                    "enhancements": [(1, 2, 1, 1), (2, 2, 2), (2,), (2,)]
                },
                "body": {
                    "name": "hunter_of_glacial_forest",
                    "level": 15,
                    "main_stat_type": "crt_rate",
                    "sub_stat_types": ["crt_dmg", "def%", "atk%", "spd"],
                    "enhancements": [(1, 2, 1, 1), (1, 0), (2, 2), (1,)]
                },
                "feet": {
                    "name": "hunter_of_glacial_forest",
                    "level": 15,
                    "main_stat_type": "spd",
                    "sub_stat_types": ["crt_rate", "crt_dmg", "atk%", "hp%"],
                    "enhancements": [(1, 2, 1, 1), (1, 2, 1), (1,), (2,)]
                },
                "planar_sphere": {
                    "name": "inert_salsotto",
                    "level": 15,
                    "main_stat_type": "ice_dmg_boost",
                    "sub_stat_types": ["crt_rate", "crt_dmg", "atk%", "def%"],
                    "enhancements": [(1, 2, 1, 1), (1, 0), (2, 2), (0,)]
                },
                "link_rope": {
                    "name": "inert_salsotto",
                    "level": 15,
                    "main_stat_type": "energy_regen_rate",
                    "sub_stat_types": ["crt_rate", "crt_dmg", "atk%", "def%"],
                    "enhancements": [(1, 2), (1, 2, 2), (2, 1, 2), (0,)]
                }
            }
        }
        record_huohuo = {
            "level": 80,
            "eidolons": 6,
            "basic_atk_level": 6,
            "skill_level": 10,
            "ultimate_level": 10,
            "talent_level": 10,
            "technique_level": 1,
            "traces_stats_unlocked": (True,) * 10,
            "traces_unlocked": (True, True, True),
            "lightcone": {
                "name": "night_of_fright",
                "level": 80,
                "stacks": 5
            },
            "relics": {
                "head": {
                    "name": "passerby_of_wandering_cloud",
                    "level": 15,
                    "main_stat_type": "hp",
                    "sub_stat_types": ["def", "spd", "hp%", "crt_rate"],
                    "enhancements": [(1, 2), (1, 2, 1), (1, 2, 2), (0,)]
                },
                "hands": {
                    "name": "passerby_of_wandering_cloud",
                    "level": 15,
                    "main_stat_type": "atk",
                    "sub_stat_types": ["hp%", "spd", "eff_res", "atk%"],
                    "enhancements": [(1, 1, 0, 1), (2, 2), (2,), (2,)]
                },
                "body": {
                    "name": "passerby_of_wandering_cloud",
                    "level": 15,
                    "main_stat_type": "outgoing_healing_boost",
                    "sub_stat_types": ["hp%", "def%", "spd", "break_eff"],
                    "enhancements": [(1, 2, 1, 1), (1, 0), (2, 2), (1,)]
                },
                "feet": {
                    "name": "passerby_of_wandering_cloud",
                    "level": 15,
                    "main_stat_type": "spd",
                    "sub_stat_types": ["spd", "eff_res", "hp", "hp%"],
                    "enhancements": [(1, 2, 1, 1), (1, 2, 1), (1,), (2,)]
                },
                "planar_sphere": {
                    "name": "fleet_of_the_ageless",
                    "level": 15,
                    "main_stat_type": "hp%",
                    "sub_stat_types": ["eff_res", "spd", "atk%", "def%"],
                    "enhancements": [(1, 2, 1, 1), (1, 0), (2, 2), (0,)]
                },
                "link_rope": {
                    "name": "fleet_of_the_ageless",
                    "level": 15,
                    "main_stat_type": "energy_regen_rate",
                    "sub_stat_types": ["hp", "eff_res", "hp%", "def%"],
                    "enhancements": [(1, 2), (1, 2, 2), (2, 1, 2), (0,)]
                }
            }
        }
        record_ruan_mei = {
            "level": 80,
            "eidolons": 6,
            "basic_atk_level": 6,
            "skill_level": 10,
            "ultimate_level": 10,
            "talent_level": 10,
            "technique_level": 1,
            "traces_stats_unlocked": (True,) * 10,
            "traces_unlocked": (True, True, True)
        }
        await send_message(websocket, {"type": "add_character", "name": "herta", "record": record_herta})
        await send_message(websocket, {"type": "add_character", "name": "huohuo", "record": record_huohuo})
        await send_message(websocket, {"type": "add_character", "name": "ruan_mei", "record": record_ruan_mei})
        for i in range(5):
            await send_message(websocket, {"type": "add_monster", "name": "baryon", "level": 120, "moc": True})
            #await send_message(websocket, {"type": "add_monster", "name": "dummy", "level": 120, "moc": True})
        await send_message(websocket, {"type": "start_battle"})
        while True:
            message = json.loads(await websocket.recv())
            response = await handle_message(websocket, message)
            await send_message(websocket, response)
        await send_message(websocket, {"type": "end_battle"})

asyncio.run(main())
