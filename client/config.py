import json

config_data_cache = {}

def load_config_data(category, nameid):
    name = category + "." + nameid
    if name not in config_data_cache:
        with open(f"config/{category}/{nameid}.json", "r", encoding="utf-8") as f:
            config_data_cache[name] = json.load(f)
    return config_data_cache[name]
