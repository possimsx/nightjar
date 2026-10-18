# 04 — Game Objects Index

Everything Snake can carry or pick up: **what it is, what it's for, where it is, and when
you need it to progress.** Source tables: `constants/Enums.asm` (IDs),
`data/itemsinrooms.asm` (placement), `data/itemnames.asm` (names),
`data/itemtakeamount.asm` (quantities), `logic/items.asm` (pickup logic),
`logic/doors/opendoor.asm` (what cards unlock).

---

## 1. How objects work

### Object identity uses **two** numbering schemes
* **Pickup/world ID** (`enum ITEMS` in `Enums.asm`): the byte stored in the world and in
  `ItemsInTheRoom`. Weapons share this space (1–7), then equipment 8h–23h.
* **Inventory/selected ID** (`enum SELECTED_ITEM`): how an item is referenced once in the
  menu / when "in use" (`SelectedItem`). Pickup ID `SUPRESSOR(8)` maps to `SELECTED` index
  1, i.e. `selected = pickupID − 8` for equipment.

### Three behavioral categories (decided in `logic/items.asm > ChkTakeItem`)
1. **Weapons** (IDs 1–7) → go into the 7-slot `Weapons` array; picking a duplicate adds
   ammo. First weapon picked is auto-selected (unless it's the grenade launcher).
2. **Consumables / ammo** (`AMMO_CRATE`, `RATION`, `PLASTIC_BOMB`, `LAND_MINE`, `MISSILE`)
   → increment a counter, capped by `MaxAmmo*` / `MaxRations`.
3. **Equipment & cards** (9h–20h) → go into the 25-slot `Equipment` array; each also sets a
   one-byte "taken" flag (`Card1Taken`…`UniformTaken`, etc.).

Special cases: `AMMO_CRATE` tops up *all* gun ammo at once; `BAG`(22h) **recovers your whole
loadout** after you've been captured and adds the transmitter; `SUPRESSOR`(8) goes to its
own slot (`InvSupressor`); `CARDBOARD_BOX`(21h) lets you hide (truck/lorry transport).

### Pickup mechanic
`ChkTakeItems` runs every frame in `CommonLogic`. It walks the up-to-3 `ItemsInTheRoom`
entries and, if Snake's X/Y is within the item's radius, calls `ChkTakeItem` → adds it,
plays SFX `24h`, erases it from the room, and (Japanese only) shows a description text.

---

## 2. Master object table

Pickup IDs from `enum ITEMS`. "Selected" from `enum SELECTED_ITEM`.

| ID | Name | Category | What it's for |
|----:|------|----------|---------------|
| 01 | `HAND_GUN` | Weapon | Default firearm. **Only safe weapon vs. Coward Duck's hostages.** |
| 02 | `SUB_MACHINE_GUN` | Weapon | Rapid fire (burst). |
| 03 | `GRENADE_LAUNCHER` | Weapon | **Required to kill Hind-D** (room 50). |
| 04 | `ROCKET_LAUNCHER` | Weapon | Heavy/armored targets. |
| 05 | `PLASTIC_BOMB` | Weapon/consumable | Plant & detonate. **Breaks basement walls; destroys Metal Gear.** |
| 06 | `LAND_MINE` | Weapon/consumable | Lay mines. **Required to kill the Tank** (room 67). |
| 07 | `MISSILE` | Weapon/consumable | Remote-control missile. **Kills Machine Gun Kid (room 20) & the power-supply box (room 37).** |
| 08 | `SUPRESSOR` | Equip (special) | Silences shots so firing doesn't raise the alarm. Often a drop. |
| 09 | `ARMOR` | Equipment | Reduces damage taken. |
| 0A | `BOMB_SUIT` | Equipment | **Survive the rooftop "wind barrier" / blast areas** (hint rooms 53). |
| 0B | `FLASH_LIGHT` | Equipment | **See in dark/blackout rooms** (hint rooms 93/123). |
| 0C | `GOGGLES` | Equipment | Infra-red goggles — see in specific dark areas. |
| 0D | `GAS_MASK` | Equipment | **Survive gas-filled rooms** (hint room 29). |
| 0E | `CIGARS` | Equipment | Reveals infra-red trip-beams; **extends the escape timer** at the end (room 119 hint). |
| 0F | `MINE_DETECTOR` | Equipment | Reveals buried enemy mines. |
| 10 | `ANTENNA` | Equipment | **Extends radio range** — required to contact people in high `MapZone`s. Picking it forces a pending incoming call. |
| 11 | `BINOCULARS` | Equipment | Scout adjacent area (`GAME_MODE_BINOCULARS`). |
| 12 | `OXYGEN` | Equipment | **Breathe in the underwater channel** between buildings 2↔3 (hint room 115). |
| 13 | `COMPASS` | Equipment | **Navigate the pitch-black maze rooms** (hint rooms 82/202; door opened by Jennifer). |
| 14 | `PARACHUTE` | Equipment | **Survive the jump off the roof / courtyard drop** (hint room 45). |
| 15 | `ANTIDOTE` | Equipment | **Cure scorpion venom** (`Poisoned`); hint room 102. |
| 16–1D | `CARD1`…`CARD8` | Key (card) | **Open colored doors.** Each card opens its matching door type. See §4. |
| 1E | `RATION` | Consumable | Restores `Life`; +5 per pickup. Carry for damage rooms (room 116 hint). |
| 1F | `TRANSMITTER` | Equipment | The bug/transceiver returned with your gear `BAG`. |
| 20 | `UNIFORM` | Equipment | **Disguise** — desert guards open Building 2's door for you (hint room 69). |
| 21 | `CARDBOARD_BOX` | Equipment | Hide inside; used to ride lorries between zones. Can't open doors while boxed. |
| 22 | `BAG` | Special | Your **confiscated equipment**, hidden after capture — recovers everything (rooms 54/58). |
| 23 | `AMMO_CRATE` | Consumable | Refills ammo for **all** owned guns at once. |

> Names as shown in the HUD are in `data/itemnames.asm` (`ARMOR`, `SUIT`, `LIGHT`,
> `GOGGL`, `MASK`, `CIGAL`, `DETEC`, `ANTEN`, `SCOPE`, `BOMBE`, `COMPAS`, `PARAC`,
> `ANTID`, `CARD1`…`CARD8`, `RATIO`, `TRANS`, `UNIFO`, `BOX`).

---

## 3. Where objects are (decoded room → item map)

> ⚠️ **Corrected 2026-06-20.** Items are indexed **`idxRoomItemsIdx[room − 122]`**
> (`logic/addroomitems.asm`: `cp 122 / ret c`, `cp 218 / ret nc` → only rooms **122–217**
> can hold items). The earlier table here listed the *table slot* as the room and was wrong
> by +122 (it claimed "Gas Mask = room 16"; it is actually **room 138**). Verified with
> `tools/mgmap.py`: all 48 item rooms are door destinations.

**Architecture this reveals:** the world has two kinds of rooms.
* **Open grid, rooms 0–121** — the navigable corridors/exteriors wired by
  `data/roomsconnections.asm`. These hold **enemies but no static items** (combat happens
  here: Machine Gun Kid r20, Hind-D r50, Tank r67, power box r37, Metal Gear r118).
* **Door rooms, rooms 122–217** — small interior rooms you enter **through a door**
  (`DEST_ROOM`); this is where **every pickup item lives**. (Room ≥218 is guarded out, so the
  slot-96 ration in room 218 is dead data and never loads.)

Derived from `idxRoomItemsIdx` (room−122 → set#) × `idxRoomItems` (set# → contents). Exact
(Y,X) coords and multi-item sets are in `data/itemsinrooms.asm`.

| Room | Object(s) | Set |
|------|-----------|-----|
| 122 | **Card 3** + Ammo | ItemCard3 |
| 126 | Ration | ItemRation |
| 127 | **Card 1** | ItemCard1 |
| 128 | **Binoculars** | ItemBinoculars |
| 130 | **Hand Gun** | ItemGun |
| 132 | Land Mine | ItemMines |
| 135 | **Card 4** | ItemCard4 |
| 137 | **Sub-Machine Gun** | ItemSMG |
| 138 | **Gas Mask** | ItemGasMask |
| 139 | **IR Goggles** | ItemGoggles |
| 140 | Land Mine | ItemMines2 |
| 142 | **Plastic Bomb** + Ammo | ItemPBombAmmo |
| 143 | **Parachute** | ItemParachute |
| 147 | **Missile** | ItemMissile |
| 149 | Ammo crate | ItemAmmo |
| 151 | **Grenade Launcher** | ItemGrenade |
| 153 | Plastic Bomb | ItemPBomb3 |
| 156 | **Cardboard Box** | ItemBox |
| 157 | **Card 2** | ItemCard2 |
| 158 | Ration | ItemRation3 (shared; was ItemRation4, RATION@4820h) |
| 160 | **Mine Detector** | ItemMineDetect |
| 162 | Ammo crate | ItemAmmo2 |
| 163 | **Missile** (2nd) | ItemMissile (shared; was ItemMissile2, MISSILE@4820h) |
| 168 | **BAG (your gear)** | ItemBag — recover after capture |
| 169 | **Uniform** | ItemUniform |
| 170 | **Bomb-Blast Suit** | ItemBombSuit |
| 171 | **Armor** | ItemArmor |
| 172 | Ammo + Plastic Bomb | ItemPBombAmmo2 |
| 174 | Plastic Bomb | ItemPBomb2 |
| 175 | Ration | ItemRation2 |
| 176 | **Flashlight** | ItemFlashLight |
| 177 | Mine + Ammo + **Uniform** | ItemUniMineAmm |
| 178 | **Antenna** | ItemAntenna |
| 179 | **Plastic Bomb** | ItemPBomb |
| 181 | Ammo ×3 | ItemAmmox3 |
| 183 | **Antidote** | ItemAntidote |
| 184 | **Compass** | ItemCompass — door opened by Jennifer |
| 185 | **Rocket Launcher** | ItemRocket |
| 187 | **Card 5** + Ammo | ItemCard5Ammo |
| 188 | **Card 6** | ItemCard6 |
| 191 | Plastic Bomb + Ammo + Ration | ItemBombAmmRat |
| 192 | Ammo ×2 | ItemAmmox2 |
| 196 | Ammo ×2 | ItemAmmox2_ |
| 197 | Ration | ItemRation4 |
| 200 | **Oxygen Tank** | ItemOxygen — water channel |
| 214 | Ammo crate | ItemAmmo2 |
| 216 | Ammo ×2 | ItemAmmox2_ |
| ~~218~~ | ~~Ration~~ | dead (room ≥218 never loads items) |

The full authoritative list — precise coordinates and multi-item ordering — is
`data/itemsinrooms.asm`; regenerate this table any time with `python tools/mgmap.py`.

---

## 4. The card → door system (progression keys)

Cards are the primary **gating mechanism**. A door declares an "open-logic" type
(`IdDoorsLogic` in `data/doors.asm`); when Snake faces it in the right direction and has the
matching card **selected**, it opens (`logic/doors/opendoor.asm`).

| Selected item | Opens door type | Roughly where it gates |
|---------------|-----------------|------------------------|
| `CARD1` | `ChkCard1` | Early Building 1 doors |
| `CARD2` | `ChkCard2` | Building 1 |
| `CARD3` | `ChkCard3` | Building 1 |
| `CARD4` | `ChkCard4` | Building 1 / desert |
| `CARD5` | `ChkCard5` | Building 2 |
| `CARD6` | `ChkCard6` | Building 2 |
| `CARD7` | `ChkCard7` | Building 2/3 — **a dropped item** (`SPAWN_CARD7`) |
| `CARD8` | `ChkCard8` | Late game — **dropped by Coward Duck**, room 193 |

Other (non-card) door logics, for completeness: `ChkElevatorDoor`, `ChkPunchDoor`
(punch open — Shot Gunner's door), `ChkDesertDoorBuild2` (opens automatically when wearing
the **Uniform**), `ChkCompassDoor` (Jennifer opens it: `JeniOpenDoorF`), `ChkBigBossDoor`
(opens after Big Boss / for the escape: `OpenBigBossDoor`), `ChkPrisonWalls` (punch through
cell walls — Snake's & Grey Fox's), `ChkBasementWall` (blow open with a **Plastic Bomb**).

Full door-by-door details: [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md).

---

## 5. Dropped / spawned objects

Some objects don't sit in the world — enemies drop them, or they're hidden behind walls.
`logic/spawnitem.asm` (`enum SPAWN`) handles 5 droppable items:

| Spawn # | Item | Source |
|--------:|------|--------|
| 0 | `RATION` | Killed guards (random) |
| 1 | `AMMO_CRATE` | Killed guards (random) |
| 2 | `CARD7` | A specific enemy drop |
| 3 | `CARD8` | **Coward Duck** (room 193) |
| 4 | `SUPRESSOR` | A specific enemy drop |

Only one spawned item can exist at a time (`SpawnedItems` flag), and only if the room has no
other active item. Hidden items (oxygen, gear bag, some cards) live **behind breakable
walls** — punch suspicious walls or blow them with plastic bombs (radio rooms 54/58/115).

---

## 6. The critical-path object checklist

The minimum objects you *must* obtain to finish the game, in dependency order:

(Pickup-room numbers below are the door rooms 122+; the boss/usage rooms in **bold** are
open-grid rooms.)

1. **An I.D. Card** (Card 1 in room 127) → open the first locked doors.
2. **Grenade Launcher** (151) → kill **Hind-D** (50).
3. **Mines** (132/140) → kill the **Tank** (67).
4. **Missile** (147/163) → kill **Machine Gun Kid** (20) and the **power-supply box** (37).
5. **Gas Mask** (138) → cross gas rooms; **Bomb Suit** (170) → rooftop barrier.
6. **Uniform** (169/177) → pass the desert into **Building 2** (room 69/73).
7. **Compass** (184) + **Flashlight** (176) / **Goggles** (139) → the dark maze rooms.
8. **Cards 5–8** (Card 5 r187, Card 6 r188) → deeper Building 2/3 doors (Card 8 from
   **Coward Duck**, 193).
9. **Oxygen** (200) → the **water channel** to Building 3.
10. **Plastic Bombs** (142/153/172/174/179/191) → blast basement walls and finally
    **destroy Metal Gear** (118).
11. **Cigarettes** (hint 119) → extend the **self-destruct timer** for the escape after Big Boss.
