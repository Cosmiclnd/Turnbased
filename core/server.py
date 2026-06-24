import websockets
import logging
import json
import os
import sys
import io

import battle
import target
import config

port = 55716
websocket = None

async def handle_message(message):
    type = message["type"]
    if type == "init_battle":
        battle.current = battle.Battle()
    elif type == "start_battle":
        await battle.current.start()
    elif type == "add_character":
        character = config.load_class("characters", message["name"])(message["record"])
        battle.current.characters.append(character)
    elif type == "setup_monsters":
        battle.current.monster_setup.set_record(message["record"])

async def handle(w):
    global websocket
    websocket = w
    while True:
        try:
            message = await websocket.recv()
            await handle_message(json.loads(message))
        except websockets.ConnectionClosedOK:
            logging.info("connection closed")
            break
        except Exception as e:
            logging.exception(e)
            logging.error(battle.current.event_bus.format_stack())
            logging.info("server closing")
            os._exit(1)

async def handle_command(message):
    type = message["type"]
    if type == "query_characters":
        subtype = message["subtype"]
        if subtype == "base":
            message["characters"] = [c.get_info() | {
                "cur_hp": c.cur_hp, "hp": c.stats["hp"].calculate(),
                "cur_energy": c.cur_energy, "energy": c.stats["energy"].calculate()
            } for c in battle.current.characters]
        elif subtype == "stats":
            c = battle.current.characters[message["character"]]
            message["character"] = c.get_info() | {"stats": c.get_stats_info()}
        elif subtype == "skills":
            c = battle.current.characters[message["character"]]
            message["character"] = c.get_info() | {"skills": c.get_skills_info()}
        await websocket.send(json.dumps(message))
    elif type == "query_monsters":
        subtype = message["subtype"]
        if subtype == "base":
            message["monsters"] = [m.get_info() | {"cur_hp": m.cur_hp, "hp": m.stats["hp"].calculate()} for m in battle.current.monsters]
        elif subtype == "stats":
            m = battle.current.monsters[message["monster"]]
            message["monster"] = m.get_info() | {"stats": m.get_stats_info()}
        await websocket.send(json.dumps(message))
    elif type == "exec":  # 暂时用来调试
        code = message["code"]
        logging.info(f"exec: \"{code}\"")
        stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            message["result"] = str(eval(code))
        except Exception as e:
            message["result"] = str(e)
        message["output"] = sys.stdout.getvalue()
        sys.stdout = stdout
        await websocket.send(json.dumps(message))
    else:
        return False
    return True

async def send_and_recv(message):
    await websocket.send(json.dumps(message))
    while True:
        response = json.loads(await websocket.recv())
        if not await handle_command(response):
            break
    return response
