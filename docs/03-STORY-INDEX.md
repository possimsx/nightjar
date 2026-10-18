# 03 — Game Story / History Index

This is the **narrative spine** of Metal Gear, reconstructed from the radio-call script
(`data/radiocalls.asm`), the text table (`data/texts.asm`), the boss placements
(`data/actorsinrooms.asm`) and the event logic. Use it to understand *what story each room
tells* and *in what order the player experiences it*.

> How the story is delivered: almost entirely through the **radio/transceiver**. Each room
> can have a list of callers (`idxRoomRadio` → `RadioRoom_xxx`). A caller either
> **auto-replies** (speaks as soon as you tune the right frequency / enter the room) or is a
> **wait-call** (only answers when *you* call them). The byte flags are decoded in
> [02-ARCHITECTURE.md](02-ARCHITECTURE.md) and `data/radiocalls.asm`'s header.

---

## Premise

**OPERATION INTRUDE N313.** Solid Snake, rookie of the special-forces unit **FOXHOUND**, is
air-dropped near the fortified state of **Outer Heaven**. His mission, radioed by commander
**Big Boss**: infiltrate the fortress, rescue the captured operative **Grey Fox**, and learn
what Grey Fox's last transmission — *"METAL GEAR"* — means. It turns out to be a walking
nuclear battle tank. Snake must destroy it and topple Outer Heaven.

The twist (revealed late): **Big Boss himself is the leader of Outer Heaven**, feeding Snake
misdirection over the radio the whole time.

## Cast & radio frequencies

| Who | Role | Freq (`Enums.asm`) |
|-----|------|--------------------|
| **Big Boss** | FOXHOUND commander (secretly the enemy leader) | `FREQ_BIGBOSS` 85, `FREQ_BIGBOSS_BUILDING2` 13h |
| **Grey Fox** | Captured FOXHOUND operative you must rescue | (found in cell, room 164) |
| **Schneider** | Leader of the Outer Heaven resistance; your main informant | `FREQ_SCHNEIDER` 79, `FREQ_SCHNEIDER_BUILDING2` 26h |
| **Diane** | Resistance member; boss-weakness hints | `FREQ_DIANE` 33h, `FREQ_DIANE_BUILDING2` 91h |
| **Jennifer** | Resistance ally; opens doors, supplies gear | `FREQ_JENIFFER` 48h |
| **Dr. Pettrovich Madnar** | Kidnapped scientist, designer of Metal Gear | (found, room 182) |
| **Ellen / prisoners** | Hostages (incl. Jennifer's brother) | — |
| News broadcast | Flavor (FOXHOUND / galzburg report) | `FREQ_NEWS` 77 |

---

## Act-by-act progression

The world is three buildings plus outdoor desert, water channel, and basements. Story
beats below are in roughly the order a player meets them; **room IDs are the in-engine room
numbers** (see [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md)).

### Act 1 — Building 1: getting a foothold
| Room | Beat (radio caller → message) |
|------|-------------------------------|
| 0 / 1 / 4 | **Big Boss (intro):** "Gain access to Outer Heaven. Don't be discovered." **Schneider** introduces himself, says to contact him on 12079 for fortress details. |
| 5 | **Big Boss:** "Take the weapons & equipment from the enemy's lorry — you need an I.D. card to open the door." (teaches the card/door system) |
| 20 | **Diane:** "Machine Gun Kid must be killed by **remote-control missile**." → **BOSS: Machine Gun Kid.** |
| 28 | **Big Boss:** "There must be resistance — contact them with the transceiver." (teaches calling) |
| 29 | **Big Boss/Schneider:** "Put on a **gas mask** in the gas room — it's in the south of floor 1." |
| 37 | **Big Boss/Schneider:** "Break the **power-supply box** with the remote-control missile to kill the high-voltage floor. The missile is in the southeast." |
| 50 | **Diane:** "Beat **Hind-D** with a **grenade launcher**." → **BOSS: Hind-D helicopter.** |
| 53 | **Big Boss/Schneider:** "A wind barrier covers the rooftop; find the **bomb-blast suit** (it's in the basement)." |
| 57 | **BOSS: Shot Gunner** (a door is broken open by punching). |

### Act 2 — capture, prison, Grey Fox
| Room | Beat |
|------|------|
| (capture) | If caught, Snake is stripped of gear and thrown in a **prison cell** (`logic/capturescene.asm`, `GAME_MODE_CAPTURED`). |
| 54 / 58 | **Big Boss:** "Take back your gear and escape — it's hidden in a room, punch around to find it." **Schneider:** "Punch walls and bomb hollow-sounding areas." (the bag with your equipment is `BAG`/`ID 22h`) |
| 165 | **Big Boss:** "Infiltration successful. Find **Grey Fox's cell** — CHECK THE WALL!" |
| 164 | **Grey Fox** (rescued from cell after breaking the wall): warns the enemy is building **Metal Gear**, a nuclear tank, and that the boss is someone you know. |

### Act 3 — the desert & Building 2
| Room | Beat |
|------|------|
| 67 | **Diane:** "Beat the **tank** with **mines**." → **BOSS: Tank.** |
| 69 | **Big Boss (checkpoint):** "Put on an **enemy's uniform** to pass." **Schneider:** "Uniform is in the basement of Building 1." Future contact moves to building-2 frequencies. → **Desert Security** guards. |
| 71 | **BOSS: Bulldozer.** |
| 82 / 202 | **Schneider:** "The **compass** is on floor 2." (needed for the dark/blackout rooms) |
| 83 | **Diane:** "The **Arnolds** guarding the doors can't be destroyed — LEAVE!" → invincible **Arnold** guards. |
| 86 / 87 | **Jennifer:** "I'm preparing a **rocket launcher** for you." / "I'm opening the door." (she opens the compass-room door, `JeniOpenDoorF`) |
| 93 / 123 | **Schneider:** "The **flashlight** is on floor 1." **Diane:** "Be careful of pitfalls." |
| 95 | **BOSS: Fire Trooper** (flamethrower). |
| 99 | **Schneider:** "There's a gassy area in there." |
| 102 / 103 | **Diane:** "Use **antidote** for scorpion venom." → **BOSS: Scorpions.** |

### Act 4 — Building 3, the false ending, Madnar
| Room | Beat |
|------|------|
| 104 | **Big Boss:** "Creep into the lorry on the right side." (truck transport puzzle) |
| 108 | **Big Boss:** "Go into the left door!" **Jennifer:** "Destroy the wall!!" (Big Boss is now actively misleading you) |
| 111 | **Big Boss:** *"Mission over, return now. THAT'S AN ORDER!! TURN OFF THE MSX!!"* — the famous **fake-out**; obeying does nothing good. **Jennifer:** the real hint — "the card that opens the door ahead is in the east of Building 3; that area connects to Building 2 via the water channel." (`SwitchOffMSXF` event, `logic/madnarbigbossevent.asm`) |
| 115 | **Jennifer:** "An **oxygen tank** is behind the wall." (needed for the water channel) |
| 116 | **Jennifer:** "Just run — you'll be OK with **rations**." |
| 182 | **Schneider:** "A secret passage leads from the SW basement to Building 1." → **Dr. Madnar** found. He helps if rescued; note the `MadnarMoved`/"it's too late" event (room 113/133). |
| 189 | **Fake Madnar** — an impostor/booby trap. |
| 192 | **Schneider:** "The Boss of Outer Heaven was revealed! It's… *…AH!*" — **Schneider is captured mid-sentence** (`SchneiderCaptured`). |
| 193 | **Jennifer:** "**Coward Duck has Card 8.** My big brother is a hostage — don't kill him, or I won't help you!" **Diane:** "A **handgun** beats Coward Duck without killing the prisoners." → **BOSS: Coward Duck** (+ 3 prisoners human shields). |

### Act 5 — Metal Gear & Big Boss
| Room | Beat |
|------|------|
| 118 | **BOSS: METAL GEAR.** Destroy it by planting plastic bombs on its parts. Destroying it sets `MetalGear_KO` and starts the **self-destruct countdown** (`logic/destructiontimer.asm`). |
| 119 | **Diane:** "I don't know how to destroy Big Boss — it's up to you, Solid Snake… the way I feel about you… good luck." **Jennifer:** "Use a **cigarette** to extend the timer. Return alive!" → **FINAL BOSS: Big Boss.** The reveal — your own commander is the enemy. |
| (escape) | After Big Boss falls, `OpenBigBossDoor` opens the route to the **escape ladders**; race the destruction timer out of the collapsing fortress. `LeavedOuterHeaven` marks success → **Ending** (`GameStatus 8`, `logic/ending.asm`). |

---

## Boss / named-actor location table

| Room | Actor (`Enums.asm`) | How to beat / role | KO flag |
|------|---------------------|--------------------|---------|
| 20 | `ID_MACH_GUN_KID` | Remote-control **missile** | `MachGunStatus` |
| 50 | `ID_HIND_D` | **Grenade launcher** | `BossHindD_KO` |
| 57 | `ID_SHOT_GUNNER` | Combat; door punched open | `ShotGunnerStat` |
| 67 | `ID_TANK` | **Mines** | `BossTank_KO` |
| 71 | `ID_BULLDOZER` | Combat | `Bulldozer_KO` |
| 83 | `ID_ARNOLD` ×2 | **Cannot be killed** — avoid | — |
| 95 | `ID_FIRE_TROOPER` | Combat (fire-resistant gear helps) | `FireTrooper_KO` |
| 102/103/208/209 | `ID_SCORPION` ×6 | Combat; carry **antidote** | — |
| 164 | `ID_GREY_FOX` | Rescue (break cell wall) | `PrisonWall2Life` |
| 167 | `ID_ELLEN` | Hostage/NPC | — |
| 182 | `ID_MADNAR` | Rescue scientist | `MadnarMoved` |
| 189 | `ID_FAKE_MADNAR` | Impostor trap | — |
| 193 | `ID_COWARD_DUCK` (+`ID_PRISONER1`×3) | **Handgun only** (spare hostages); drops **Card 8** | `CowardDuckSpeech` |
| 118 | `ID_METAL_GEAR` | **Plastic bombs** on its parts | `MetalGear_KO` |
| 119 | `ID_BIG_BOSS` | Final fight | `BigBossStat` |

(Also: `ID_SENTINEL` patrolling guards in many rooms; `ID_DESERT_SECURITY` at room 69.)

---

## Intro & ending (story bookends)

* **Intro** (`logic/introscene.asm`, `GS_*`): the air-drop / infiltration scene; text
  `txtOpIntrude` = "OPERATION INTRUDE N313", `txtMission` = the mission briefing.
* **Ending** (`logic/ending.asm`, `GameStatus 8`): after Big Boss is destroyed and Snake
  escapes (`LeavedOuterHeaven`), the staff-roll plays. Key texts: `txtBossRevealed` (138),
  `txtBigBossConf` (147, Big Boss's confession), `txtN313End` (155), `txtStaff` (45, the
  credit roll with the dev names).

> **For reworking the story:** every line above is just two bytes in `data/radiocalls.asm`
> (caller-flags + text-ID) plus a string in `data/texts.asm`, indexed by room. You can
> rewrite the entire plot without touching a single line of Z80 — see
> [06-REWORK-GUIDE.md](06-REWORK-GUIDE.md).
