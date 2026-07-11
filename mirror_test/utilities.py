import sys
import os
import websockets
import json
import pytest

port = 55716

async def send_message(websocket, message):
    await websocket.send(json.dumps(message))

async def recv_message(websocket):
    return json.loads(await websocket.recv())

async def start(name, gen_data=False):
    if gen_data:
        os.system(f"python mirror_test/gen_data.py {name}")
    async with websockets.connect(f'ws://localhost:{port}') as websocket:
        await send_message(websocket, {"type": "init_battle"})
        with open(f"mirror_test/{name}/data.json") as f:
            data = json.load(f)
        await send_message(websocket, {"type": "setup_monsters", "record": data["monsters"]})
        for record in data["characters"]:
            await send_message(websocket, {"type": "add_character", "record": record})
        uuids = data["uuids"]
        for name, state in data["initial_state"].items():
            await send_message(websocket, {"type": "set_initial_state", "target": uuids[name], "state": state})
        for name in data["techniques"]:
            await send_message(websocket, {"type": "use_technique", "target": uuids[name]})
        await send_message(websocket, {"type": "setup_random", "config": {"use_random": False}})
        await send_message(websocket, {"type": "set_battle_config", "config": data["battle_config"]})
        await send_message(websocket, {"type": "start_battle"})
        await main(websocket, data)

class Tester:
    def __init__(self, uuids):
        self.uuids = uuids
    
    def test(self, step, message):
        if message["type"] != step["message_info"]["type"] or message["name"] != step["message_info"]["name"]:
            return False
        for test in step["tests"]:
            method = getattr(self, test["$type"])
            if not method(test, message):
                return False
        return True
    
    def respond(self, response):
        name = f"respond_{response['type']}_{response['name']}"
        if hasattr(self, name):
            return getattr(self, name)(response)
        else:
            return response
    
    def assert_target(self, test, message):
        return message[test["name"]] == self.uuids[test["uuid"]]
    
    def assert_skill_name(self, test, message):
        return message["skill"] == test["name"]
    
    def assert_damage_types(self, test, message):
        return set(message["damage"]["types"]) == set(test["types"])
    
    def assert_damage_crit(self, test, message):
        return message["damage"]["crit"] == test["crit"]
    
    def assert_damage_amount(self, test, message):
        return pytest.approx(message["damage"]["amount"], abs=1) == test["amount"]
    
    def assert_toughness_amount(self, test, message):
        return pytest.approx(message["amount"], abs=1e-6) == test["amount"]
    
    def assert_heal_amount(self, test, message):
        return pytest.approx(message["amount"], abs=1) == test["amount"]
    
    def assert_effect_name(self, test, message):
        return message["effect"] == test["name"]
    
    def assert_turn_target(self, test, message):
        return message["turn"]["target"] == self.uuids[test["uuid"]]
    
    def assert_scale(self, test, message):
        return pytest.approx(message["scale"], abs=1e-6) == test["scale"]
    
    def respond_ask_ultimate(self, response):
        response["character"] = self.uuids[response["character"]]
        if "target" in response:
            response["target"] = self.uuids[response["target"]]
        return response
    
    def respond_ask_character_skill_option(self, response):
        if "target" in response:
            response["target"] = self.uuids[response["target"]]
        return response
    
    def respond_ask_random_monster_target(self, response):
        response["result"] = self.uuids[response["result"]]
        return response

async def main(websocket, data):
    tester = Tester(data["uuids"])
    process = data["process"]
    for group in process:
        while group:
            message = await recv_message(websocket)
            for step in group:
                if tester.test(step, message):
                    group.remove(step)
                    break
            else:
                assert False, f"group = {group}, message = {message}"
            if "response" in step:
                await send_message(websocket, tester.respond(step["response"]))
            else:
                await send_message(websocket, {"type": "empty"})
