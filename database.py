import json
import os

PLAYERS_FILE = "players.json"
FLOWERS_FILE = "flowers.json"
REGISTRY_FILE = "registry.json"


def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)

    with open(filename, "r") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def get_players():
    return load_json(PLAYERS_FILE)


def save_players(data):
    save_json(PLAYERS_FILE, data)


def get_flowers():
    return load_json(FLOWERS_FILE)


def save_flowers(data):
    save_json(FLOWERS_FILE, data)


def get_registry():
    return load_json(REGISTRY_FILE)


def save_registry(data):
    save_json(REGISTRY_FILE, data)
