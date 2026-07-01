from __future__ import annotations  
  
import json  
import os  
import tempfile  
from pathlib import Path  
from typing import Any  
  
class DatabaseError(Exception):  
    pass  
  
class ValidationError(DatabaseError):  
    pass  
  
class JSONStorage:  
    def __init__(self, basepath: str | Path | None = None) -> None:  
        self.basepath = Path(basepath) if basepath is not None else Path(__file__).resolve().parent  
        self.playersfile = self.basepath / "players.json"  
        self.flowersfile = self.basepath / "flowers.json"  
        self.registryfile = self.basepath / "registry.json"  
        self.configfile = self.basepath / "config.json"  
  
    def initializefiles(self) -> None:  
        self.ensurefile(self.playersfile, {})  
        self.ensurefile(self.flowersfile, {})  
        self.ensurefile(self.registryfile, {})  
        self.ensurefile(  
            self.configfile,  
            {  
                "registrychannelid": None,  
                "lookupchannelid": None,  
                "commandschannelid": None,  
                "managerroleid": None,  
                "registrymessageids": [],  
            },  
        )  
        self.normalizeall()  
  
    def loadplayers(self) -> dict[str, str]:  
        data = self.readjson(self.playersfile, {})  
        if not isinstance(data, dict):  
            raise ValidationError("players.json must contain a JSON object.")  
        normalized: dict[str, str] = {}  
        for discordid, ign in data.items():  
            if ign is None:  
                continue  
            discordidstr = str(discordid).strip()  
            ignstr = str(ign).strip()  
            if not discordidstr or not ignstr:  
                continue  
            normalized[discordidstr] = ignstr  
        if normalized != data:  
            self.saveplayers(normalized)  
        return normalized  
  
    def saveplayers(self, players: dict[str, str]) -> None:  
        normalized: dict[str, str] = {}  
        for discordid, ign in players.items():  
            discordidstr = str(discordid).strip()  
            ignstr = str(ign).strip()  
            if not discordidstr:  
                raise ValidationError("Player Discord ID cannot be empty.")  
            if not ignstr:  
                raise ValidationError("Player IGN cannot be empty.")  
            normalized[discordidstr] = ignstr  
        self.writejson(self.playersfile, normalized)  
  
    def loadflowers(self) -> dict[str, str]:  
        data = self.readjson(self.flowersfile, {})  
        if not isinstance(data, dict):  
            raise ValidationError("flowers.json must contain a JSON object.")  
        normalized: dict[str, str] = {}  
        for flowername, rarity in data.items():  
            if flowername is None or rarity is None:  
                continue  
            cleanname = self.normalizeflowername(str(flowername))  
            cleanrarity = self.normalizerarity(str(rarity))  
            normalized[cleanname] = cleanrarity  
        normalized = self.sortdictalphabetically(normalized)  
        if normalized != data:  
            self.saveflowers(normalized)  
        return normalized  
  
    def saveflowers(self, flowers: dict[str, str]) -> None:  
        normalized: dict[str, str] = {}  
        for flowername, rarity in flowers.items():  
            cleanname = self.normalizeflowername(flowername)  
            cleanrarity = self.normalizerarity(rarity)  
            normalized[cleanname] = cleanrarity  
        self.writejson(self.flowersfile, self.sortdictalphabetically(normalized))  
  
    def loadregistry(self) -> dict[str, list[str]]:  
        data = self.readjson(self.registryfile, {})  
        if not isinstance(data, dict):  
            raise ValidationError("registry.json must contain a JSON object.")  
        normalized: dict[str, list[str]] = {}  
        for flowername, owners in data.items():  
            cleanname = self.normalizeflowername(str(flowername))  
            if owners is None:  
                normalized[cleanname] = []  
                continue  
            if not isinstance(owners, list):  
                raise ValidationError(f"Registry entry for '{cleanname}' must be a list.")  
            cleanowners = self.normalizeownerlist(owners)  
            normalized[cleanname] = cleanowners  
        normalized = self.sortdictalphabetically(normalized)  
        if normalized != data:  
            self.saveregistry(normalized)  
        return normalized  
  
    def saveregistry(self, registry: dict[str, list[str]]) -> None:  
        normalized: dict[str, list[str]] = {}  
        for flowername, owners in registry.items():  
            cleanname = self.normalizeflowername(flowername)  
            if not isinstance(owners, list):  
                raise ValidationError(f"Registry entry for '{cleanname}' must be a list.")  
            normalized[cleanname] = self.normalizeownerlist(owners)  
        self.writejson(self.registryfile, self.sortdictalphabetically(normalized))  
  
    def loadconfig(self) -> dict[str, Any]:  
        defaultconfig = {  
            "registrychannelid": None,  
            "lookupchannelid": None,  
            "commandschannelid": None,  
            "managerroleid": None,  
            "registrymessageids": [],  
        }  
        data = self.readjson(self.configfile, defaultconfig)  
        if not isinstance(data, dict):  
            raise ValidationError("config.json must contain a JSON object.")  
        normalized = {  
            "registrychannelid": self.normalizeoptionalint(data.get("registrychannelid")),  
            "lookupchannelid": self.normalizeoptionalint(data.get("lookupchannelid")),  
            "commandschannelid": self.normalizeoptionalint(data.get("commandschannelid")),  
            "managerroleid": self.normalizeoptionalint(data.get("managerroleid")),  
            "registrymessageids": self.normalizemessageids(data.get("registrymessageids", [])),  
        }  
        if normalized != data:  
            self.saveconfig(normalized)  
        return normalized  
  
    def saveconfig(self, config: dict[str, Any]) -> None:  
        normalized = {  
            "registrychannelid": self.normalizeoptionalint(config.get("registrychannelid")),  
            "lookupchannelid": self.normalizeoptionalint(config.get("lookupchannelid")),  
            "commandschannelid": self.normalizeoptionalint(config.get("commandschannelid")),  
            "managerroleid": self.normalizeoptionalint(config.get("managerroleid")),  
            "registrymessageids": self.normalizemessageids(config.get("registrymessageids", [])),  
        }  
        self.writejson(self.configfile, normalized)  
  
    def getplayerign(self, discordid: int | str) -> str | None:  
        players = self.loadplayers()  
        return players.get(str(discordid))  
  
    def registerplayer(self, discordid: int | str, ign: str) -> None:  
        cleanign = self.normalizeign(ign)  
        players = self.loadplayers()  
        players[str(discordid)] = cleanign  
        self.saveplayers(players)  
  
    def updateplayerign(self, discordid: int | str, newign: str) -> tuple[str, str]:  
        players = self.loadplayers()  
        discordidstr = str(discordid)  
        if discordidstr not in players:  
            raise ValidationError("Player is not registered.")  
        oldign = players[discordidstr]  
        cleannewign = self.normalizeign(newign)  
        if oldign == cleannewign:  
            players[discordidstr] = cleannewign  
            self.saveplayers(players)  
            return oldign, cleannewign  
  
        players[discordidstr] = cleannewign  
        self.saveplayers(players)  
  
        registry = self.loadregistry()  
        for flowername, owners in registry.items():  
            updatedowners = [cleannewign if owner == oldign else owner for owner in owners]  
            registry[flowername] = self.normalizeownerlist(updatedowners)  
        self.saveregistry(registry)  
  
        return oldign, cleannewign  
  
    def removeplayerbyign(self, ign: str) -> bool:  
        cleanign = self.normalizeign(ign)  
        players = self.loadplayers()  
        removed = False  
  
        remainingplayers = {}  
        for discordid, playerign in players.items():  
            if playerign == cleanign:  
                removed = True  
                continue  
            remainingplayers[discordid] = playerign  
  
        registry = self.loadregistry()  
        for flowername, owners in registry.items():  
            registry[flowername] = [owner for owner in owners if owner != cleanign]  
        self.saveplayers(remainingplayers)  
        self.saveregistry(registry)  
  
        return removed  
  
    def addflower(self, flowername: str, rarity: str) -> None:  
        cleanname = self.normalizeflowername(flowername)  
        cleanrarity = self.normalizerarity(rarity)  
  
        flowers = self.loadflowers()  
        registry = self.loadregistry()  
  
        if cleanname in flowers:  
            raise ValidationError("Flower already exists.")  
  
        flowers[cleanname] = cleanrarity  
        registry.setdefault(cleanname, [])  
  
        self.saveflowers(flowers)  
        self.saveregistry(registry)  
  
    def renameflower(self, oldname: str, newname: str) -> None:  
        cleanoldname = self.normalizeflowername(oldname)  
        cleannewname = self.normalizeflowername(newname)  
  
        flowers = self.loadflowers()  
        registry = self.loadregistry()  
  
        if cleanoldname not in flowers:  
            raise ValidationError("Flower does not exist.")  
        if cleannewname in flowers and cleannewname != cleanoldname:  
            raise ValidationError("A flower with the new name already exists.")  
  
        rarity = flowers.pop(cleanoldname)  
        owners = registry.pop(cleanoldname, [])  
  
        flowers[cleannewname] = rarity  
        registry[cleannewname] = self.normalizeownerlist(owners)  
  
        self.saveflowers(flowers)  
        self.saveregistry(registry)  
  
    def removeflower(self, flowername: str) -> None:  
        cleanname = self.normalizeflowername(flowername)  
        flowers = self.loadflowers()  
        registry = self.loadregistry()  
  
        if cleanname not in flowers:  
            raise ValidationError("Flower does not exist.")  
  
        flowers.pop(cleanname, None)  
        registry.pop(cleanname, None)  
  
        self.saveflowers(flowers)  
        self.saveregistry(registry)  
  
    def claimflowers(self, ign: str, flowernames: list[str]) -> dict[str, list[str]]:  
        cleanign = self.normalizeign(ign)  
        flowers = self.loadflowers()  
        registry = self.loadregistry()  
  
        added: list[str] = []  
        alreadyowned: list[str] = []  
        missing: list[str] = []  
  
        seeninput: set[str] = set()  
        for flowername in flowernames:  
            cleanname = self.normalizeflowername(flowername)  
            if cleanname in seeninput:  
                continue  
            seeninput.add(cleanname)  
  
            if cleanname not in flowers:  
                missing.append(cleanname)  
                continue  
  
            owners = registry.setdefault(cleanname, [])  
            if cleanign in owners:  
                alreadyowned.append(cleanname)  
                continue  
  
            owners.append(cleanign)  
            registry[cleanname] = self.normalizeownerlist(owners)  
            added.append(cleanname)  
  
        self.saveregistry(registry)  
  
        return {  
            "added": sorted(added, key=str.casefold),  
            "alreadyowned": sorted(alreadyowned, key=str.casefold),  
            "missing": sorted(missing, key=str.casefold),  
        }  
  
    def unclaimplayerfromallflowers(self, ign: str) -> list[str]:  
        cleanign = self.normalizeign(ign)  
        registry = self.loadregistry()  
        changedflowers: list[str] = []  
  
        for flowername, owners in registry.items():  
            if cleanign in owners:  
                registry[flowername] = [owner for owner in owners if owner != cleanign]  
                changedflowers.append(flowername)  
  
        self.saveregistry(registry)  
        return sorted(changedflowers, key=str.casefold)  
  
    def getflowerowners(self, flowername: str) -> list[str] | None:  
        cleanname = self.normalizeflowername(flowername)  
        flowers = self.loadflowers()  
        if cleanname not in flowers:  
            return None  
        registry = self.loadregistry()  
        return registry.get(cleanname, [])  
  
    def getallregisteredigns(self) -> list[str]:  
        players = self.loadplayers()  
        return sorted(set(players.values()), key=str.casefold)  
  
    def flowerexists(self, flowername: str) -> bool:  
        cleanname = self.normalizeflowername(flowername)  
        flowers = self.loadflowers()  
        return cleanname in flowers  
  
    def getrarity(self, flowername: str) -> str | None:  
        cleanname = self.normalizeflowername(flowername)  
        flowers = self.loadflowers()  
        return flowers.get(cleanname)  
  
    def getfullregistry(self) -> dict[str, dict[str, Any]]:  
        flowers = self.loadflowers()  
        registry = self.loadregistry()  
        combined: dict[str, dict[str, Any]] = {}  
  
        for flowername in sorted(flowers.keys(), key=str.casefold):  
            combined[flowername] = {  
                "rarity": flowers[flowername],  
                "owners": registry.get(flowername, []),  
            }  
  
        return combined  
  
    def importregistrydata(self, importedflowers: dict[str, str], importedregistry: dict[str, list[str]]) -> None:  
        normalizedflowers: dict[str, str] = {}  
        normalizedregistry: dict[str, list[str]] = {}  
  
        for flowername, rarity in importedflowers.items():  
            cleanname = self.normalizeflowername(flowername)  
            normalizedflowers[cleanname] = self.normalizerarity(rarity)  
  
        for flowername, owners in importedregistry.items():  
            cleanname = self.normalizeflowername(flowername)  
            normalizedregistry[cleanname] = self.normalizeownerlist(owners)  
  
        for flowername in normalizedflowers:  
            normalizedregistry.setdefault(flowername, [])  
  
        self.saveflowers(normalizedflowers)  
        self.saveregistry(normalizedregistry)  
  
    def setregistrymessageids(self, messageids: list[int | str]) -> None:  
        config = self.loadconfig()  
        config["registrymessageids"] = self.normalizemessageids(messageids)  
        self.saveconfig(config)  
  
    def sortdictalphabetically(self, data: dict[str, Any]) -> dict[str, Any]:  
        return dict(sorted(data.items(), key=lambda item: item[0].casefold()))  
  
    @staticmethod  
    def normalizeign(ign: str) -> str:  
        clean = " ".join(str(ign).strip().split())  
        if not clean:  
            raise ValidationError("IGN cannot be empty.")  
        return clean  
  
    @staticmethod  
    def normalizeflowername(flowername: str) -> str:  
        clean = " ".join(str(flowername).strip().split())  
        if not clean:  
            raise ValidationError("Flower name cannot be empty.")  
        return clean  
  
    @staticmethod  
    def normalizeownerlist(owners: list[Any]) -> list[str]:  
        cleaned: list[str] = []  
        seen: set[str] = set()  
  
        for owner in owners:  
            cleanowner = JSONStorage.normalizeign(str(owner))  
            if cleanowner in seen:  
                continue  
            seen.add(cleanowner)  
            cleaned.append(cleanowner)  
  
        return sorted(cleaned, key=str.casefold)  
  
    @staticmethod  
    def normalizerarity(rarity: str) -> str:  
        value = str(rarity).strip().lower()  
  
        raritymap = {  
            "uncommon": "🔵 Uncommon",  
            "rare": "🟣 Rare",  
            "epic": "🟠 Epic",  
            "legendary": "🔴 Legendary",  
            "🔵 uncommon": "🔵 Uncommon",  
            "🟣 rare": "🟣 Rare",  
            "🟠 epic": "🟠 Epic",  
            "🔴 legendary": "🔴 Legendary",  
        }  
  
        if value not in raritymap:  
            raise ValidationError("Invalid rarity. Allowed: Uncommon, Rare, Epic, Legendary.")  
  
        return raritymap[value]  
  
    def normalizeall(self) -> None:  
        self.saveplayers(self.loadplayers())  
        self.saveflowers(self.loadflowers())  
        self.saveregistry(self.loadregistry())  
        self.saveconfig(self.loadconfig())  
  
    def ensurefile(self, filepath: Path, defaultdata: Any) -> None:  
        if filepath.exists():  
            return  
        filepath.parent.mkdir(parents=True, exist_ok=True)  
        self.writejson(filepath, defaultdata)  
  
    def readjson(self, filepath: Path, defaultdata: Any) -> Any:  
        if not filepath.exists():  
            self.ensurefile(filepath, defaultdata)  
            return defaultdata  
  
        try:  
            with filepath.open("r", encoding="utf-8") as file:  
                content = file.read().strip()  
                if not content:  
                    self.writejson(filepath, defaultdata)  
                    return defaultdata  
                return json.loads(content)  
        except json.JSONDecodeError as exc:  
            raise DatabaseError(f"Invalid JSON in {filepath.name}: {exc}") from exc  
        except OSError as exc:  
            raise DatabaseError(f"Failed to read {filepath.name}: {exc}") from exc  
  
    def writejson(self, filepath: Path, data: Any) -> None:  
        filepath.parent.mkdir(parents=True, exist_ok=True)  
        temppath: Path | None = None  
  
        try:  
            with tempfile.NamedTemporaryFile(  
                mode="w",  
                encoding="utf-8",  
                dir=filepath.parent,  
                delete=False,  
                suffix=".tmp",  
            ) as tmp_file:  
                json.dump(data, tmp_file, ensure_ascii=False, indent=2)  
                tmp_file.write("\n")  
                temppath = Path(tmp_file.name)  
  
            os.replace(temppath, filepath)  
        except OSError as exc:  
            raise DatabaseError(f"Failed to write {filepath.name}: {exc}") from exc  
        finally:  
            if temppath is not None and temppath.exists():  
                try:  
                    temppath.unlink()  
                except OSError:  
                    pass  
  
    @staticmethod  
    def normalizeoptionalint(value: Any) -> int | None:  
        if value in (None, "", 0, "0"):  
            return None  
        try:  
            parsed = int(value)  
        except (TypeError, ValueError) as exc:  
            raise ValidationError("Config channel/role IDs must be integers or null.") from exc  
        return parsed if parsed > 0 else None  
  
    @staticmethod  
    def normalizemessageids(value: Any) -> list[int]:  
        if value is None:  
            return []  
        if not isinstance(value, list):  
            raise ValidationError("registrymessageids must be a list.")  
        normalized: list[int] = []  
        seen: set[int] = set()  
        for item in value:  
            try:  
                messageid = int(item)  
            except (TypeError, ValueError) as exc:  
                raise ValidationError("Each registry message ID must be an integer.") from exc  
            if messageid <= 0 or messageid in seen:  
                continue  
            seen.add(messageid)  
            normalized.append(messageid)  
        return normalized  
