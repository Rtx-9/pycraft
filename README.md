# PyCraft

A Minecraft-style voxel sandbox written in Python (Panda3D + NumPy), in one file: `pycraft.py`.
Procedural terrain with biomes, caves, villages and dungeons; survival and creative; mobs, mounts and fishing;
weather, smooth lighting and generated music; the **Sillyland** dimension with its boss; and multiplayer with
a headless dedicated server. All textures and sounds are generated in code, so there are no asset files.

![textures](textures_preview.png)

## Play

| OS | First time | Start |
|---|---|---|
| Windows | install Python 3.10+ from python.org | double-click `run.bat` (or `py pycraft.py`) |
| Linux | see below | `./run.sh` |
| macOS | `brew install python` | `./run.sh` |

`run.sh` / `run.bat` create a local `.venv` and install `panda3d` + `numpy` on the first run.
Manual install: `pip install -r requirements.txt` then `python pycraft.py`.

### Linux

```bash
# Debian / Ubuntu / Mint / Pop!_OS
sudo apt install python3 python3-venv python3-pip libgl1 libopenal1
# Fedora
sudo dnf install python3 python3-pip mesa-libGL openal-soft
# Arch / Manjaro
sudo pacman -S python python-pip mesa openal

./run.sh
```

Works on X11 and on Wayland (through XWayland). Saves and settings live in `~/.pycraft/`.

## Controls

WASD move · Space jump (double-tap in creative = fly) · Ctrl sprint · Shift sneak/dismount · mouse look ·
LMB break/attack · RMB place/use/eat/ride · MMB pick block · 1-9 / wheel hotbar · E inventory · Q drop ·
T chat · `/` command · M minimap · G survival/creative · F fly · F3 debug · F4 weather · F11 fullscreen · Esc pause.
Press **Help & Guides** in the main menu for everything else.

## Multiplayer

**Host from the game:** load a world, Esc, **Open to LAN / Host**. PyCraft asks your router to open TCP 25565 (UPnP)
and prints your **public address** in chat for friends on other networks. If your router refuses, forward TCP 25565
to your PC manually. Set a password under Multiplayer > Password first if the server is public.

**Join:** main menu, Multiplayer, enter name + `host:port` (+ password), Join.

Shared: blocks, physics, chests, time, weather, chat, PvP. Mobs and dropped items are per player for now,
and Sillyland is single-player only.

## Dedicated server (Linux, headless)

No display, GPU or sound card needed, so it runs on a VPS or a Raspberry Pi-class box.

```bash
git clone <this repo> pycraft && cd pycraft
./server.sh --password hunter2              # first run sets up .venv
```

| Option | Default | |
|---|---|---|
| `--port` | 25565 | TCP port |
| `--world` | `~/.pycraft/server_world.sav` | world file; a singleplayer `world.sav` works too (copy it over) |
| `--seed` | random | seed for a new world |
| `--password` | none (or `$PYCRAFT_PASSWORD`) | required to join |
| `--max-players` | 8 | |
| `--autosave` | 120 | seconds between saves |
| `--no-upnp` | off | don't ask the router to open the port (use on a VPS) |

Console commands: `help`, `list`, `say <msg>`, `kick <name>`, `time day|night|<hour>`,
`weather clear|rain|thunder`, `save`, `stop`. Ctrl+C or SIGTERM saves and stops cleanly.

Open the port in the firewall, e.g. `sudo ufw allow 25565/tcp`, and run it 24/7 with systemd using
`pycraft-server.service` (instructions are at the top of that file). A server world file can be opened in the game
by copying it to `~/.pycraft/world.sav`.

## Discord status (optional)

`pip install pypresence`, create an application at discord.com/developers/applications, and put its ID in
`~/.pycraft/settings.json` as `"discord_app_id": "..."`.
