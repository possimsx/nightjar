# NIGHTJAR — Room-by-Room Beat Sheet (build work order)

This turns the [NEWGAME-PLOT.md](NEWGAME-PLOT.md) story into a **direct edit list for the
`data/` tables**. Each critical-path room below is a work order: which file to touch and what
to put there. It is anchored to the **real engine room IDs** so the room graph, doors, and
triggers already line up — you re-skin in place rather than re-wiring.

Cross-reference while editing: [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md)
(room graph + door system), [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md) (item IDs),
[06-REWORK-GUIDE.md](06-REWORK-GUIDE.md) (how each table is edited).

---

## How to read a room block

```
ROOM nn — <name>            tileset: <current> | conn N/S/W/E: a/b/c/d
ROLE   : what happens here (story)
TILES  : data/rooms.asm > RoomNNN          (background re-skin)
ITEMS  : data/itemsinrooms.asm             (pickups; ID from enum ITEMS)
ACTORS : data/actorsinrooms.asm > ActorsRoomNNN  (enemies/boss; ID from enum ACTORS)
DOORS  : data/doors.asm > DoorsRoomNNN + IdDoorsLogic  (gates)
RADIO  : data/radiocalls.asm[room] + data/texts.asm   (caller → the line to write)
```

* **conn N/S/W/E** is from `data/roomsconnections.asm` (255 = wall). Keep these unless you
  redesign the map.
* **tileset** is the room's current graphics set (`data/roomtileset.asm`). Re-skin the
  *graphics* of that tileset in `gfx/` to change the look of every room that uses it.
* **RADIO lines** are the new script — write them into `data/texts.asm` and point the
  room's `RadioRoom_xxx` entry at the new text ID.

### Re-skin lookup tables (apply globally)

**Actors** (`enum ACTORS` stays numerically identical — only the *sprite/name* changes):

| Engine ID | Was | Now (NIGHTJAR) |
|-----------|-----|----------------|
| `ID_GUARD_SLOW/MEDIUM/FAST` | guards | Concord troopers (light/regular/elite) |
| `ID_SENTINEL` | patrol guard | Concord sentry |
| `ID_DOG` | dog | K-9 drone |
| `ID_CAMERA` | camera | scanner-eye |
| `ID_MACH_GUN_KID` | Machine Gun Kid | **HOWLER** (gun-drone) |
| `ID_HIND_D` | Hind-D | **SHRIKE** (gunship) |
| `ID_SHOT_GUNNER` | Shot Gunner | **BREAKER** (juggernaut) |
| `ID_TANK` | tank | **GOLIATH** (crawler) |
| `ID_BULLDOZER` | bulldozer | **DOZER** (demo rig) |
| `ID_FIRE_TROOPER` | Fire Trooper | **PYRE** |
| `ID_SCORPION` | scorpion | venom drone / scorpion |
| `ID_ARNOLD` | Arnold | **The Arbiters** (invincible) |
| `ID_COWARD_DUCK` | Coward Duck | **MAGPIE** |
| `ID_GREY_FOX` | Grey Fox | **GRAVE** (Cole Marsh) |
| `ID_MADNAR` | Madnar | **Dr. Elias Roth** |
| `ID_FAKE_MADNAR` | fake Madnar | **"Roth" the Double** |
| `ID_ELLEN`/`ID_PRISONER1` | prisoners | hostages (incl. Iris) |
| `ID_METAL_GEAR` | Metal Gear | **AZRAEL** |
| `ID_BIG_BOSS` | Big Boss | **Director Crane / WARDEN** |

**Radio callers** (`enum RADIO`/`FREQUENCIES` unchanged; rename in text):
`BIGBOSS → WARDEN`, `SCHNEIDER → RELAY`, `DIANE → ORACLE`, `JENIFFER → SAINT`.
(Building-2 frequency variants = the same people after the zone change.)

> ⚠️ **Item-room model (corrected 2026-06-20).** Pickups are **not** in the open-grid combat
> rooms named in the beats below — the engine reads `idxRoomItemsIdx[room−122]` and only
> rooms **122–217** can hold items. Each item sits in a small **door room** (122+) entered
> through a door from the open room where the beat happens. So a beat that says "ROOM 16 —
> get the Gas Mask" means: open room 16 has a *door* into room **138**, which contains the
> Gas Mask. See [04-OBJECTS-INDEX.md §3](04-OBJECTS-INDEX.md) for the authoritative
> room→item table (Gas Mask = 138, Antidote = 183, Uniform = 169, Compass = 184, Oxygen =
> 200, …). When wiring the new map, place items by setting the **door room's** item slot,
> not the open room's.

**Items** (`enum ITEMS` unchanged; rename in `data/itemnames.asm`): see the item table in
[NEWGAME-PLOT.md §8](NEWGAME-PLOT.md). Cards 1–8 → Access Cards I–VIII / Master Card,
Uniform → Concord Uniform, Oxygen → Rebreather, Compass → Compass, Flashlight → Lamp,
Gas Mask → Gas Mask, Bomb Suit → Kinetic Suit, Antidote → Antivenom, Antenna → Signal
Booster, Parachute → Parachute, Plastic Bomb → Breaching Charge, Ration → Stim,
Cigarettes → Pulse Stim, Bag → Kit Bag.

---

## ACT I — Insertion (Zone 1: Causeway & Outer Wall)

```
ROOM 121 — Landfall            tileset: Building | conn N/S/W/E: 0/255/255/255
ROLE  : Insertion point. KESTREL comes ashore on the causeway. Empty, calm — the breath
        before the dive. (No radio here; first contact is room 0.)
TILES : re-skin to a wet concrete causeway / sea-gate.
ACTORS: none (keep empty).
DOORS : none.
```

```
ROOM 0 — Outer Gate            tileset: Building | conn: 1/121/255/4
ROLE  : First contact. WARDEN delivers the three mission orders (auto-reply on entry).
ITEMS : Access Card III (engine: CARD3) — your first keycard.
ACTORS: Concord troopers (keep ID_GUARD_MEDIUM/SLOW).
RADIO : WARDEN (auto) →
        "Kestrel, WARDEN. You're inside the Reach. Three things: confirm AZRAEL is real,
         pull our man GRAVE out, and put that machine in the dirt. Stay a ghost. Out."
```

```
ROOM 1 — Gatehouse             tileset: Building | conn: 2/0/255/5
ROLE  : RELAY makes uninvited contact — establishes the informant.
ACTORS: troopers.
RADIO : WARDEN (wait) → repeat mission if called.
        RELAY (end) →
        "Don't shoot — I'm a friend on the inside. Mara Vance. The Concord built this place
         to be a maze; I have the map. Tune 12079 and I'll walk you through. ...if you live."
```

```
ROOM 5 — Loading Dock          tileset: Building | conn: 6/4/1/9
ROLE  : Teaches the card→door system via the supply skiffs.
ITEMS : Access Card I (CARD1).
ACTORS: ID_GUARD_EXIT_LORRY (Concord dockhands climbing off a skiff).
DOORS : skiff doors (keep DoorsRoom005 wiring; card/lorry logic).
RADIO : WARDEN (wait) →
        "Grab the gear off that cargo skiff. You'll need an access card to crack the door.
         Cards open colored locks — match the card to the door. Out."
```

```
ROOM 20 — Drone Bay            tileset: Building | conn: 255/255/16/22
ROLE  : First boss. ORACLE introduces enemy-telemetry hints.
ACTORS: HOWLER (keep ID_MACH_GUN_KID).
DOORS : keep DoorsRoom020 (card-gated side doors).
RADIO : ORACLE (wait) →
        "Ada Lin, telemetry. That gun-drone — HOWLER — skins anything that moves but its
         tracking is dumb. Kill it with a GUIDED MISSILE, nothing else. ...Bye."
```

```
ROOM 25 — Munitions            tileset: Building | conn: 26/24/255/255
ROLE  : Supplies the weapon for HOWLER / the power coupling.
ITEMS : Guided Missile (MISSILE).
ACTORS: troopers.
```

```
ROOM 28 — Comms Closet         tileset: Building | conn: 29/255/255/32
ROLE  : Teaches calling out on the radio.
RADIO : WARDEN (wait) →
        "There's a resistance cell in here somewhere. Work the transceiver and find them.
         Out."
```

```
ROOM 29 — Vent Control         tileset: Building | conn: 30/28/255/255
ROLE  : Gas-hazard sign-posting; supplies the grenade launcher.
ITEMS : Grenade Launcher (GRENADE_LAUNCHER).
RADIO : WARDEN (auto) → "Toxic scrubbers ahead. Get a GAS MASK before you choke. Out."
        RELAY (wait) → "Mask's in the south end of floor 1. Go get it before that room."
```

```
ROOM 16 — Scrubber Room        tileset: Building | conn N/S/W/E: 17/-/-/20
ROLE  : The gas-mask pickup the radio (room 29) points to.
ITEMS : Gas Mask (GAS_MASK).   [engine: Gas Mask lives in DOOR ROOM 138 (slot 16); reached via a door from open room 16]
```

```
ROOM 37 — Power Spine          tileset: Building | conn: 38/36/255/255
ROLE  : The electrified-floor puzzle: blow the power coupling with a missile.
RADIO : WARDEN (auto) →
        "That floor's live. Put a GUIDED MISSILE through the power coupling to kill the
         current. Out."
        RELAY (wait) → "Spare missile's in the southeast cells. Don't waste it."
```

```
ROOM 50 — Helipad Approach     tileset: Hind-D | conn: 51/255/48/255
ROLE  : Boss: the gunship.
ACTORS: SHRIKE (keep ID_HIND_D).
RADIO : ORACLE (wait) →
        "That's SHRIKE — a Concord gunship. Small-arms tickle it. A GRENADE LAUNCHER puts
         it down. ...Bye."
```

```
ROOM 48 — Basement Cache       tileset: Building | conn: 117/255/44/50
ROLE  : Kinetic-suit pickup (for the rooftop wind-wall).
ITEMS : Kinetic Suit (BOMB_SUIT).
```

```
ROOM 53 — Roof Edge            tileset: Roof | conn: 255/52/49/255
ROLE  : Rooftop hazard sign-posting.
RADIO : WARDEN (auto) →
        "The Crown's got a kinetic wind-wall — it'll throw you off. Find the KINETIC SUIT to
         push through. Out."
        RELAY (wait) → "Suit's down in the basement. Typical Concord — safety gear in the
         one place you can't reach."
```

---

## ACT II — Captured (Zone 1 lower levels / cells)

```
ROOM 54 — Holding Block        tileset: Basement | conn: 55/255/255/57
ROLE  : Post-capture recovery hub. WARDEN tells you to reclaim your kit. Lamp pickup.
ITEMS : Lamp (FLASH_LIGHT).
RADIO : WARDEN (wait) →
        "They stripped you? Figures. We stashed your KIT BAG in one of these rooms — punch
         the walls that sound hollow and take it back. Out."
```

```
ROOM 46 — Stash Room           tileset: Building | conn: 47/45/42/117
ROLE  : Recover your confiscated loadout.
ITEMS : Kit Bag (BAG) — restores all weapons/equipment + adds the transmitter.
```

```
ROOM 57 — Cellblock Door       tileset: Basement | conn: 255/255/54/58
ROLE  : Boss: BREAKER smashes the cellblock door open.
ACTORS: BREAKER (keep ID_SHOT_GUNNER).
DOORS : punch-open door (keep DoorsRoom057, ChkPunchDoor logic).
RADIO : WARDEN (wait) → reuse "take back your kit" line if called.
```

```
ROOM 164 — GRAVE's Cell        tileset: Isolated | reached via door from the cell wing
ROLE  : Rescue partner Cole Marsh. Seeds Twist I.
ACTORS: GRAVE (keep ID_GREY_FOX) behind a breakable cell wall.
DOORS : breakable prison wall (keep ChkPrisonWalls; punch through).
RADIO : (in-room text, not radio) GRAVE →
        "Kestrel. Knew they'd send you. Listen — AZRAEL is real, and this op is rotten to
         the spine. Whoever's in your ear... don't trust the voice. Check the wall behind me."
RADIO @165 (Cell Wing): WARDEN (auto) →
        "Infiltration's holding. GRAVE's cell is close — CHECK THE WALLS. Out."
```

---

## ACT III — The Yards (desert + skiffs) & Building 2

```
ROOM 67 — The Yards            tileset: Basement/Desert | conn: 68/65/66/66
ROLE  : Boss: the crawler, out on the open hardstand.
ACTORS: GOLIATH (keep ID_TANK).
RADIO : ORACLE (wait) →
        "GOLIATH — a Concord crawler. Armor laughs at bullets. Lay MINES and let it drive
         over them. ...Bye."
```

```
ROOM 69 — Checkpoint Gate      tileset: Basement/Desert | conn: 73/68/69/69
ROLE  : Disguise checkpoint into Building 2. Frequencies move to deep-zone bands.
ACTORS: Concord checkpoint security (keep ID_DESERT_SECURITY + ID_SENTINEL).
DOORS : uniform-gated desert door (keep ChkDesertDoorBuild2).
RADIO : WARDEN (auto) →
        "Checkpoint. Put on a CONCORD UNIFORM and walk through like you own it. From here we
         switch to band 12013. Out."
        RELAY (wait) → "Uniform's in the Building 1 basement. New band for me: 12026."
        ORACLE (wait) → "I'm moving to 12091. Stay sharp in there."
```

```
ROOM 47 — Lower Armory         tileset: Building | conn: 255/46/43/49
ROLE  : The Concord-uniform pickup.
ITEMS : Concord Uniform (UNIFORM).
```

```
ROOM 71 — Service Level        tileset: Building | conn: 72/70/255/74
ROLE  : Boss: the demolition rig.
ACTORS: DOZER (keep ID_BULLDOZER).
```

```
ROOM 83 — The Gauntlet         tileset: Building | conn: 84/82/80/86
ROLE  : Invincible sentinels guard the doors — pure evasion.
ACTORS: The Arbiters ×2 (keep ID_ARNOLD).
RADIO : ORACLE (wait) →
        "Those two — the ARBITERS — are armored cores. You can't kill them. Don't try. Slip
         past and LEAVE. ...Bye."
```

```
ROOM 86 — Vault Approach       tileset: Building | conn: 87/85/83/255
ROLE  : SAINT introduces himself; supplies the rocket launcher.
ITEMS : (SAINT leaves it nearby — ROCKET_LAUNCHER lives at room 63; keep or relocate.)
RADIO : SAINT (wait) →
        "Joon Park — quartermaster, and I'm done with these people. I left you a ROCKET
         LAUNCHER. My sister Iris is a hostage in here. Please... get her out. ...Over."
```

```
ROOM 87 — Compass Vault Door   tileset: Building | conn: 255/86/84/255
ROLE  : SAINT opens the locked vault to the Compass.
DOORS : ally-opened door (keep ChkCompassDoor / JeniOpenDoorF).
RADIO : SAINT (wait) → "Opening the vault now. Go. ...Over."
```

```
ROOM 62 — Compass Vault        tileset: Building | conn: 63/61/58/255
ROLE  : Compass pickup (for the dark maze).
ITEMS : Compass (COMPASS).
```

---

## ACT IV — The Drowned Quarter (Building 2 basement + channel + maze)

```
ROOM 93 — Blackout Sub-level   tileset: Basement | conn: 94/125/255/96
ROLE  : Lightless maze entry; pitfall warnings.
RADIO : RELAY (wait) → "Power's cut in there. The LAMP's on floor 1 — grab it or go blind."
        ORACLE (wait) → "Watch your step. The floor isn't all there. ...Bye."
```

```
ROOM 95 — Incinerator          tileset: Basement | conn: 255/94/255/98
ROLE  : Boss: the flamethrower trooper.
ACTORS: PYRE (keep ID_FIRE_TROOPER).
```

```
ROOM 102 — Flooded Yard        tileset: Basement/Desert | conn: 103/75/102/102
ROOM 103 — Flooded Yard 2      tileset: Basement/Desert | conn: 208/102/103/103
ROLE  : Venom-drone / scorpion nests.
ACTORS: Scorpions ×6 (keep ID_SCORPION).
RADIO : RELAY (wait, @102) → "The COMPASS is on floor 2 if you still need it."
        ORACLE (wait, @102) → "Those stingers carry venom. Keep ANTIVENOM on you. ...Bye."
```

```
ROOM 189 — "Roth" (the Double) tileset: Isolated | reached via door from B2
ROLE  : Twist II part 1 — the impostor scientist baits an ambush.
ACTORS: "Roth" the Double (keep ID_FAKE_MADNAR).
RADIO : (in-room text) "Roth" → "Thank god, an agent! Quickly, this way — I'll show you the
        core access..." (it's a trap; the room is a kill-box).
```

```
ROOM 115 — Channel Lock        tileset: Basement | conn: 255/255/111/255
ROLE  : Rebreather is hidden behind a wall before the flooded channel.
RADIO : SAINT (auto) → "There's a REBREATHER behind that wall. The channel ahead floods —
        you won't make it without air. ...Over."
```

```
ROOM 78 — Rebreather Cache     tileset: Building | (reached off the channel)
ROLE  : Rebreather pickup; gates the underwater crossing to Building 3.
ITEMS : Rebreather (OXYGEN).
```

---

## ACT V — The Spire & the truth (Building 3)

```
ROOM 104 — Skiff Terminal      tileset: Basement/Desert | conn: 108/210/104/104
ROLE  : Truck-transport puzzle into the Spire.
RADIO : WARDEN (auto) → "Climb into the cargo skiff on the right. It'll carry you in. Out."
```

```
ROOM 108 — Spire Junction      tileset: Building | conn: 109/104/255/107
ROLE  : WARDEN starts steering you wrong; SAINT counters.
RADIO : WARDEN (auto) → "Take the LEFT door. Trust me. Out."
        SAINT (end) → "Don't — destroy the WALL instead. The left door's a furnace. ...Over."
```

```
ROOM 111 — Dead Air            tileset: Basement | conn: 112/255/255/115
ROLE  : THE TRAP. WARDEN orders you to abort. SAINT gives the real route.
RADIO : WARDEN (auto) →
        "Kestrel — operation's burned. Trigger your transponder self-wipe and go dark. Walk
         away. That's a direct order. ...Out."
        SAINT (end) →
        "Don't you dare. The core card's in the east block of Building 3 — it loops back
         through the water channel. Keep moving. ...Over."
```

```
ROOM 182 — The Real Roth       tileset: Isolated | reached via SW basement passage
ROLE  : Twist II part 2 — the true architect and AZRAEL's weakness.
ACTORS: Dr. Elias Roth (keep ID_MADNAR).
RADIO : RELAY (wait, @182) → "There's a secret passage from the southwest basement back to
        Building 1. Roth's through there. ...Over."
        (in-room text) Roth → "You found me. AZRAEL has three cores — BREACHING CHARGES,
        all three, or it's pointless. And listen: Crane fires the uplink the instant the
        alarm peaks. Your break-in IS his trigger. Beat his clock or we all lose."
```

```
ROOM 192 — Uplink Antechamber  tileset: Isolated | reached via B2 east
ROLE  : RELAY names the traitor on air — and is silenced.
RADIO : RELAY (auto) →
        "I have it — the architect of AZRAEL is— it's— no— !!" [signal lost]
        (Set SchneiderCaptured. RELAY goes off the air for the rest of the game.)
```

```
ROOM 193 — Hostage Hall        tileset: Isolated | conn (B-side): keep existing
ROLE  : Boss: MAGPIE behind human shields; drops the Master Card.
ACTORS: MAGPIE (keep ID_COWARD_DUCK) + hostages (ID_PRISONER1 ×3, incl. Iris).
RADIO : SAINT (auto) →
        "MAGPIE has the MASTER CARD — but he's hiding behind hostages. My sister's in there.
         Use your SIDEARM only. Please don't hit them. ...Over."
        ORACLE (wait) →
        "A HANDGUN drops MAGPIE clean without spraying the room. Anything bigger and you'll
         kill them. ...Bye."
```

---

## FINALE — AZRAEL, Crane, and the run

```
ROOM 118 — AZRAEL Hangar       tileset: Metal Gear | conn: 255/116/119/255
ROLE  : Boss: the colossal siege-walker. Plant breaching charges on its three cores.
ACTORS: AZRAEL (keep ID_METAL_GEAR).
DOORS : west wall to Crane's deck opens after AZRAEL falls (keep OpenBigBossDoor logic).
NOTE  : destroying it sets MetalGear_KO → starts the self-destruct timer; NO MORE SAVES.
```

```
ROOM 119 — Command Deck        tileset: Building | conn: 255/255/255/118
ROLE  : Final boss: Director Crane / WARDEN. The mentor, unmasked.
ACTORS: Crane (keep ID_BIG_BOSS).
DOORS : door to escape ladders opens after Crane (keep ChkBigBossDoor → dest 224).
RADIO : ORACLE (auto) →
        "I can't tell you how to beat him, Kestrel. Only you can. ...Just come back."
        SAINT (end) →
        "A PULSE STIM steadies your hands — and buys you seconds on that clock. Live, you
         hear me? ...Over."
```

```
ROOMS 224+ — Escape Ladders    tileset: Elevator/Ladders
ROLE  : Race the self-destruct out of the flooding Spire. Pulse Stim stretches the timer.
        Reaching the extraction skiff = win → Ending (GameStatus 8).
NOTE  : no pause / radio / inventory in ladder rooms (engine rule for rooms >=224).
```

**Ending text** (`data/texts.asm`, ending strings + staff roll):
> ORACLE: "NIGHTJAR's gone, Kestrel. Officially, you never existed. ...Unofficially —
> thank you."
> Coda (clean Concord signal): "Reach is lost. The board has voted. Begin Halcyon Two."
> **THERE IS NO NIGHTJAR.**

---

## Appendix A — Zone → room-range → tileset map

For all rooms (including the connective corridors not detailed above). Tileset from
`data/roomtileset.asm`.

| Rooms | Zone (NIGHTJAR) | Tileset | Treatment |
|-------|-----------------|---------|-----------|
| 121, 0–39 | Z1 Causeway / Outer Wall interior | Building (0) | re-skin to fortress interior |
| 40–53 | The Crown (Building 1 roof) | Roof (2) | rooftop / wind-wall; Hind-D pad at 50 (tileset 5) |
| 54–63 | Z1 basement / cells | Basement (1) + Building | holding block, caches |
| 64–69 | The Yards (desert) | Basement/Desert (1) | open hardstand + skiff docks |
| 70–101 | Z2 Drowned Quarter (Building 2) | Building (0) + Basement (1) | flooded interior + sub-levels |
| 102–110, 208–212 | Flooded yards + water channel | Basement/Desert (1) | scorpion nests, the channel |
| 111–119 | Z3 The Spire (Building 3) | Building (0) / Metal Gear (6) at 118 | AI core, AZRAEL hangar, command deck |
| 117 | The Crown drop | Roof (2) | parachute jump |
| 122–125, 138–141, 220–222 | The Bilge (dark maze) | Isolated (4) | blackout, pitfalls, secret passages |
| 160–207 (incl. 164/167/182/189/193) | Isolated cells / NPC & hostage rooms | Isolated (4) | GRAVE, Roth, the Double, MAGPIE, hostages |
| 213–219 | Cargo skiffs | Lorry (4) | transport puzzles |
| 224–228 | Escape ladders | Elevator/Ladders (3) | finale run |
| 240–250 | Internal lifts | Elevator (3) | elevator shafts |

## Appendix B — Complete per-room reference (rooms 0–221)

Every room with engine data, extracted directly from the source tables
(`roomtileset.asm`, `roomsconnections.asm`, `actorsinrooms.asm`, `itemsinrooms.asm`,
`doors.asm`, `radiocalls.asm`). This **supersedes a blanket "filler" rule** — each room is
now explicit.

* **★** = detailed as a story beat in the Act sections above (critical path). Unmarked rows
  are connective/patrol rooms.
* **Enemies / Item set / Door / Radio** use the *engine's own labels* (what you edit in the
  `data/` files). Translate names to NIGHTJAR via the re-skin tables at the top of this doc.
* **N/S/W/E** `-` = wall. `(via door)` = room is reached through a door (rooms >154 are the
  "B-side" rooms the door tables teleport into); keep existing door wiring.
* **Door**/**Radio** `-` = none. Door/Radio values are the `DoorsRoomNNN` / `RadioRoom_NNN`
  label suffix for that room.

### Work-order rule for unmarked (filler) rooms
1. **Tiles** — re-skin via the room's tileset (column 4); no layout change required.
2. **Enemies** — keep the listed `ID_*` actors (already balanced); re-skin sprites globally.
3. **Item set** — keep `Ammo*`/`Ration*` caches (they pace the game); rename in
   `data/itemnames.asm` only. Relocate a key item only if you redesign the map.
4. **Door** — keep wiring; change a card requirement only if your access tiers differ (§8).
5. **Radio** — leave `-` rooms silent.

| Rm | ★ | Zone | Tileset | N/S/W/E | Enemies | Item set | Door | Radio |
|---:|:-:|------|---------|---------|---------|----------|------|-------|
| 0 | ★ | Z1 Outer Wall | Building | 1/121/-/4 | - | Card3 | - | 000 |
| 1 | ★ | Z1 Outer Wall | Building | 2/0/-/5 | 3: 2xGUARD_MEDIUM, 1xGUARD_SLOW | - | - | 001 |
| 2 |  | Z1 Outer Wall | Building | 3/1/-/6 | 2: 1xGUARD_SLOW, 1xGUARD_MEDIUM | - | - | - |
| 3 |  | Z1 Outer Wall | Building | -/2/-/7 | 3: 1xSPAWN_GUARD_ELEV, 2xGUARD_ELEVATOR | - | 003 | - |
| 4 | ★ | Z1 Outer Wall | Building | 5/-/0/8 | 2: 1xGUARD_MEDIUM, 1xGUARD_FAST | Ration | - | 004 |
| 5 | ★ | Z1 Outer Wall | Building | 6/4/1/9 | 1: 1xGUARD_EXIT_LORRY | Card1 | 005 | 005 |
| 6 |  | Z1 Outer Wall | Building | 7/5/2/10 | 2: 2xDOG | Binoculars | 006 | - |
| 7 |  | Z1 Outer Wall | Building | -/6/3/11 | 2: 2xGUARD_EXIT_LORRY | - | 007 | 005 |
| 8 |  | Z1 Outer Wall | Building | 9/-/4/12 | - | Gun | 008 | 005 |
| 9 |  | Z1 Outer Wall | Building | 10/8/5/13 | 12: 12xLAND_MINE | - | 009 | - |
| 10 |  | Z1 Outer Wall | Building | 11/9/6/14 | 3: 3xDOG | Mines | 010 | - |
| 11 |  | Z1 Outer Wall | Building | 64/10/7/15 | 4: 4xSENTINEL | - | 011 | - |
| 12 |  | Z1 Outer Wall | Building | 13/-/8/- | 2: 2xGUARD_SLOW | - | - | - |
| 13 |  | Z1 Outer Wall | Building | 14/12/9/- | 2: 2xGUARD_SLOW | Card4 | 013 | - |
| 14 |  | Z1 Outer Wall | Building | 15/13/10/- | 3: 3xCAMERA | - | 014 | - |
| 15 |  | Z1 Outer Wall | Building | -/14/11/- | 2: 2xGUARD_SLOW | SMG | 015 | - |
| 16 |  | Z1 Outer Wall | Building | 17/-/-/20 | 1: 1xGUARD_SWITCH | GasMask | 016 | - |
| 17 |  | Z1 Outer Wall | Building | 18/16/-/- | 4: 4xGUARD_SLOW | Goggles | 017 | - |
| 18 |  | Z1 Outer Wall | Building | 19/17/-/- | 5: 5xGUARD_SLOW | Mines2 | - | - |
| 19 |  | Z1 Outer Wall | Building | -/18/-/21 | 2: 2xGUARD_FAST | - | 019 | - |
| 20 | ★ | Z1 Outer Wall | Building | -/-/16/22 | 1: 1xMACH_GUN_KID | PBombAmmo | 020 | 020 |
| 21 |  | Z1 Outer Wall | Building | -/-/19/23 | 1: 1xCAMERA | Parachute | 021 | - |
| 22 |  | Z1 Outer Wall | Building | -/-/20/24 | 2: 2xGUARD_FAST | - | 022 | - |
| 23 |  | Z1 Outer Wall | Building | -/-/21/27 | 3: 3xGUARD_SLOW | - | 023 | - |
| 24 |  | Z1 Outer Wall | Building | 25/-/22/- | 1: 1xLASER | - | 024 | - |
| 25 | ★ | Z1 Outer Wall | Building | 26/24/-/- | 1: 1xLASER | Missile | - | - |
| 26 |  | Z1 Outer Wall | Building | 27/25/-/- | 1: 1xGUARD_SLOW | - | - | - |
| 27 |  | Z1 Outer Wall | Building | -/26/23/- | 2: 2xCAMERA | Ammo | 027 | - |
| 28 | ★ | Z1 Outer Wall | Building | 29/-/-/32 | 2: 1xCAMERA, 1xGUARD_SLOW | - | 028 | 028 |
| 29 | ★ | Z1 Outer Wall | Building | 30/28/-/- | 4: 4xGAS | Grenade | 029 | 029 |
| 30 |  | Z1 Outer Wall | Building | 31/29/-/- | 2: 2xGUARD_FAST | - | 030 | 030 |
| 31 |  | Z1 Outer Wall | Building | -/30/-/33 | 2: 2xCAMERA | PBomb3 | 031 | 031 |
| 32 |  | Z1 Outer Wall | Building | -/-/28/34 | 1: 1xGUARD_SLOW | - | 032 | - |
| 33 |  | Z1 Outer Wall | Building | -/-/31/35 | 2: 2xGUARD_MEDIUM | - | 033 | 033 |
| 34 |  | Z1 Outer Wall | Building | -/-/32/36 | 2: 1xGUARD_FAST, 1xGUARD_MEDIUM | Box | - | - |
| 35 |  | Z1 Outer Wall | Building | -/-/33/39 | 3: 2xGUARD_SLOW, 1xGUARD_FAST | Card2 | 035 | - |
| 36 |  | Z1 Outer Wall | Building | 37/-/34/- | 3: 2xCAMERA, 1xGUARD_SLOW | Ration4 | 036 | - |
| 37 | ★ | Z1 Outer Wall | Building | 38/36/-/- | 1: 1xPOWER_SWITCH | - | - | 037 |
| 38 |  | Z1 Outer Wall | Building | 39/37/-/- | 2: 1xGUARD_SLOW, 1xGUARD_FAST | MineDetect | 038 | - |
| 39 |  | Z1 Outer Wall | Building | -/38/35/- | 4: 4xSENTINEL | - | 039 | - |
| 40 |  | Crown (roof) | Roof | 41/-/-/44 | 1: 1xJETPACK_SWITCH | Ammo2 | 040 | - |
| 41 |  | Crown (roof) | Roof | 42/40/-/45 | - | Missile2 | 041 | - |
| 42 |  | Crown (roof) | Roof | 43/41/-/46 | - | - | 042 | - |
| 43 |  | Crown (roof) | Roof | -/42/-/47 | 2: 1xGUARD_MEDIUM, 1xGUARD_SLOW | - | - | - |
| 44 |  | Crown (roof) | Roof | 45/-/40/48 | 1: 1xJETPACK_TAKEOFF | - | - | - |
| 45 |  | Crown (roof) | Building | 46/44/41/117 | 9: 1xBRIDGE_CTRL, 8xBRIDGE | - | - | 045 |
| 46 | ★ | Crown (roof) | Building | 47/45/42/- | 9: 1xBRIDGE_CTRL, 8xBRIDGE | Bag | - | 045 |
| 47 | ★ | Crown (roof) | Roof | -/46/43/49 | 2: 2xGUARD_MEDIUM | Uniform | - | - |
| 48 | ★ | Crown (roof) | Roof | 117/-/44/50 | 1: 1xJETPACK_TAKEOFF | BombSuit | - | 045 |
| 49 |  | Crown (roof) | Roof | -/-/47/53 | 3: 3xGUARD_MEDIUM | Armor | - | - |
| 50 | ★ | Crown (roof) | Hind-D | 51/-/48/- | 1: 1xHIND_D | PBombAmmo2 | - | 050 |
| 51 |  | Crown (roof) | Roof | 52/50/117/- | 1: 1xGUARD_SLOW | - | 051 | 045 |
| 52 |  | Crown (roof) | Roof | 53/51/-/- | 2: 2xGUARD_FAST | PBomb2 | - | - |
| 53 | ★ | Crown (roof) | Roof | -/52/49/- | - | Ration2 | 053 | 053 |
| 54 | ★ | Z1 cells/cache | Basem/Desert | 55/-/-/57 | - | FlashLight | 054 | 054 |
| 55 |  | Z1 cells/cache | Basem/Desert | 56/54/-/- | 2: 2xDOG | UniMineAmm | 055 | - |
| 56 |  | Z1 cells/cache | Basem/Desert | 123/55/-/- | 4: 4xDOG | Antenna | 056 | - |
| 57 | ★ | Z1 cells/cache | Basem/Desert | -/-/54/58 | 1: 1xSHOT_GUNNER | PBomb | 057 | 054 |
| 58 |  | Z1 cells/cache | Basem/Desert | 59/-/57/61 | 2: 1xDOG_BASEMENT, 1xSPAWN_DOG | - | 058 | 058 |
| 59 |  | Z1 cells/cache | Basem/Desert | 60/58/-/62 | 1: 1xSPAWN_DOG | Ammox3 | 059 | 058 |
| 60 |  | Z1 cells/cache | Basem/Desert | -/59/-/63 | 2: 1xDOG_BASEMENT, 1xSPAWN_DOG | - | 060 | 058 |
| 61 |  | Z1 cells/cache | Basem/Desert | 62/-/58/- | 2: 1xDOG_BASEMENT, 1xSPAWN_DOG | Antidote | 061 | 058 |
| 62 | ★ | Z1 cells/cache | Basem/Desert | 63/61/59/- | 1: 1xSPAWN_DOG | Compass | 062 | 058 |
| 63 |  | Z1 cells/cache | Basem/Desert | -/62/60/- | 2: 1xDOG_BASEMENT, 1xSPAWN_DOG | Rocket | 063 | 058 |
| 64 |  | The Yards | Basem/Desert | 120/11/64/64 | 9: 9xLAND_MINE | - | 064 | - |
| 65 |  | The Yards | Basem/Desert | 66/120/65/65 | 1: 1xSPAWN_TANK_SHELL | Card5Ammo | 065 | - |
| 66 |  | The Yards | Basem/Desert | 67/65/66/66 | 1: 1xSPAWN_TANK_SHELL | Card6 | - | - |
| 67 | ★ | The Yards | Basem/Desert | 68/66/67/67 | 1: 1xTANK | - | - | 067 |
| 68 |  | The Yards | Basem/Desert | 69/67/68/68 | - | - | - | - |
| 69 | ★ | The Yards | Basem/Desert | 73/68/69/69 | 4: 3xSENTINEL, 1xDESERT_SECURITY | BombAmmRat | 069 | 069 |
| 70 |  | Z2 Drowned Q. | Building | 71/-/-/73 | 2: 2xGUARD_SLOW | Ammox2 | 070 | - |
| 71 | ★ | Z2 Drowned Q. | Building | 72/70/-/74 | 1: 1xBULLDOZER | - | 071 | - |
| 72 |  | Z2 Drowned Q. | Building | -/71/-/75 | 1: 1xLASER | - | 072 | - |
| 73 |  | Z2 Drowned Q. | Building | 74/69/70/76 | - | - | 073 | - |
| 74 |  | Z2 Drowned Q. | Building | 75/73/71/77 | 3: 3xGUARD_SLOW | Ammox2_ | 074 | - |
| 75 |  | Z2 Drowned Q. | Building | 102/74/72/78 | - | Ration4 | 075 | - |
| 76 |  | Z2 Drowned Q. | Building | 77/-/73/- | 1: 1xPITFALL | - | 076 | - |
| 77 |  | Z2 Drowned Q. | Building | 78/76/74/- | 3: 1xSENTINEL, 2xGUARD_SLOW | - | - | - |
| 78 | ★ | Z2 Drowned Q. | Building | 105/77/75/- | - | Oxygen | 078 | - |
| 79 |  | Z2 Drowned Q. | Building | 80/-/-/82 | 4: 3xGUARD_FAST, 1xGUARD_SLOW | - | 079 | - |
| 80 |  | Z2 Drowned Q. | Building | 81/79/-/83 | 3: 3xSENTINEL | - | - | - |
| 81 |  | Z2 Drowned Q. | Building | -/80/-/84 | 4: 4xGUARD_SLOW | - | 081 | - |
| 82 |  | Z2 Drowned Q. | Building | 83/-/79/85 | 4: 4xSENTINEL | - | 082 | 082 |
| 83 | ★ | Z2 Drowned Q. | Building | 84/82/80/86 | 2: 2xARNOLD | - | 083 | 083 |
| 84 |  | Z2 Drowned Q. | Building | -/83/81/87 | 4: 2xGUARD_FAST, 2xGUARD_MEDIUM | - | 084 | - |
| 85 |  | Z2 Drowned Q. | Building | 86/-/82/- | 1: 1xGUARD_SLOW | - | 085 | - |
| 86 | ★ | Z2 Drowned Q. | Building | 87/85/83/- | 3: 1xSENTINEL, 2xGUARD_SLOW | - | 086 | 086 |
| 87 | ★ | Z2 Drowned Q. | Building | -/86/84/- | 3: 3xSENTINEL | - | 087 | 087 |
| 88 |  | Z2 Drowned Q. | Roof | -/-/-/91 | 3: 3xSHOOTER | - | 088 | - |
| 89 |  | Z2 Drowned Q. | Roof | 90/-/-/92 | 1: 1xJETPACK_TAKEOFF | - | 089 | - |
| 90 |  | Z2 Drowned Q. | Roof | 91/89/-/- | 3: 3xSHOOTER | - | - | - |
| 91 |  | Z2 Drowned Q. | Roof | -/90/88/- | 4: 4xSHOOTER | - | - | - |
| 92 |  | Z2 Drowned Q. | Roof | -/-/89/- | 1: 1xJETPACK_TAKEOFF | Ammo2 | 092 | - |
| 93 | ★ | Z2 Drowned Q. | Basem/Desert | 94/125/-/96 | 1: 1xPITFALL | - | 093 | 093 |
| 94 |  | Z2 Drowned Q. | Basem/Desert | 95/93/-/97 | 4: 4xGAS | Ammox2_ | 094 | 094 |
| 95 | ★ | Z2 Drowned Q. | Basem/Desert | -/94/-/98 | 9: 1xFIRE_TROOPER, 8xFLAME | - | 095 | - |
| 96 |  | Z2 Drowned Q. | Basem/Desert | 97/-/93/99 | 4: 4xGAS | Ration5 | 096 | 094 |
| 97 |  | Z2 Drowned Q. | Basem/Desert | 98/96/94/100 | 4: 4xGAS | - | - | 094 |
| 98 |  | Z2 Drowned Q. | Basem/Desert | -/97/95/101 | 4: 4xGAS | - | 098 | - |
| 99 |  | Z2 Drowned Q. | Basem/Desert | 100/-/96/- | - | - | 099 | 099 |
| 100 |  | Z2 Drowned Q. | Basem/Desert | 101/99/97/- | 4: 4xGAS | - | 100 | 094 |
| 101 |  | Z2 Drowned Q. | Basem/Desert | -/100/98/- | 4: 4xGAS | - | 101 | - |
| 102 | ★ | Flooded yards | Basem/Desert | 103/75/102/102 | 6: 6xSCORPION | - | 102 | 102 |
| 103 | ★ | Flooded yards | Basem/Desert | 208/102/103/103 | 6: 6xSCORPION | - | - | 103 |
| 104 | ★ | Flooded yards | Basem/Desert | 108/210/104/104 | 4: 4xLORRY_SHOOTER | - | 104 | 104 |
| 105 |  | Flooded yards | Building | 106/78/-/- | - | - | - | - |
| 106 |  | Flooded yards | Building | 211/105/-/- | - | - | - | - |
| 107 |  | Flooded yards | Building | 110/212/108/- | 4: 4xGUARD_SLOW | - | - | - |
| 108 | ★ | Flooded yards | Building | 109/104/-/107 | 3: 3xGUARD_REDALERT | - | 108 | 108 |
| 109 |  | Flooded yards | Building | -/108/-/110 | 3: 3xPITFALL | - | 109 | - |
| 110 |  | Flooded yards | Building | -/107/109/- | 1: 1xPOWER_SWITCH | - | 110 | - |
| 111 | ★ | Z3 Spire | Basem/Desert | 112/-/-/115 | 2: 2xCAMERA_LASER | - | 111 | 111 |
| 112 |  | Z3 Spire | Basem/Desert | 113/111/-/- | 3: 3xGAS | - | 112 | - |
| 113 |  | Z3 Spire | Basem/Desert | 114/112/-/- | 2: 2xPITFALL | - | 113 | - |
| 114 |  | Z3 Spire | Basem/Desert | 116/113/-/- | 11: 8xLAND_MINE, 3xGAS | - | Room_114 | - |
| 115 | ★ | Z3 Spire | Basem/Desert | -/-/111/- | 2: 2xCAMERA_LASER | - | 115 | 115 |
| 116 |  | Z3 Spire | Basem/Desert | 118/114/-/- | 1: 1xPOWER_SWITCH | - | 116 | 116 |
| 117 |  | Z3 Spire | Roof | -/48/45/51 | - | - | 117 | 045 |
| 118 | ★ | Z3 Spire | MetalGear | -/116/119/- | 3: 1xMETAL_GEAR, 2xCAMERA_LASER | - | 118 | - |
| 119 | ★ | Z3 Spire | Building | -/-/-/118 | 1: 1xBIG_BOSS | - | 119 | 119 |
| 120 |  | Bilge/maze | Basem/Desert | 65/64/120/120 | 9: 9xLAND_MINE | - | - | - |
| 121 | ★ | Z1 Landfall | Building | 0/-/-/- | - | - | - | - |
| 122 |  | Bilge/maze | Lorry/Isolated | 221/56/-/- | - | - | 122 | - |
| 123 |  | Bilge/maze | Basem/Desert | 125/220/-/- | 3: 3xPITFALL | - | 123 | 123 |
| 124 |  | Bilge/maze | Basem/Desert | 93/124/-/- | 2: 2xPITFALL | - | - | 123 |
| 125 |  | Bilge/maze | Basem/Desert | 209/103/208/208 | - | - | 125 | 123 |
| 126 |  | Bilge/maze | Lorry/Isolated | 210/208/209/209 | - | - | 126 | - |
| 127 |  | Bilge/maze | Lorry/Isolated | 104/209/210/210 | 1: 1xGUARD_ALERT | - | 127 | - |
| 128 |  | Bilge/maze | Lorry/Isolated | 212/106/-/- | - | - | 128 | - |
| 129 |  | Bilge/maze | Lorry/Isolated | 107/211/-/- | 1: 1xPRISONER1 | - | 129 | - |
| 130 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | - | - | 130 | - |
| 131 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | 4: 4xGUARD_ALERT | - | 131 | - |
| 132 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | 1: 1xGUARD_ALERT | - | 132 | - |
| 133 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | - | - | 133 | - |
| 134 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | 1: 1xPRISONER1 | - | 134 | - |
| 135 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | - | - | 135 | - |
| 136 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | 1: 1xPRISONER1 | - | 136 | - |
| 137 |  | Bilge/maze | Lorry/Isolated | 124/221/-/- | - | - | 137 | - |
| 138 |  | Bilge/maze | Lorry/Isolated | 220/123/-/- | 1: 1xGUARD_SLOW | - | 138 | - |
| 139 |  | Bilge/maze | Lorry/Isolated | 221/124/-/- | - | - | 139 | - |
| 140 |  | Bilge/maze | Lorry/Isolated | -/-/-/- | 6: 3xSENTINEL, 3xSLEEPING_SIGN | - | 140 | - |
| 141 |  | Bilge/maze | Lorry/Isolated | 225/-/-/- | 1: 1xROLLING_BARREL | - | 141 | - |
| 142 |  | Bilge/maze | Lorry/Isolated | 226/224/-/- | - | - | 142 | - |
| 143 |  | Bilge/maze | Lorry/Isolated | 227/225/-/- | - | - | 143 | - |
| 144 |  | Bilge/maze | Lorry/Isolated | 228/226/-/- | 1: 1xPRISONER1 | - | 144 | - |
| 145 |  | Bilge/maze | Lorry/Isolated | 242/-/-/- | 1: 1xPRISONER1 | - | 145 | - |
| 146 |  | Bilge/maze | Lorry/Isolated | -/241/-/- | 1: 1xPRISONER1 | - | 146 | - |
| 147 |  | Bilge/maze | Lorry/Isolated | 244/-/-/- | - | - | 147 | - |
| 148 |  | Bilge/maze | Lorry/Isolated | -/243/-/- | 1: 1xPRISONER1 | - | 148 | - |
| 149 |  | Bilge/maze | Lorry/Isolated | 246/-/-/- | - | - | 149 | - |
| 150 |  | Bilge/maze | Lorry/Isolated | -/245/-/- | 4: 4xGUARD_SILENCER | - | 150 | 150 |
| 151 |  | Bilge/maze | Lorry/Isolated | -/248/-/- | - | - | 151 | - |
| 152 |  | Bilge/maze | Lorry/Isolated | 247/249/-/- | 1: 1xPRISONER1 | - | 152 | - |
| 153 |  | Bilge/maze | Lorry/Isolated | 248/250/-/- | 1: 1xROLLING_BARREL | - | 153 | - |
| 154 |  | Bilge/maze | Lorry/Isolated | 249/-/-/- | 1: 1xGUARD_ALERT | - | 154 | - |
| 155 |  | Bilge/maze | Lorry/Isolated | (via door) | - | - | - | - |
| 156 |  | Bilge/maze | Lorry/Isolated | (via door) | - | - | 156 | - |
| 157 |  | Bilge/maze | Lorry/Isolated | (via door) | - | - | 157 | - |
| 158 |  | Bilge/maze | Lorry/Isolated | (via door) | - | - | 158 | - |
| 159 |  | Bilge/maze | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 159 | - |
| 160 |  | Bilge/maze | Lorry/Isolated | (via door) | - | - | 160 | - |
| 161 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 161 | - |
| 162 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 162 | - |
| 163 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 163 | - |
| 164 | ★ | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xGREY_FOX | - | 164 | - |
| 165 | ★ | Cells/NPC | Lorry/Isolated | (via door) | - | - | 165 | 165 |
| 166 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 1xHELPME_VOICE, 1xPITFALL | - | 166 | - |
| 167 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xELLEN | - | 167 | - |
| 168 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 168 | - |
| 169 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 169 | - |
| 170 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 170 | - |
| 171 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 171 | - |
| 172 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 172 | - |
| 173 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 173 | - |
| 174 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 174 | - |
| 175 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 175 | - |
| 176 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 176 | - |
| 177 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 177 | - |
| 178 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xGUARD_SLOW | - | 178 | 178 |
| 179 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 179 | - |
| 180 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 180 | - |
| 181 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 2xGUARD_ALERT | - | 181 | - |
| 182 | ★ | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xMADNAR | - | 182 | 182 |
| 183 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 2xGUARD_REDALERT | - | 183 | - |
| 184 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 184 | - |
| 185 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 185 | - |
| 186 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 186 | - |
| 187 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 2xGUARD_ALERT | - | 187 | - |
| 188 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 188 | - |
| 189 | ★ | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xFAKE_MADNAR | - | 189 | - |
| 190 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 190 | - |
| 191 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xROLLING_BARREL | - | 191 | - |
| 192 | ★ | Cells/NPC | Lorry/Isolated | (via door) | - | - | 192 | 192 |
| 193 | ★ | Cells/NPC | Lorry/Isolated | (via door) | 5: 1xCOWARD_DUCK, 3xPRISONER1, 1xPITFALL | - | 193 | 193 |
| 194 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 194 | - |
| 195 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 195 | - |
| 196 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 196 | - |
| 197 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 197 | - |
| 198 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 198 | - |
| 199 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 199 | - |
| 200 |  | Cells/NPC | Lorry/Isolated | (via door) | - | - | 200 | - |
| 201 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPITFALL | - | 201 | - |
| 202 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 202 | 202 |
| 203 |  | Cells/NPC | Lorry/Isolated | (via door) | 1: 1xPRISONER1 | - | 203 | - |
| 204 |  | Cells/NPC | Elevator | (via door) | - | - | 204 | - |
| 205 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 1xROLLING_BARREL, 1xPITFALL | - | 205 | - |
| 206 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 2xSHOOTER | - | 206 | - |
| 207 |  | Cells/NPC | Lorry/Isolated | (via door) | 2: 2xDOG | - | 207 | - |
| 208 |  | special | Basem/Desert | (via door) | 6: 6xSCORPION | - | - | - |
| 209 |  | special | Basem/Desert | (via door) | 6: 6xSCORPION | - | - | - |
| 210 |  | special | Basem/Desert | (via door) | - | - | - | - |
| 211 |  | special | Building | (via door) | - | - | - | - |
| 212 |  | special | Building | (via door) | - | - | - | - |
| 213 |  | special | Lorry/Isolated | (via door) | - | - | 213 | - |
| 214 |  | special | Lorry/Isolated | (via door) | - | - | 214 | - |
| 215 |  | special | Lorry/Isolated | (via door) | - | - | 215 | - |
| 216 |  | special | Lorry/Isolated | (via door) | 3: 3xGUARD_REDALERT | - | 216 | - |
| 217 |  | special | Lorry/Isolated | (via door) | - | - | 217 | - |
| 218 |  | special | Lorry/Isolated | (via door) | - | - | 218 | - |
| 219 |  | special | Lorry/Isolated | (via door) | - | - | 219 | - |
| 220 |  | special | Basem/Desert | (via door) | 3: 3xPITFALL | - | - | 123 |
| 221 |  | special | Basem/Desert | (via door) | 3: 3xPITFALL | - | - | 123 |

## Appendix C — Per-file edit checklist

Work the files in this order (each is "content", safe to rewrite — see
[06-REWORK-GUIDE.md](06-REWORK-GUIDE.md)):

1. **`data/itemnames.asm`** — rename all items (one-time, global). Quick win.
2. **`gfx/*` + `data/palettes.asm`** — re-skin the 8 tilesets + sprite sets. Bulk of the art.
3. **`data/texts.asm`** — write every radio/in-room line from this sheet using
   **`tools/mgtext.py patch <label> --type 0x13 "..."`** (see
   [07-TEXT-ENCODING.md](07-TEXT-ENCODING.md)); note each new text ID.
4. **`data/radiocalls.asm`** — repoint each `RadioRoom_xxx` to the new text IDs; rename
   caller comments WARDEN/RELAY/ORACLE/SAINT. (Room→caller wiring already matches the beats.)
5. **`data/actorsinrooms.asm`** — confirm boss placements per §7 of the plot (they already
   match the rooms in this sheet). Adjust only if relocating a boss.
6. **`data/itemsinrooms.asm`** — confirm key-item placements per the room blocks; relocate
   if your map differs.
7. **`data/doors.asm`** — only if you change access tiers / add a gate.
8. **`data/rooms.asm` + `data/roomtileset.asm`** — only if you redraw room layouts.
9. **`logic/*`** — leave alone. No engine change is required for this story.

Rebuild after each file (see [01-BUILD.md](01-BUILD.md)); watch for `ASSERT $=#C000`
(bank overflow) if you add a lot of text.
