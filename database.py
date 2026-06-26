import json
import os
from datetime import datetime

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


# ---------- PLAYERS ----------

def get_players():
    return load_json(PLAYERS_FILE)


def save_players(players):
    save_json(PLAYERS_FILE, players)


def register_player(discord_id, ign):
    players = get_players()
    players[str(discord_id)] = {"ign": ign}
    save_players(players)


def get_ign(discord_id):
    players = get_players()
    user = players.get(str(discord_id))
    if not user:
        return None
    return user["ign"]


# ---------- FLOWERS ----------

def get_flowers():
    return load_json(FLOWERS_FILE)


def save_flowers(flowers):
    save_json(FLOWERS_FILE, flowers)


# ---------- REGISTRY ----------

def get_registry():
    return load_json(REGISTRY_FILE)


def save_registry(registry):
    save_json(REGISTRY_FILE, registry)


def claim_flower(flower_name, ign, discord_id):

    registry = get_registry()

    if flower_name in registry:
        return False, registry[flower_name]["owner"]

    registry[flower_name] = {
        "owner": ign,
        "discord_id": str(discord_id),
        "claimed_at": datetime.utcnow().isoformat()
    }

    save_registry(registry)

    return True, ign
