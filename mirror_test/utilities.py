import websockets
import json
import pytest

port = 55716

async def send_message(websocket, message):
    await websocket.send(json.dumps(message))

async def recv_message(websocket):
    return json.loads(await websocket.recv())

async def start(name):
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
        await send_message(websocket, {"type": "setup_random", "config": {"use_random": False}})
        await send_message(websocket, {"type": "start_battle"})
        await main(websocket, data)

class Tester:
    def __init__(self, uuids):
        self.uuids = uuids
    
    def test(self, type, test, message):
        method = getattr(self, type)
        method(test, message)
    
    def respond(self, response):
        name = f"respond_{response['type']}_{response['name']}"
        if hasattr(self, name):
            return getattr(self, name)(response)
        else:
            return response
    
    def assert_message_name(self, test, message):
        assert message["type"] == test["type"]
        assert message["name"] == test["name"]
    
    def assert_target(self, test, message):
        name = test["name"]
        uuid_name = test["uuid"]
        assert message[name] == self.uuids[uuid_name]
    
    def assert_skill_name(self, test, message):
        assert message["skill"] == test["name"]
    
    def assert_damage_types(self, test, message):
        assert message["damage"]["types"] == test["types"]
    
    def assert_damage_crit(self, test, message):
        assert message["damage"]["crit"] == test["crit"]
    
    def assert_damage_amount(self, test, message):
        assert pytest.approx(message["damage"]["amount"], abs=2) == test["amount"]  # TODO: error too high
    
    def assert_toughness_amount(self, test, message):
        assert pytest.approx(message["amount"], abs=1e-6) == test["amount"]
    
    def assert_effect_name(self, test, message):
        assert message["effect"] == test["name"]
    
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
    for step in process:
        message = await recv_message(websocket)
        for test in step["tests"]:
            type = test["$type"]
            tester.test(type, test, message)
        if "response" in step:
            await send_message(websocket, tester.respond(step["response"]))
        else:
            await send_message(websocket, {"type": "empty"})
