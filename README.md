
![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/teejo75/mtghs?sort=semver)
![GitHub](https://img.shields.io/github/license/teejo75/mtghs)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/teejo75/mtghs/docker-publish.yml)

# Description
## Moonraker Tuya Generic HTTP Service
This is a simple service to be used with the [Moonraker](https://github.com/Arksine/moonraker) API server for Klipper 3D printing. 
It provides an API for the Moonraker Generic HTTP power plugin to control Tuya/Smart Life smart wifi electrical outlets locally.

Tuya do not make it easy to control your devices locally, and you will have to jump through a few hoops to get this running.

This service makes use of the [tinytuya](https://github.com/jasonacox/tinytuya) python library to interact with your devices.
You will need to use some of their guides in order to get required information for your devices.

This service is intended to run as a docker container (easiest), but you can also run it directly by cloning the repository if you prefer.
I recommend setting up a venv. The command to launch the service is `uvicorn main:app --host 0.0.0.0`.

## Initial Setup
I strongly recommend assigning static IP addresses for each device that you want to control with this service. You can do this via static DHCP mapping on your DHCP server or router.

Ensure that you add your devices to either the Tuya App or the Smart Life App and that you have a Tuya account.

Follow Step 3 of the section "Setup Wizard - Getting Local Keys" in [this document](https://github.com/jasonacox/tinytuya/blob/master/README.md#setup-wizard---getting-local-keys) to create a Tuya IoT developer account.
This account is different to your Tuya/Smart Life App account.
Link your Tuya/Smart Life App account into your Tuya Iot cloud project.
Search [this document](https://developer.tuya.com/en/docs/iot/oem-app-data-center-distributed?id=Kafi0ku9l07qb) for your country to determine what data center your account is associated with.
 
You will need the following information from the developer account:
  * Access ID/Client ID
  * Access Secret/Client Secret
  * The location of the data center for your account and project

From the Devices tab of your cloud project, copy one of the device IDs for one of your devices, it doesn't matter which one.
If you don't see any Devices, check that you have linked your Tuya/Smart Life App account.

Run the wizard command from the directory where you will put the `docker-compose.yml`, or specify the full path instead of `./config`:
`docker run --rm -it -v ./config:/app/config ghcr.io/teejo75/mtghs /app/tinytuya.sh wizard` and enter the details from your Tuya IoT project. 
_The `tinytuya.sh` script is just a shortcut to running `python -m tinytuya` so all options it supports are available. 
Run it with `-h` for more information._

This will create `devices.json` based on your devices listed in your Tuya/Smart Life App.
I strongly recommend that you also allow the wizard to poll all the devices. This will create `snapshot.json` that contains more information than `devices.json`
If you add new devices, or remove and re-add devices to your Tuya/Smart Life App, you will need to re-run the wizard command.

If the wizard is unable to find any devices on your network, add the parameter `-force 192.168.0.0/24` or whatever your local network subnet is to the wizard command. 

Once the `devices.json` exists in the config directory, create `names.json` by copying `names-example.json` and editing as required. 
If `snapshot.json` exists, the ip key in `names.json` will be ignored, so you can leave it as a blank string or remove it entirely.
Add as many entries as you require. Only the devices listed in names.json will be controllable.

The service requires `names.json` and `devices.json`, however if `snapshot.json` exists, `devices.json` will be ignored.

On start up, the service will generate an api key and save it to `config.json`. Use the api key within the moonraker config to query this service.
To generate a new key, either edit `config.json` and input your own key, then restart the service, or delete `config.json` then restart the service, and a new key will be generated.
Check the console logs `docker compose logs` or get the new key from `config.json`.

Use the following simple `docker-compose.yml` to bring the service up.

```yaml
version: "3.9"
services:
  mtghs:
    image: ghcr.io/teejo75/mtghs:latest
    ports:
      - 8000:80
    volumes:
      - ./config:/app/config
    restart: unless-stopped
```
To bring the service up, run `docker compose up`. This will bring the service up with the logs in the console. Verify that the service is starting and not throwing an error.
If you're getting an error, it's probably because one of `names.json`, `devices.json`, `snapshot.json` is missing.
If you're happy that it starts up properly, kill it with ctrl+c then bring it up in the background with `docker compose up -d`.
_Note: If you see duplicated log entries, it's because of the number of workers. Two workers start by default, so you will see two log entries initially._

If you call the service URL directly, `http://<service>:8000/` you will get a json doc with the available devices. 

## Moonraker Config
Add the generated api key to `moonraker.secrets`, this file lives in the moonraker data_path. If you don't know where this is, check the top of `moonraker.log`.
Be sure to add a `[secrets]` section to the `moonraker.conf` file so that the secrets file will be loaded.

`moonraker.secrets`:
```
[mtghs]
api_key: <your generated key goes here>
```

`moonraker.conf`:
```
#  Add as many sections as needed for the devices you want to control.
[power tuyaoutlet]
type: http
#  In the below urls, <name> should be replaced with your device name per names.json, devices.json/snapshot.json
#  <service> should be replaced with the hostname and port of the service.
on_url: http://<service>/on/<name>
off_url: http://<service>/off/<name>
status_url: http://<service>/status/<name>
request_template:
    {% if command in ["on", "off"] %}
        {% do http_request.set_method("PUT") %}
        {% do http_request.add_header("api_key", "%s" % secrets.mtghs.api_key) %}
        {% do http_request.set_body({}) %}
    {% endif %}
    {% do http_request.send() %}
response_template:
  {% set resp = http_request.last_response().json() %}
  {resp["status"]}
# This enables a power button in mainsail.
bound_services: klipper  # You can remove this line for non printer power sources where you don't need Klipper to restart.
```

### Building your own image
Clone the repository: `git clone https://github.com/teejo75/mtghs.git`.
Inside the cloned respository, run `docker build -t teejo75/mtghs .`
