"""mgnewgame -- generate the "blank new plot" project template.

docs/PROJECTS-PLAN.md Phase 3. Copies the pristine Metal Gear base into
projects/<slug>/, turns on WORLDBANK (full per-room connections, so the id
bands stop being remap-locked) and clears the game content through the
existing codecs (never raw text surgery), leaving an empty fortress to build a
new game in:

  undefined : EVERY plain room, and every special already reworked into an
              editable data table (hazards/respawns/hide-guards/SpecialEnemyCnt/
              capture) — its idxRooms slot is repointed at RoomUndefined so the
              map starts as a blank id space, not 200 empty frames.
  kept      : the start room 121 (byte-for-byte) plus the rooms whose behaviour
              is still nailed to a specific id by hardcoded cp <id> checks
              (KEEP_ROOMS: parachute 204, ladders 224-226, elevators 240-250,
              bosses/events 118/119/133/167/193) — KEPT WITH THEIR ORIGINAL ART
              as anchors, since if the new plot ever wants that gimmick it must
              live at this id. All are inert until a route reaches them.
  cleared   : every connection slot, door, item, actor, patrol route, radio
              trigger, hide-guard rule, respawn entry, codec gate, antenna
              room, gateway; checkpoints reduced to the room-121 start.
  intact    : ALL engine code (intro/title, specials), every tileset/sprite/
              item/weapon graphic, palette and text table.

Usage:
  python tools/mgnewgame.py <name>            create projects/<slug>/
  (the editor calls create_blank() from POST /api/projects template=blank)
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgproj, mgmap

START_ROOM = 121                      # start/insertion screen (SaveStatRooms)
# Rooms whose engine behaviour is nailed to a specific id by hardcoded cp <id>
# checks (docs/SPECIAL-ROOMS.md) and NOT reworked into a relocatable data table.
# Kept with their ORIGINAL art as anchors; every other defined room is
# undefined. (The pure-mechanic hardcodes 53/78/103 are left OUT on purpose —
# niche and inert — so the map stays genuinely blank; add them here to keep.)
PINNED_ROOMS = ({204}                 # parachute free-fall ("bricks wall")
                | set(range(224, 227))  # ladder rooms 224-226
                | set(range(240, 251)))  # elevator rooms 240-250 (pinned to 240)
BOSS_ROOMS = {118, 119, 133, 167, 193}  # Metal Gear/Big Boss/Madnar/Ellen/Coward Duck
KEEP_ROOMS = {START_ROOM} | PINNED_ROOMS | BOSS_ROOMS


def _set_worldbank(on=True):
    """Flip the WORLDBANK feature flag in the ACTIVE project's features.asm.
    WORLDBANK=1 (docs/LIMITS-PLAN.md C2) gives every room its own 4 exits and
    deletes the GetNextRoomNum remap chain, so the walkable band is no longer
    capped at 126 and freed ids can be renumbered."""
    f = mgproj.path("features.asm")
    with open(f, encoding="latin-1") as fh:
        txt = fh.read()
    txt = re.sub(r'(?m)^(WORLDBANK\s+equ\s+)\d+',
                 r'\g<1>%d' % (1 if on else 0), txt)
    with open(f, "w", encoding="latin-1") as fh:
        fh.write(txt)


def _clear_map_tables():
    """Blank the mgmap model of the ACTIVE project: keep the start room and the
    ID-locked anchors (KEEP_ROOMS) with their ORIGINAL art, undefine every other
    defined room, seal all connections, empty doors/items/actors/checkpoints.
    Writes back with regen (so idxDoors/idxActorsRooms stay consistent), then
    repoints the undefined rooms' idxRooms slots at RoomUndefined."""
    m = mgmap.load_model()
    layouts = list(m["layouts"])
    conns = [list(q) for q in m["connections"]]
    full = ([list(q) for q in m["connections_full"]]
            if m.get("connections_full") else None)

    undefine = sorted(r for r, lay in enumerate(layouts)
                      if lay is not None and r not in KEEP_ROOMS)
    # seal EVERY connection slot (255 = no exit): kept anchors become unreachable
    # islands (their parachute/elevator/ladder/boss code stays inert until the
    # designer wires a route in), the start screen stays self-contained.
    for r in range(len(conns)):
        conns[r] = [255, 255, 255, 255]
    if full:
        for r in range(len(full)):
            full[r] = [255, 255, 255, 255]

    model = dict(m,
                 layouts=layouts,                         # kept rooms: original art
                 connections=conns, connections_full=full,
                 doors={},                                # every block emptied
                 # IdDoorsLogic can be neither empty (the label must survive)
                 # nor stock (160 ids = table full, door_add would refuse):
                 # one normal-closed byte, so new doors mint ids from 2.
                 iddoorslogic=[2],
                 item_idx=[0] * len(m["item_idx"]),
                 actor_slots=["NoActorsInRoom"] * len(m["actor_slots"]),
                 actor_blocks={},
                 checkpoints=[[121, 121], [121, 0]])
    mgmap.write_model(model, regen=True)
    mgmap.undefine_rooms(undefine)
    return undefine


def _clear_radio():
    import mgradio
    idx = mgradio.parse_idx(mgradio._read(mgradio.RADIO_F))
    n = 0
    for room, lbl in enumerate(idx):
        if lbl != mgradio.NO_RADIO:
            mgradio.set_room_call(room, [])
            n += 1
    return n


def _clear_paths():
    import mgpath
    n = 0
    for room in range(mgpath.STOCK_N_ROOMS):
        try:
            if mgpath.room_paths(room).get("paths"):
                mgpath.set_room_paths(room, [])
                n += 1
        except Exception:
            pass
    return n


def _clear_hideguards():
    import mghideguard
    mghideguard.set_table({})


def _clear_respawns():
    import mgrespawn
    n = 0
    for room in range(mgrespawn.MAX_ROOM):
        try:
            e = mgrespawn.room_entry(room)
        except Exception:
            continue
        if e and e.get("enemy"):
            mgrespawn.set_entry(room, 0, 0, 0)
            n += 1
    return n


def _clear_gates():
    import mgcodecgate
    mgcodecgate.set_text_gates([])
    mgcodecgate.set_item_gates([])
    mgcodecgate.set_door_gates([])
    for room, needs in enumerate(mgcodecgate.load_antenna()):
        if needs:
            mgcodecgate.set_antenna_room(room, False)


def _clear_gateways():
    mgmap.write_gateways([])


README = """# {name}

Blank "new plot" project generated by tools/mgnewgame.py from the Metal Gear
base. The whole engine, the intro/title, all artwork (tilesets, sprites,
palettes) and every text table are intact; the game content is cleared:

* WORLDBANK is ON -- every room owns its 4 exits, so the id space is fully
  yours to renumber (no 0-125 walkable cap, no elevator/ladder remap lock)
* the map starts as a blank id space: every plain room, and every special
  already moved to an editable data table, is UNDEFINED (its idxRooms slot
  points at RoomUndefined) -- create rooms in the map editor as you design
* the start room 121 is kept byte-for-byte, with the single checkpoint
  dropping the player there and all connections sealed (255 = wall)
* the ID-locked anchor rooms are kept WITH THEIR ORIGINAL ART, because their
  behaviour is nailed to that id in engine code (parachute 204, ladders
  224-226, elevators 240-250, bosses/events 118/119/133/167/193). They are
  unreachable islands until you route the map into them -- if the new plot
  wants that gimmick, build it here; if not, undefine or repurpose the room.
* no doors, items, actors, patrol routes, radio room-triggers, hide-guard
  rules, respawn reinforcements, codec gates, antenna rooms or gateways
* all item/weapon graphics, names, sprites, tilesets, palettes and texts
  are the stock Metal Gear ones, ready to reuse or redraw

Build: activate this project in the editor (or MG_PROJECT={slug}) and use
the build button / `python tools/build.py`.
"""


def create_blank(name):
    """Copy the base into projects/<slug>/ and clear it. Returns the project
    meta dict. On any failure the half-built project dir is removed."""
    meta = mgproj.create_project(name, source="base", template="blank")
    prev = mgproj.root()
    mgproj.set_root(meta["root"])
    try:
        _set_worldbank(True)
        _clear_map_tables()
        _clear_radio()
        _clear_paths()
        _clear_hideguards()
        _clear_respawns()
        _clear_gates()
        _clear_gateways()
        with open(os.path.join(meta["root"], "README.md"), "w",
                  encoding="utf-8") as f:
            f.write(README.format(name=meta["name"], slug=meta["slug"]))
    except BaseException:
        mgproj.set_root(prev)
        import shutil
        shutil.rmtree(meta["root"], ignore_errors=True)
        raise
    return meta


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python tools/mgnewgame.py <project name>")
    meta = create_blank(sys.argv[1])
    print("blank project created: %s  (%s)" % (meta["slug"], meta["root"]))
    print("activate it: MG_PROJECT=%s  or the editor's project switcher"
          % meta["slug"])


if __name__ == "__main__":
    main()
