import asyncio
from mihomo import Language, MihomoAPI
import json

with open("client/data/translate_data.json", "r", encoding="utf-8") as f:
    translate_data = json.load(f)

def get_record(character):
    id = character.id
    record = {
        "name": translate_data["character_name"][id],
        "level": character.level,
        "eidolons": character.eidolon,
        "traces_stats_unlocked": [False] * 10,
        "traces_unlocked": [False] * 3
    }
    for node in character.trace_tree:
        node_id = str(node.id)
        if node_id[4] == "0":  # 技能
            skill_type = translate_data["skill_type"][node_id[5:7]]
            max_level = 6 if skill_type == "basic_atk" else 10
            record[f"{skill_type}_level"] = max_level - (node.max_level - node.level)
        elif node_id[4] == "1":  # 额外能力
            idx = int(node_id[5:7]) - 1
            if node.level > 0:
                record["traces_unlocked"][idx] = True
        elif node_id[4] == "2":  # 属性加成
            idx = int(node_id[5:7]) - 1
            if node.level > 0:
                record["traces_stats_unlocked"][idx] = True
    if character.light_cone is not None:
        record["lightcone"] = {
            "name": translate_data["lightcone_name"][str(character.light_cone.id)],
            "level": character.light_cone.level,
            "stacks": character.light_cone.superimpose
        }
    for relic in character.relics:
        relic_id = str(relic.id)
        if relic_id[0] != "6":
            continue  # 不支持非5星遗器
        relic_type = translate_data["relic_type_name"][relic_id[-1]]
        if "relics" not in record:
            record["relics"] = {}
        relic_record = {
            "name": translate_data["relic_set_name"][str(relic.set_id)],
            "level": relic.level,
            "main_stat_type": translate_data["stat_name"][relic.main_affix.type],
            "sub_stat_types": [],
            "enhancements": []
        }
        for sub in relic.sub_affixes:
            relic_record["sub_stat_types"].append(translate_data["stat_name"][sub.type])
            enhancements = [0] * (sub.count - 1) + [sub.step]
            relic_record["enhancements"].append(enhancements)
        record["relics"][relic_type] = relic_record
    return record

async def fetch_record(uid):
    '''client = MihomoAPI(language=Language.EN)
    try:
        data = await client.fetch_user(uid)
    except Exception as e:
        print("Failed to fetch user:", e)
        return'''  # TODO: currently [500] Internal Server Error and waiting for fix
    import pickle
    with open("client/temp_data.pkl", "rb") as f:
        data = pickle.load(f)  # TODO: temp
    characters = []
    for character in data.characters:
        try:
            characters.append(get_record(character))
        except Exception as e:
            characters.append({})
    return characters

if __name__ == "__main__":
    uid = input("uid: ")
    asyncio.run(fetch_record(int(uid)))
