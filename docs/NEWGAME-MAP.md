# NIGHTJAR — New Fortress Map (design blueprint)

The plan for the **new whole map**: a fresh topology + layouts for *Halcyon Reach*, the
Concord sea-fortress KESTREL infiltrates to destroy the AI siege-walker **AZRAEL**. This is
the design artifact; the actual data is authored with **`tools/mgmap.py`** (see
[map codec](#7-encoding-workflow)) and validated by a green build + `graph` reachability.

Story source: [NEWGAME-PLOT.md](NEWGAME-PLOT.md) + [NEWGAME-BEATSHEET.md](NEWGAME-BEATSHEET.md).
World mechanics: [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md). Items:
[04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md).

---

## 1. The two-layer room model (design around this)

The engine splits rooms into two populations — design the fortress as **both**:

* **Open grid — rooms 0–121.** The navigable screens wired N/S/W/E by
  `data/roomsconnections.asm`. Enemies and bosses live here; **no static items**. This is
  the floor plan the player walks.
* **Door rooms — rooms 122–217.** Small interiors entered **through a door** (`DEST_ROOM`).
  **Every pickup item lives here** (`idxRoomItemsIdx[room−122]`). One open-grid room can have
  several doors into several door rooms (item caches, cells, vaults).

So a "room with the Gas Mask" is really: an open-grid room + a door into a door-room that
holds the item.

---

## 2. Engine-locked room semantics (cannot move without engine changes)

These room IDs carry hardcoded behavior. **Keep them in role; re-theme/re-layout freely.**

| Room(s) | Locked behavior | Source |
|---------|-----------------|--------|
| 121 | **Start / insertion point** | `SaveStatRooms`, start logic |
| 240–250 | **Elevators** (no enemies; shaft physics) | `data/elevatorrooms.asm`, `cp 240` |
| ≥224 | **Ladder climb** rooms (mode 6/7; no pause/radio) | `Banks0123.asm:12114` |
| 117 | **Roof parachute jump** (mode 4) | `DoorsRoom_117` render 14h |
| 204 | Parachute **landing** brick room (mode 5/air) | special movement |
| 122–217 | **Door-room item layer** (≥218 never loads items) | `logic/addroomitems.asm` |
| 0–121 | Open grid; **isolated/lorry** rooms disable alarm + allow box transport | `IsolatedRoom` |
| — | **Bosses are ACTORS** (`data/actorsinrooms.asm`) → freely relocatable to any open room | codec `actor_slots`/`actor_blocks` |

Tilesets are per-room (`data/roomtileset.asm`); 0=Building,1=Basem/Desert,2=Roof,
3=Elevator/Ladder,4=Lorry/Isolated,5=HindD,6=MetalGear,7=Ending.

---

## 3. Halcyon Reach — zones (re-theme of the engine's zone skeleton)

Mapping NIGHTJAR onto the engine's existing zone structure (from `SaveStatRooms`), so locked
IDs keep their role. Re-wire connections *within/between* these to make the new shape.

| # | NIGHTJAR zone | Engine open-grid rooms | Door rooms (items) | Elevators | Tileset |
|---|---------------|------------------------|--------------------|-----------|---------|
| Z1 | **Dock & Outer Platform** (insertion) | 121, 0–15 | 122–137 | 240,241 | Building |
| Z2 | **Comms Spire & Helipad** (DOZER gunship, parachute) | 16–63, 117 | 138–163 | 241,242 | Building/Roof/HindD |
| Z3 | **Sea Causeway** (GOLIATH walker-tank, uniform gate) | 64–72, 204 | 164–168 | — | Lorry/Isolated |
| Z4 | **Reactor Hall** (BREAKER, PYRE, Arbiters; dark ducts) | 73–110 | 169–203 | 243–246 | Building/Basem |
| Z5 | **Flooded Channel** (rebreather, venom drones) | 102–110, 211–212 | — | — | Basem/Desert |
| Z6 | **AZRAEL Bay & WARDEN** (MAGPIE, AZRAEL, escape) | 111–119 | 187–200 | 247,250 | MetalGear/Building |
|  | **Escape ladders** (post-AZRAEL) | 142–154, 224+ | — | — | Elevator/Ladder |
|  | **Dark maze / cells** (compass + lamp) | 122–141→220+ | — | — | Basem |

Boss re-skin (actor swaps, all relocatable): MACH_GUN_KID→**HOWLER**, HIND_D→**DOZER**,
TANK→**GOLIATH**, SHOT_GUNNER→**BREAKER**, FIRE_TROOPER→**PYRE**, ARNOLD→**Arbiters**,
COWARD_DUCK→**MAGPIE**, BIG_BOSS→**WARDEN**, METAL_GEAR→**AZRAEL**.

---

## 4. Critical path & gating (the spine the graph must guarantee)

Start 121 → **Z1** grab Access Card I + Hand Gun/SMG, beat **HOWLER** → **Z2** Missile kills
the power trunk + **DOZER** on the helipad; get Gas Mask / Kinetic Suit / Parachute → **Z3**
Mines kill **GOLIATH**; wear the **Concord Uniform** to pass the causeway checkpoint → **Z4**
**Compass + Lamp** for the dark ducts; **BREAKER**, **PYRE**, the unkillable **Arbiters**;
Access Cards V–VI → **Z5** **Rebreather** through the flooded channel (venom drones need
Antivenom) → **Z6** Master Card from **MAGPIE**; ignore WARDEN's "stand down" trap; Breaching
Charges destroy **AZRAEL**; confront **WARDEN**; **Pulse Stim** stretches the self-destruct
timer; escape via the ladders → ending.

Gating keys (unchanged engine logic, re-themed): Cards I–VIII / Master Card (door logic
2–9), Uniform (`ChkDesertDoorBuild2`), Compass (`ChkCompassDoor`/SAINT), Breaching Charge
(`ChkBasementWall`), punch-walls (`ChkPrisonWalls`), Big-Boss/escape door
(`ChkBigBossDoor`).

---

## 5. Item placement (door rooms 122–217)

Set each item by writing the **door room's** slot (`item` field for room 122+ in `map.json`).
Keep one-tool-per-boss: Missile→DOZER/power, Mines→GOLIATH, Breaching Charge→AZRAEL, Grenade
→ (mid boss), Antivenom→venom drones. Cards gate their zone's doors. See
[04-OBJECTS-INDEX §3](04-OBJECTS-INDEX.md) for the current room→item table to rework.

---

## 6. Checkpoints

Update the 31 `SaveStatRooms` `[room, prevRoom]` pairs to fire on the new zone borders
(each elevator landing, each zone transition, each boss room entry). Edit the top-level
`checkpoints` array in `map.json`. Keep exactly 31 pairs (engine hardcodes the count).

---

## 7. Encoding workflow

```
python tools/mgmap.py export                 # rooms+conns+tilesets+doors+items+actors+checkpoints -> tools/map.json
#   edit map.json: per-room grid/conn/tileset/item/doors; top-level actor_slots/actor_blocks/checkpoints
python tools/mgmap.py import --regen          # rebuilds idxDoors/idxActorsRooms; allows new doors/enemies
"C:/DevMSX/sjasm039j/sjasm.exe" MetalGear.asm MetalGear.rom    # must be 131072 / 0 errors
python tools/mgmap.py graph                   # verify reachability from 121 (0 unreachable expected)
python tools/mgmap.py selftest                # codec integrity
```

Round-trip is **byte-exact** (validated: no-op `import` and `import --regen` both reproduce
the baseline ROM). Adding doors with new DoorIDs ≥156 needs extending `iddoorslogic`.

---

## 8. First milestone (proposed)

Author **Z1 (Dock & Outer Platform)** end-to-end as the vertical slice: re-wire rooms
121,0–15 into the dock layout, draw their metatile grids, place Access Card I + Hand Gun in
door rooms 122–137, set HOWLER's actor room, and add the Z1→Z2 checkpoint pair. Build green +
`graph` clean, verify in openMSX, then template the remaining zones from it.
