# Hay Day v1.5.42

First ever opensource HayDay private server! For version 1.5.42.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
[![Download IPA](https://img.shields.io/badge/Download-IPA-blue?logo=apple&logoColor=white)](https://bluetalktg.pythonanywhere.com/testflight/Hay%20Day%201.5.42%20%28772.14583.4279%29.ipa)

<img width="1024" height="768" alt="IMG_0058" src="https://github.com/user-attachments/assets/b08cafa0-1499-457d-ab98-f3d18c186ed4" />


## What works

- Home screen
- Visiting the AI neighbour in friend list (Greg)

The rest isn't implemented yet!

## Setup

1. Install the requirements:
 `pip install -r requirements.txt`.
2. Edit `config.json`, set `Host` to the **LAN IP of your machine running the server**.
3. Patch the client and install it on your device (ARMv7, iOS only).
4. Run `python3 Main.py`.

## Patching the client

First, download the IPA from [here](https://bluetalktg.pythonanywhere.com/testflight/Hay%20Day%201.5.42%20%28772.14583.4279%29.ipa)

The client asks `http://<host>:8080/env_settings` where the game server is. Three hard coded URLs point at HayDay's domains. `patcher.py` rewrites them:

Replace `192.168.x.x` with your IP address.

```bash
python3 patcher.py "Hay Day 1.5.42 (772.14583.4279).ipa" haydaypatched.ipa 192.168.x.x
```

The host must be at most 24 characters including the port. Once you're done install the .IPA using something like Sideloadly on a **jailbroken** device.


## Feel free to use this as base for your own projects :3 


### Core based on [Solaree/CoC-1.7.0](https://github.com/Solaree/CoC-1.7.0)
