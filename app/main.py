from fastapi import FastAPI, Security, HTTPException, Depends
import tinytuya
from pathlib import Path
import json
from tuyadevice import TuyaDevice
import ipaddress
from fastapi.security.api_key import APIKey
import logging
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="api_key", auto_error=False)

snapshot = False


def generate_api_key(count):
    import random
    import string

    return "".join(random.choices(string.ascii_letters + string.digits, k=count))


def save_apikey(api_key):
    """Saves api key to ./config/config.json. If the file exists, the key is added,
    updated or the file is created."""
    configjson = Path("./config/config.json")
    if configjson.exists():
        try:
            with open(configjson) as f:
                configdict = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(
                "save_apikey: Invalid JSON while loading existing ./config/config.json"
            )
            logger.error(f"{e.doc}: line:{e.lineno}, column:{e.colno}, message:{e.msg}")
            return False
        configdict["api_key"] = api_key
    else:
        configdict = {"api_key": api_key}
    with open(configjson, "w") as f:
        json.dump(configdict, f, indent=1)
    return True


def load_apikey():
    """Attempts to load API key from ./config/config.json, or generates and saves new
     key"""
    def gen_save_key():
        key = generate_api_key(32)
        save_apikey(key)
        logger.info(f"API Key Generated: {key}")
        return key

    configjson = Path("./config/config.json")
    if configjson.exists():
        try:
            with open(configjson) as f:
                configdict = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(
                "load_apikey: Invalid JSON while loading existing ./config/config.json"
            )
            logger.error(f"{e.doc}: line:{e.lineno}, column:{e.colno}, message:{e.msg}")
            return ""
        if "api_key" in configdict:
            return configdict["api_key"]
        else:
            logger.warning("API Key not found in ./config/config.json, generating new")
            gen_save_key()
    else:
        gen_save_key()


def is_valid_ip(ip_address):
    try:
        _ = ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False


def load_devices():
    global snapshot
    snapshotjson = Path("./config/snapshot.json")
    if snapshotjson.exists():
        with open(snapshotjson) as f:
            try:
                devicesdict = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Snapshot loading failed. {e.doc}, line: {e.lineno}, column: "
                    f"{e.colno}, Error: {e.msg}"
                )
                return {}
            devices = devicesdict["devices"]
            snapshot = True
        logger.info(f"Loaded {len(devicesdict)} devices from snapshot.json")
        return devices
    else:
        devicesjson = Path("./config/devices.json")
        if devicesjson.exists():
            with open("./config/devices.json") as f:
                try:
                    devicesdict = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Devices loading failed. {e.doc}, line: {e.lineno}, "
                        f"column: {e.colno}, Error: {e.msg}"
                    )
                    return {}
            logger.info(f"Loaded {len(devicesdict)} devices from devices.json")
            return devicesdict
        else:
            logger.error("No devices.json or snapshot.json found. Please read README.md.")
            return {}


def load_names():
    with open("./config/names.json") as f:
        try:
            names = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(
                f"Names loading failed. {e.doc}, line: {e.lineno}, column: {e.colno}, "
                f"Error: {e.msg}"
            )
            return {}
        if not snapshot:
            for name in names:
                if "ip" not in name:
                    logger.error(
                        "names.json does not appear to contain an ip key and "
                        "snapshot.json does not exist."
                    )
                    return {}
                if not is_valid_ip(name["ip"]):
                    logger.error(
                        f"{name['name']} does not have a valid ip address specified in "
                        f"the ip key. It is currently: {name['ip']}"
                    )
                    return {}
    logger.info(f"Loaded {len(names)} names from names.json")
    return names


def create_tuya_devices():
    _tuyadevices = []
    _devices = load_devices()
    if not _devices:
        return []
    _names = load_names()
    if not _names:
        return []

    for name in _names:
        for device in _devices:
            if name["name"] == device["name"]:
                if "ip" in device:
                    tuyadevice = TuyaDevice(
                        device["name"],
                        device["id"],
                        device["ip"],
                        device["key"],
                        float(device["ver"]) if device["ver"] != "" else 3.1,
                    )
                else:
                    tuyadevice = TuyaDevice(
                        device["name"], device["id"], name["ip"], device["key"], "3.1"
                    )  # Consider adding protocol version key to names.json
                _tuyadevices.append(tuyadevice)
    logger.info(f"Processed {len(_tuyadevices)} controllable devices")
    return _tuyadevices


api_key = load_apikey()
if not api_key:
    logger.error("Unable to parse ./config/config.json for the API key.")
    exit(1)

tuyadevices = create_tuya_devices()
if not tuyadevices:
    logger.error("Unable to create tuya device objects.")
    exit(1)

app = FastAPI()


def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == api_key:
        return api_key_header
    else:
        logger.error("Could not validate API key")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
        )


def get_device(name):
    for device in tuyadevices:
        if device.name == name:
            return device


@app.get("/")
def index():
    return tuyadevices


@app.get("/status/{name}")
def status(name):
    d = get_device(name)
    outletdevice = tinytuya.OutletDevice(d.device_id, d.address, d.key)
    outletdevice.set_version(d.version)  # Must be float or you get 905
    data = outletdevice.status()
    if "Error" in data:
        logger.error(f"Error accessing device {name}: {data}")
        return f"{data['Err']}: {data['Error']}"
    else:
        logger.info(f"Device control Status {name}: Status: {data['dps']['1']}")
        if data["dps"]["1"]:
            return {"status": "on"}
        else:
            return {"status": "off"}


@app.put("/off/{name}")
def off(name, api_key: APIKey = Depends(get_api_key)):
    d = get_device(name)
    outletdevice = tinytuya.OutletDevice(d.device_id, d.address, d.key)
    outletdevice.set_version(d.version)  # Must be float or you get 905
    data = outletdevice.turn_off()
    if "Error" in data:
        logger.error(f"Error accessing device {name}: {data}")
        return f"{data['Err']}: {data['Error']}"
    else:
        logger.info(f"Device control Off {name}: Status: {data['dps']['1']}")
        if data["dps"]["1"]:
            return {"status": "on"}
        else:
            return {"status": "off"}


@app.put("/on/{name}")
def on(name, api_key: APIKey = Depends(get_api_key)):
    d = get_device(name)
    outletdevice = tinytuya.OutletDevice(d.device_id, d.address, d.key)
    outletdevice.set_version(d.version)  # Must be float or you get 905
    data = outletdevice.turn_on()
    if "Error" in data:
        logger.error(f"Error accessing device {name}: {data}")
        return f"{data['Err']}: {data['Error']}"
    else:
        logger.info(f"Device control On {name}: Status: {data['dps']['1']}")
        if data["dps"]["1"]:
            return {"status": "on"}
        else:
            return {"status": "off"}
