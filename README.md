# Hay Day v1.5.42

First ever open source Hay Day private server! For version 1.5.42.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
[![Download IPA](https://img.shields.io/badge/Download-IPA-blue?logo=apple&logoColor=white)](https://bluetalktg.pythonanywhere.com/testflight/Hay%20Day%201.5.42%20%28772.14583.4279%29.ipa)

<img width="1024" height="768" alt="IMG_0058" src="https://github.com/user-attachments/assets/b08cafa0-1499-457d-ab98-f3d18c186ed4" />


## What works

- Home screen
- Visiting the AI neighbour in friend list (Greg)
- **Per-player accounts** via SQLite (`hayday.db`, OOP `Account` model) — every
  device gets its own row keyed by `(high_id, low_id)` and its own farm
- Mutable farm state (`Logic/Home.py`), stored as one JSON blob per account
  in the database, with a human readable export in `JSON/`
- Farm **layout** comes from `HomeFile` in `config.json` (`JSON/home.json` by
  default) and seeds every *new* account; progress is layered on top from the
  account's saved blob (or `JSON/home_state.json` for the configured account)
- Logging: colored console + rotating `logs/hayday.log` and `logs/errors.log` (configure `LogLevel`/`LogColor` in `config.json`)
- HTTP `/status` endpoint for server/account info
- Full message scaffold: 68 client/server message modules, dynamic `MessageFactory`
- Full command scaffold: 98 `Logic*Command` handlers, dynamic `CommandFactory`
- `EndClientTurn` parses tick/checksum and dispatches commands, then persists state

### Game logic implemented (first wave)

| System | Commands |
| --- | --- |
| Farming | plant, harvest (+gain/over), boost, instant-grow, fruit/bush collect |
| Production | start, collect, instant-complete |
| Shop | buy seed, buy object, sell object |
| Animals | buy, feed, collect |
| Orders | complete, discard |
| Economy | achievements, level-up bonus, wheel spin, mine, expansion, building upgrade |
| Roadside shop | list item on stand, claim/sold |
| Utility | update timers, debug, speed-ups (order/boat/ad), tutorial complete |

Everything else falls back to a generic handler that logs the command id,
decoded args and raw payload hex so formats can be filled in from play logs.

### Real game data

The 90 encrypted CSVs inside `haydaypatched_extracted/Payload/Hay Day.app/res/data/`
are decoded with [supercell-resource-decoder](https://github.com/proydakov/supercell-resource-decoder)
via `decode_data.py` into plain CSVs in `data/`. `Logic/GameData.py`
loads those tables lazily and resolves the client's global ids
(`table_id * 100000 + instance`) so commands use the real balance values:

- crop grow times, harvest yields, seed prices and unlock levels (`fields.csv`)
- the full 100 level exp curve and level-up rewards (`exp_levels.csv`)
- production times, recipe requirements and collect exp (`*_goods.csv`)
- animal feed/products (`animals.csv`, `animal_feed.csv`, `animal_goods.csv`)
- object/animal prices with `PriceIncrease` scaling, purchase exp and unlock levels
- order reward windows, speed-up prices, achievement and mystery-box rewards
- boat orders/crates, visitor (boy) hire prices, movie-ticket exp/diamonds,
  mine ores and probabilities, fruit-tree tools and instant costs,
  pet food from `pet_habitats.csv`, building repair exp and roadside-stand
  diamond prices from `game_config.csv`
- every remaining generic action now derives its prices/rewards from the CSVs
  instead of hardcoded numbers; all 96 command ids and field layouts come from
  `command_formats.json`

When a CSV row is missing (or an older save has no server-side items yet) the
handlers fall back to their previous hardcoded values and log the mismatch,
so older saves keep working.

> Note: buildings start with a `BrokenParts` list in the default farm layout,
> which makes the client render the broken/grey version (e.g. the unfinished
> house). `LogicFixBuildingCommand` clears one part per command and removes the
> field once every part is repaired, switching to the finished coloured
> export. `LogicInstantCompleteBuildingCommand` clears them all at once.

> Note: `Objects` entries must carry a real global data id. A `-1` /
> `4294967295` id makes the client throw `Unable to load object -1 class:0
> instance:-1` while loading home. `LogicBuyObjectCommand` now ignores unknown
> data ids, stores the data id (not the per-session object id) and converts
> the client's 1/512 accurate coordinates into tile coordinates;
> `Logic/Home.py` filters invalid objects on load.

> Note: saved JSON must never contain duplicate keys. The client's
> `LogicJSONObject::put()` throws on them (e.g. `already contains key
> 4294967295`). `Logic/Inventory.py` now keeps only string keys and
> `Logic/Home.py` stringifies all keys before serializing.

> Note: an object id is `table_id * 100000 + instance`, and the client splits
> it back as `class = id / 100000`, `instance = id % 100000`. Dropping a zero
> turns `roadside_shop` (`35 * 100000 = 3500000`) into `350000`, which decodes
> to class 3 instance 50000 and aborts the app on the next home load with
> `Unable to load object 350000 class:3 instance:50000`
> (`LogicGameObjectManager::loadObjectsFromJSON` -> `Debugger::error`).
> `LogicBuyMarketStandCommand` writes `3500000`, and `Logic/Home.py` now
> verifies every `Objects` id against the decoded CSV tables — upgrading the
> legacy id when possible and dropping ids the client could not load.

> Notes about the avatar bit lists (`Logic/ClientAvatar.py`):
> - the patched client crashes on the next home load if **all** tutorial bits
>   are set (it switches to a post-tutorial state the farm was never set up
>   for), so the last tutorial bit is always left clear and
>   `LogicTutorialCompletedCommand` never flips the global "tutorial finished"
>   flag from step progress.
> - `LogicInventory::isUnlocked()` reads the other bit lists, not just
>   `UnlockLevel`. They are filled from rows whose `UnlockLevel` is at most
>   the current level. Leaving them empty makes the level-8 spin wheel build
>   an empty prize list and throw `LogicDataRandomizer constructed with zero
>   sized list`.

To regenerate the decoded tables after changing the IPA:

```bash
python decode_data.py
```

### Binary command formats

The command wire format is baked into the ARMv7 executable, not into a CSV.
`decode_macho.py` parses the Mach-O symbol table, disassembles every
`Logic*Command::createAndDecode` with capstone and reads the `ByteStream::readXxx`
calls to recover the exact field order, plus the literal returned by every
`getCommandType()`. The result is `Logic/command_formats.json` (96 commands).

`LogicCommand.__init_subclass__` applies those layouts to every registered
handler at import time, so a wrong guessed field count can no longer desync
`EndClientTurn`. Regenerate after replacing the IPA with:

```bash
python decode_macho.py
```

## Player data

Everything a player owns lives in `hayday.db`:

| table | keyed by | contents |
| --- | --- | --- |
| `accounts` | `(high_id, low_id)` | name, pass token, diamonds, cash, exp, tutorial flag, `stats` JSON, `created_at`/`last_seen` |
| `home_states` | `(high_id, low_id)` | the whole farm as one JSON blob (`updated_at`) |
| `home_objects` | `(high_id, low_id, object_index)` | placed object data id, runtime id, tile `X/Y`, 1/512-tile `accurate_x/accurate_y`, mirror flag and complete object JSON |
| `home_inventory` | `(high_id, low_id, item_id)` | inventory amount per item |
| `home_sections` | `(high_id, low_id, section)` | every other home section as queryable JSON |
| `schema_version` | – | which migrations have been applied |

How it behaves:

- **One connection per process** guarded by a re-entrant lock — every client
  thread and the HTTP server share it (`check_same_thread=False` alone was
  racy). `PRAGMA journal_mode=WAL` + `busy_timeout=5000` keep reads and writes
  from blocking each other.
- **Migrations, not ad-hoc ALTERs.** Old databases are upgraded in order
  (`Utils/Database.py` -> `MIGRATIONS`); adding a column means adding a
  function to that tuple. Existing rows are preserved.
- **Batched writes.** `state.save()` only marks a state dirty (a single turn
  used to serialize the farm and commit two or three times). `Main` flushes
  once per packet, again on disconnect, and at exit
  (`atexit` -> `GameState.shutdown`), so a turn costs exactly one write.
  Account and farm are written in the same transaction, and only when their
  own dirty flag is set: an exp/cash reward does not re-serialize the farm.
  If a write fails the flags stay set and the next packet retries it.
- **One way to change resources.** Diamonds, cash, level and exp are mutated
  through `GameState.account_set()`, `account_delta()`, `account_spend()` and
  `account_stat()`. Gameplay code never calls `account.save()` mid-turn. The
  avatar sent to the client reads those values from the live `Account`
  object, so the client, `/status` and the database always agree.
  `Diamonds`/`Cash`/`ExpLevel`/`ExpPoints` in `config.json` are **seed values
  for brand-new accounts only** — editing them does not rewrite an existing
  player (use `/status` to see the live values).
- **The blob and normalized rows are written atomically.**
  `JSON/home_state.json` (and
  `JSON/home_state_<high>_<low>.json` for other players) is a read-only
  export you can inspect or hand edit — flip `ExportHomeJson` to `false` to
  switch it off. Exports are written atomically (temp file + `os.replace`) so
  a crash can no longer truncate a save.
- **Object positions are queryable.** Migration 4 projects the blob into
  `home_objects`, `home_inventory` and `home_sections` in the same
  transaction and reads those normalized rows. Updating `home_objects.X/Y`
  in SQLite is therefore reflected on the next home load rather than being
  overwritten by a stale JSON mirror.
- **Coordinates preserve the Mach-O fixed point.** Home JSON stores tile
  integers, while the client holds `tile * 512`. Move commands add raw
  accurate deltas, and the normalized table keeps the remainder in
  `accurate_x/accurate_y`. Run `python macho_coordinates.py
  --runtime-id <id> --dx <delta> --dy <delta>` to replay the exact path from
  the Mach-O.
- **Backups.** Every start of a non-empty database snapshots it into
  `backups/hayday-<timestamp>.db` and keeps the newest `DbBackups` (default 3),
  after a `PRAGMA quick_check`.
- **Per-player accounts.** `LoginMessage` decodes the client's 64-bit
  `accountId` (`high_id << 32 | low_id`) and resolves that row; the id is
  echoed back in `LoginOkMessage` so the next login lands on the same farm.
  A device with no id yet gets a **new** account on a server that already has
  players (`"AssignNewAccounts": true`), so two phones never overwrite each
  other; set it to `false` to keep the old single-account behaviour where
  every device shares the configured `AccountHighID`/`AccountLowID`.

```json
"AssignNewAccounts": true,   // new devices get their own account row
"ExportHomeJson": true,      // mirror the farm blob to JSON/
"DbBackups": 3               // how many snapshots to keep in backups/
```

## Capturing client packets

Set `CapturePackets` to `true` in `config.json` (default) and restart the
server. Every packet is recorded in plaintext — client packets right after
RC4 decryption, server packets before encryption — as JSONL lines in
`captures/packets_YYYYMMDD.jsonl`:

```json
{"ts": "...", "dir": "C2S", "id": 14102, "len": 41, "version": 0, "hex": "..."}
```

Decode and inspect them offline with:

```bash
python analyze_packets.py --commands        # Logic commands + field values
python analyze_packets.py --id 14102 --last 5 --dump
```

This exposes unknown message ids, wrong command field layouts and malformed
payloads directly from the real player client.

`EndClientTurnMessage` has **no trailing checksum**: the only optional tail is
a dev-build block of tick byte streams (`int32 count`, then `int32 len + bytes`
per stream), parsed by `LogicCommand`-equivalent code in
`EndClientTurnMessage._decode_tick_streams`.

## Architecture

- `Packets/MessageFactory.py` – auto-registers client messages that declare `ID = <packet_id>`
- `Logic/CommandFactory.py` – auto-registers command handlers; `dispatch(type, payload, state)`
- `Logic/GameState.py` – per-account state registry holding `Account` (SQLite) + `Home` (farm blob); `save()` marks it dirty and `flush()` persists it once per packet
- `Logic/Commands/LogicCommand.py` – base class: generic VInt decode, inventory/currency/exp helpers

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


## Credits

- Core based on [Solaree/CoC-1.7.0](https://github.com/Solaree/CoC-1.7.0)
- Game data decoded with [proydakov/supercell-resource-decoder](https://github.com/proydakov/supercell-resource-decoder) — we use it to turn the encrypted CSVs in the IPA into the plain tables in `data/`

## Feel free to use this as base for your own projects :3 
