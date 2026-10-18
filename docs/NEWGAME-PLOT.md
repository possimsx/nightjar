# NIGHTJAR — Story Bible & Plot Foundation

> **This is the master plot document for the new game.** It replaces Metal Gear's story
> entirely while keeping the proven *engine shape* (top-down stealth infiltration of a
> multi-zone fortress, radio-guided, key-card/equipment gating, one-tool-per-boss design,
> capture & rescue beats, a colossal final machine, a traitor-handler twist, and a
> self-destruct escape). Every beat here is designed to drop onto the existing engine — see
> the **Engine Mapping** section and cross-references to
> [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md), [05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md),
> and [06-REWORK-GUIDE.md](06-REWORK-GUIDE.md).

---

## 1. Logline

A lone operative is sent to destroy an autonomous war-machine inside an impregnable sea
fortress — only to discover the machine is real, the people he was sent to "rescue" are
witnesses he was sent to bury, and the commander in his ear built all of it.

## 2. Premise

It is the near future. National armies have been quietly outsourced to private military
combines. The largest, **The Concord**, has gone dark on its contracts and fortified
**Halcyon Reach** — a chain of artificial islands and salvaged sea-rigs off a desert coast,
in waters no nation will claim. Intercepts say The Concord has built **AZRAEL**: an
AI-piloted siege walker carrying a *hijack uplink*. If AZRAEL broadcasts, every networked
drone, missile grid, and automated defense on the planet will answer to The Concord. They
won't need an army. They'll own everyone else's.

The covert outfit **NIGHTJAR** inserts a single agent — codename **KESTREL** — onto the
Reach with three orders from Director **Saul Crane** (call sign **WARDEN**):

1. Confirm AZRAEL exists.
2. Find and extract the missing NIGHTJAR agent, **Cole Marsh** (codename **GRAVE**).
3. Destroy AZRAEL before it goes online.

KESTREL goes in with a sidearm and nothing else. Everything — weapons, access, the truth —
has to be taken from the fortress itself.

## 3. The twists (the engine of the story)

* **Twist I — the handler is the architect.** NIGHTJAR is a shell. Director Crane *designed*
  AZRAEL; the "mission" is cover to field-test the Citadel's defenses and erase the only
  people who could expose him — including KESTREL. Mid-game, once KESTREL has served his
  purpose, WARDEN's radio orders turn from guidance to disposal: *"Operation's burned.
  Trigger your transponder's self-wipe and go dark. That's an order."* Obeying does nothing
  but strand you. (Maps to the original "turn off your console" trap.)
* **Twist II — the rescue is a trap, twice.** The scientist you're told to find, **Dr. Elias
  Roth** (AZRAEL's coerced architect), first appears as a **Concord double** — a planted
  impostor who leads you into a kill-box. The **real** Roth, found far deeper, reveals the
  only way to kill AZRAEL *and* that Crane plans to broadcast the uplink at the exact moment
  the intrusion alarm peaks — using *your* break-in as the final live-fire security key. Your
  success is scheduled to be his trigger. You have to beat the clock he set for you.

## 4. Cast

### Player
* **KESTREL** — NIGHTJAR field operative. Identity classified even to the player. Quiet,
  capable, increasingly certain he's been lied to. (The engine "Snake" slot.)

### Voices on the radio (your support net — earn their frequencies as you go)
| Codename | Name | Role | Mirrors |
|----------|------|------|---------|
| **WARDEN** | Director Saul Crane | Your commander. Calm, fatherly — and the villain. | Big Boss |
| **RELAY** | Mara Vance | Concord systems engineer turned defector. Your main informant: maps, door logic, where gear is. | Schneider |
| **ORACLE** | Dr. Ada Lin | NIGHTJAR analyst. Reads enemy telemetry and tells you each boss's weakness. | Diane |
| **SAINT** | Joon Park | Sympathetic Concord quartermaster inside the fortress. Stashes weapons, opens a door for you. His sister is a hostage. | Jennifer |

### People in the fortress
| Who | Role | Mirrors |
|-----|------|---------|
| **GRAVE** (Cole Marsh) | KESTREL's captured partner. Found in a cell; first to say "you're being played." | Grey Fox |
| **Dr. Elias Roth** | Architect of AZRAEL's AI, held under coercion. Rescue him for AZRAEL's weakness. | Madnar |
| **"Roth" (the Double)** | Concord impostor; an ambush. | Fake Madnar |
| **Hostages** (incl. Saint's sister, **Iris**) | Civilians used as human shields. | Prisoners / Ellen |
| **Director Saul Crane / WARDEN** | Final human boss, on the command deck. | Big Boss (final) |

## 5. The world (zones)

Halcyon Reach maps onto the engine's existing zone archetypes, so room data and tilesets
can be re-skinned in place. Five macro-zones plus connective tissue:

| Zone | Theme | Engine zone it re-skins |
|------|-------|-------------------------|
| **Z1 — The Causeway & Outer Wall** | Desert coast approach + the first rig-tower. Tutorial ground: cards, comms, disguise. | Building 1 + start room |
| **The Yards** | Open desert hardstand between towers; automated cargo **skiffs** (maglev carts) ferry you across gaps. | Desert / lorries |
| **Z2 — The Drowned Quarter** | A flooded, salvaged sea-city block. A submerged **channel** links it to the next tower; lightless **sub-levels** form a maze. | Building 2 + water channel + dark rooms |
| **Z3 — The Spire (Citadel Core)** | The Concord command spire: the AI vault, **AZRAEL's hangar**, and Crane's command deck. Endgame. | Building 3 |
| **The Crown** | Exposed rooftop helipads with a kinetic wind-wall; a drop you survive only by parachute. | Roof + parachute |
| **The Bilge** | Deep flooded basement: pitch-black, pit-trapped, secret passages between towers. | Basement / dark maze |
| **Lifts & Ladders** | Internal elevators; the final emergency-ladder escape. | Elevators / escape ladders |

## 6. Act structure & critical path

Beats are listed in the order the player meets them. **Room IDs** below are the engine's
existing rooms — reuse them so connections, doors, and triggers already line up. Tie each
gate to the matching object in [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md).

### Act I — Insertion (Z1: Causeway & Outer Wall)
* KESTREL lands on the desert causeway. **WARDEN** radios the three mission orders.
* **RELAY** breaks in uninvited: she's a defector; she'll feed you the map if you survive.
  Teaches the **keycard → door** system and the **transceiver**.
* Pull your first **Access Card**, **sidearm ammo**, and an **SMG** from the outer armory.
* **ORACLE**: "The drone gunner ahead — **HOWLER** — only cracks to a **guided missile**."
  → **BOSS: HOWLER**. Then break the **power coupling** with a missile to kill an
  electrified floor (mirrors the power-supply puzzle).
* **ORACLE**: "The gunship **SHRIKE** — hit it with a **grenade launcher**." → **BOSS: SHRIKE**.
* Find the **Gas Mask** (toxic vent level) and the **Parachute** (you'll need it up top).

### Act II — Captured (Z1 lower levels / cells)
* If taken, KESTREL is stripped of gear and thrown in a **cell** (capture scene).
* **WARDEN**: "Take back your kit and press on — we hid a cache. Punch the hollow walls."
  Recover your confiscated **Kit Bag** (restores your whole loadout). **RELAY**: "Bomb the
  walls that ring hollow." → find **GRAVE**'s cell, **break the wall**, free him.
* **GRAVE**: *"AZRAEL is real. And Kestrel — the op's dirty. Watch your handler."* (Seeds
  Twist I.) → **BOSS: BREAKER**, a juggernaut who smashes a door open with you.

### Act III — Crossing The Yards (desert + skiffs)
* **ORACLE**: "The crawler **GOLIATH** — **mines**, nothing else." → **BOSS: GOLIATH**.
* **WARDEN** (checkpoint): "Wear a **Concord uniform** past the sentries." **RELAY**:
  "Uniform's in the lower armory." Future contact moves to deep-zone frequencies — you'll
  need a **Signal Booster (Antenna)** to reach anyone past here.
* **The Arbiters**: elite sentinels at the gate that **cannot be killed** — evade them.
* **SAINT** introduces himself: "I'm inside. I'll leave you a **rocket launcher**… and I'll
  open the vault door. My sister's in here — please." → **BOSS: DOZER**.

### Act IV — The Drowned Quarter (Z2 + channel + maze)
* Grab the **Compass** and **Lamp/Goggles** for the lightless sub-levels; **ORACLE**:
  "Mind the pitfalls." → **BOSS: PYRE** (flamethrower).
* **Scorpion** nests in the flooded yards; **ORACLE**: "Carry **antivenom**." → **BOSS: Scorpions**.
* Meet **"Dr. Roth"** — *the Double*. He walks you toward an ambush (Twist II, part 1).
* **SAINT**: "Get the **Rebreather** behind the wall — the **channel** floods ahead." Cross
  the submerged channel into the Spire.

### Act V — The Spire & the truth (Z3)
* **WARDEN**, cold now: *"Mission's compromised. Trigger your self-wipe and extract. That's
  a direct order."* — the trap. **SAINT** cuts in with the **real** route: "The card for the
  core door is in the east block — it runs back through the channel."
* Find the **real Dr. Roth** deep in the Bilge. He gives AZRAEL's weakness — **breaching
  charges on its three cores** — and the bombshell: Crane will **broadcast the uplink the
  instant the alarm peaks**, using your intrusion as the trigger key (Twist II, part 2).
* **RELAY**, mid-sentence, as she names the traitor on air: *"The architect is— it's— …!"*
  — **RELAY goes silent. She's been taken.** (The handler is closing the net.)
* **SAINT**: "**MAGPIE** has the master card — but he's hiding behind hostages, my sister
  among them. Use your **sidearm only**." → **BOSS: MAGPIE**, who drops the **Master Card**.

### Finale — AZRAEL, Crane, and the run
* **BOSS: AZRAEL.** Plant **breaching charges** on its three exposed cores. Its fall starts
  the Citadel's **flood/self-destruct countdown** — and there is no more saving from here.
* **ORACLE**: "I can't tell you how to beat Crane. Only you can. …Come back, Kestrel."
  **SAINT**: "A **Pulse Stim** will steady you — it buys time on the clock. *Live.*"
  → **FINAL BOSS: Director Crane / WARDEN.** The mentor, unmasked.
* With Crane down, the command override opens the **escape ladders**. Race the countdown out
  of the flooding Spire; the **Pulse Stim** stretches the timer. Reach the extraction skiff =
  you survive the Reach.

## 7. Boss roster (one tool per boss — keep this design law)

| # | Boss | What it is | Beat it with | Engine slot |
|---|------|------------|--------------|-------------|
| 1 | **HOWLER** | Autonomous gun-drone | **Guided Missile** | Machine Gun Kid |
| 2 | **SHRIKE** | Attack gunship | **Grenade Launcher** | Hind-D |
| 3 | **BREAKER** | Riot juggernaut | Close combat (punches a door open) | Shot Gunner |
| 4 | **GOLIATH** | Armored crawler | **Mines** | Tank |
| 5 | **DOZER** | Demolition rig | Heavy weapons / combat | Bulldozer |
| 6 | **PYRE** | Flamethrower trooper | Combat (fire-resist gear helps) | Fire Trooper |
| 7 | **Scorpions** | Venomous nest | Combat + **Antivenom** | Scorpions |
| – | **The Arbiters** | Invincible sentinels | **Cannot be killed — evade** | Arnold |
| 8 | **MAGPIE** | Coward behind hostages | **Sidearm only** (spare hostages); drops Master Card | Coward Duck |
| 9 | **AZRAEL** | Colossal AI siege-walker | **Breaching charges** on 3 cores | Metal Gear |
| 10 | **Director Crane / WARDEN** | The traitor commander | Final duel | Big Boss |

## 8. Key items & progression gates

Re-themed from [04-OBJECTS-INDEX.md](04-OBJECTS-INDEX.md); same mechanics, new fiction.

| New item | Re-skins | Gate it opens |
|----------|----------|---------------|
| **Access Cards I–VIII / Master Card** | Card 1–8 | Tiered Concord doors; Master Card (from MAGPIE) opens the core. |
| **Concord Uniform** | Uniform | Pass the Arbiter checkpoint into Z2. |
| **Gas Mask** | Gas Mask | Toxic vent levels. |
| **Blast/Kinetic Suit** | Bomb Suit | The rooftop wind-wall (The Crown). |
| **Rebreather** | Oxygen | The flooded channel into the Spire. |
| **Compass + Lamp** | Compass + Flashlight/Goggles | The lightless Bilge maze. |
| **Parachute** | Parachute | The Crown rooftop drop. |
| **Antivenom** | Antidote | Scorpion venom. |
| **Signal Booster** | Antenna | Radio range in deep zones (else allies are unreachable). |
| **Kit Bag** | Bag | Recover your loadout after capture. |
| **Breaching Charges** | Plastic Bomb | Blow walls; the only thing that kills AZRAEL. |
| **Stims (Rations)** | Ration | Health. |
| **Pulse Stim** | Cigarettes | Extends the final self-destruct timer. |

## 9. Themes & tone

* **Trust as a weapon.** The friendliest voice is the enemy. The story is about who you
  believe when you can't see their face.
* **A man alone against an institution.** No backup that isn't compromised; every resource
  is improvised from the enemy's own house.
* **The cost of a lie.** NIGHTJAR was never real. KESTREL ends the game with the mission
  won and his entire world revealed as a stage.
* **Tone:** lonely, tense, radio-static dread, lit by gallows humor over the comms. Quiet
  most of the time; loud when it counts.

## 10. Ending

AZRAEL is scrap. Crane is down. The Spire floods. KESTREL claws out along the ladders as
the countdown burns, **Pulse Stim** buying the last seconds, and drops onto the extraction
skiff as Halcyon Reach goes under behind him.

**ORACLE**, faint over failing comms: *"NIGHTJAR's gone, Kestrel. Officially, you never
existed."* A beat. *"…Unofficially — thank you."*

**Coda (sequel hook):** a clean Concord transmission, untouched by the destruction:
*"Reach is lost. The board has voted. Begin Halcyon Two."* Cut to black on the words
**THERE IS NO NIGHTJAR.**

---

## 11. Engine mapping (so this is buildable, not just lore)

This plot was authored to require **zero new engine systems** — only data, text, and
graphics swaps per [06-REWORK-GUIDE.md](06-REWORK-GUIDE.md). The structural beats reuse
flags that already exist:

| Story beat | Reuse this engine mechanic / flag |
|------------|-----------------------------------|
| WARDEN's "self-wipe / stand down" trap | the `SwitchOffMSXF` event (`logic/madnarbigbossevent.asm`) |
| RELAY captured mid-sentence | the Schneider-captured beat (`SchneiderCaptured`) |
| SAINT opens the core/vault door | the compass-door ally flag (`JeniOpenDoorF`, `ChkCompassDoor`) |
| Capture → cell → recover Kit Bag | capture scene + `BAG` recovery (`logic/capturescene.asm`) |
| Free GRAVE by breaking the wall | `ChkPrisonWalls` (punch-through cell walls) |
| Door to AZRAEL / escape opens after the boss | `OpenBigBossDoor` / `ChkBigBossDoor` |
| AZRAEL destroyed → countdown, no more saves | `MetalGear_KO` + `logic/destructiontimer.asm` |
| Uniform checkpoint into Z2 | `ChkDesertDoorBuild2` (uniform-opens-door) |
| "The Double" Roth ambush | the Fake-Madnar actor/event (`ID_FAKE_MADNAR`) |

**To build it:** keep the room graph and door logic from
[05-WORLD-AND-PROGRESSION.md](05-WORLD-AND-PROGRESSION.md); re-skin tiles/sprites/palettes in
`gfx/` + `data/rooms.asm`; rewrite `data/radiocalls.asm` + `data/texts.asm` to the script in
§6; rename items in `data/itemnames.asm` per §8; and set boss placements in
`data/actorsinrooms.asm` per §7. The Z80 in `Banks0123.asm` and `logic/` does not need to
change for the story to work.

> **Next step suggestion:** turn §6 into a concrete *room-by-room beat sheet* (one row per
> room ID: tileset, items, enemies, doors, radio caller + line) — that becomes the direct
> work order for editing the `data/` tables.
