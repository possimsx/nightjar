"""mgproj -- active-project resolver for all MetalGear tools.

docs/PROJECTS-PLAN.md. The repo root is the protected "Metal Gear (base)"
project; editable projects are full copies of the buildable source set in
projects/<slug>/. Every codec resolves source files through path()/root()
at call time, so the editor can retarget the whole toolchain by calling
set_root() (or activate()) -- registered cache-invalidation callbacks fire
on each switch.

Worlds (mgmap.set_world, docs/LIMITS-PLAN.md) are orthogonal: world_file()
rewrites the *relative* path, mgproj supplies the base directory.

CLI tools honour the MG_PROJECT env var (a projects/ slug or an absolute
path) so e.g. `MG_PROJECT=my-game python tools/build.py` builds a project.
"""
import os, re, json, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PROJECTS_DIRNAME = "projects"

# The buildable source set copied into each project (plus every root *.asm).
SOURCE_DIRS = ("constants", "data", "gfx", "hooks", "logic", "sound")
# build artifacts / caches never copied between projects
_SKIP_COPY = re.compile(r'\.(rom|lst|sym)$|^\.editor$', re.I)

_ROOT = REPO_ROOT
_CALLBACKS = []


# ---------------------------------------------------------------------------
# path resolution
# ---------------------------------------------------------------------------
def repo_root():
    """The git repo root = the protected Metal Gear base. Never changes."""
    return REPO_ROOT


def repo_path(rel):
    """Repo-anchored asset (tools/, room_images/, docs/) -- project-independent."""
    return os.path.join(REPO_ROOT, rel)


def root():
    """Directory of the active project's source tree."""
    return _ROOT


def path(rel):
    """Resolve a source-relative path (e.g. 'data/rooms.asm') in the active
    project. This is THE join every codec must use instead of its own ROOT."""
    return os.path.join(_ROOT, rel)


def is_base():
    return os.path.normcase(_ROOT) == os.path.normcase(REPO_ROOT)


def git_prefix():
    """Repo-relative posix prefix of the active project's files, for
    `git show HEAD:<prefix><rel>` style commands ('' for the base)."""
    if is_base():
        return ""
    return os.path.relpath(_ROOT, REPO_ROOT).replace("\\", "/") + "/"


def on_switch(cb):
    """Register a cache-invalidation callback fired after every set_root()."""
    if cb not in _CALLBACKS:
        _CALLBACKS.append(cb)


def set_root(p):
    """Point every tool at a different project source tree and drop caches."""
    global _ROOT
    p = os.path.abspath(p)
    if not os.path.isdir(p):
        raise ValueError("project dir not found: %s" % p)
    if os.path.normcase(p) != os.path.normcase(_ROOT):
        _ROOT = p
        for cb in list(_CALLBACKS):
            cb()
    return _ROOT


# ---------------------------------------------------------------------------
# per-project editor state (map.json export, cosmetic labels, reach cache).
# The base keeps its historical locations so existing workflows/gitignore
# keep working; projects consolidate under <project>/.editor/.
# ---------------------------------------------------------------------------
_STATE_LEGACY = {
    "map": os.path.join("tools", "map.json"),
    "labels": os.path.join("tools", "editor", "labels.json"),
    "reach": os.path.join("tools", "editor", ".reach_cache.json"),
    "stamps": os.path.join("tools", "editor", "stamps.json"),
}
_STATE_PROJ = {"map": "map.json", "labels": "labels.json", "reach": "reach_cache.json",
               "stamps": "stamps.json"}


def state_file(kind):
    """Absolute path of an editor state file for the active project."""
    if is_base():
        return os.path.join(REPO_ROOT, _STATE_LEGACY[kind])
    d = os.path.join(_ROOT, ".editor")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, _STATE_PROJ[kind])


# ---------------------------------------------------------------------------
# project registry
# ---------------------------------------------------------------------------
def projects_dir():
    return os.path.join(REPO_ROOT, PROJECTS_DIRNAME)


def _slugify(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not s:
        raise ValueError("project name yields empty slug: %r" % name)
    return s


def _meta_path(proj_root):
    return os.path.join(proj_root, "project.json")


def _load_meta(proj_root):
    try:
        with open(_meta_path(proj_root), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def base_entry():
    return {"slug": "base", "name": "Metal Gear (base)", "protected": True,
            "template": "base", "root": REPO_ROOT}


def list_projects():
    """Base first, then every projects/<slug>/ with a valid project.json."""
    out = [base_entry()]
    pdir = projects_dir()
    if os.path.isdir(pdir):
        for slug in sorted(os.listdir(pdir)):
            proot = os.path.join(pdir, slug)
            meta = _load_meta(proot) if os.path.isdir(proot) else None
            if meta:
                meta = dict(meta)
                meta.setdefault("slug", slug)
                meta.setdefault("protected", False)
                meta["root"] = proot
                out.append(meta)
    return out


def find(slug):
    """Project root for a slug ('base' = repo root); None if unknown."""
    for p in list_projects():
        if p["slug"] == slug:
            return p["root"]
    return None


def active_slug():
    if is_base():
        return "base"
    return os.path.basename(_ROOT)


def is_protected():
    if is_base():
        return True
    meta = _load_meta(_ROOT) or {}
    return bool(meta.get("protected"))


def _copy_source(src_root, dst_root):
    """Copy the buildable source set (root *.asm + SOURCE_DIRS), skipping
    build artifacts and editor state."""
    os.makedirs(dst_root, exist_ok=True)
    for fn in os.listdir(src_root):
        if fn.lower().endswith(".asm") and not _SKIP_COPY.search(fn):
            shutil.copy2(os.path.join(src_root, fn), os.path.join(dst_root, fn))
    for d in SOURCE_DIRS:
        sd = os.path.join(src_root, d)
        if not os.path.isdir(sd):
            continue
        shutil.copytree(
            sd, os.path.join(dst_root, d), dirs_exist_ok=True,
            ignore=lambda _dir, names: [n for n in names if _SKIP_COPY.search(n)])


def create_project(name, source="base", template="duplicate", description=""):
    """Create projects/<slug>/ as a copy of `source` (a slug). Returns meta."""
    slug = _slugify(name)
    proot = os.path.join(projects_dir(), slug)
    if os.path.exists(proot):
        raise ValueError("project '%s' already exists" % slug)
    src_root = find(source)
    if src_root is None:
        raise ValueError("unknown source project '%s'" % source)
    _copy_source(src_root, proot)
    meta = {"slug": slug, "name": name, "description": description,
            "template": template, "source": source, "protected": False,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(_meta_path(proot), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    meta["root"] = proot
    return meta


def delete_project(slug):
    """Remove a non-protected project directory (never the base)."""
    if slug == "base":
        raise ValueError("cannot delete the base")
    proot = find(slug)
    if proot is None:
        raise ValueError("unknown project '%s'" % slug)
    meta = _load_meta(proot) or {}
    if meta.get("protected"):
        raise ValueError("project '%s' is protected" % slug)
    if os.path.normcase(root()) == os.path.normcase(proot):
        raise ValueError("cannot delete the active project")
    shutil.rmtree(proot)


# ---------------------------------------------------------------------------
# active-project persistence (editor) + env override (CLI)
# ---------------------------------------------------------------------------
def _active_file():
    return os.path.join(projects_dir(), "active.json")


def save_active():
    os.makedirs(projects_dir(), exist_ok=True)
    with open(_active_file(), "w", encoding="utf-8") as f:
        json.dump({"active": active_slug()}, f)


def restore_active():
    """Editor startup: reactivate the project persisted by save_active()."""
    try:
        with open(_active_file(), encoding="utf-8") as f:
            slug = json.load(f).get("active", "base")
    except (OSError, ValueError):
        return _ROOT
    proot = find(slug)
    if proot:
        set_root(proot)
    return _ROOT


def activate(slug, persist=True):
    proot = find(slug)
    if proot is None:
        raise ValueError("unknown project '%s'" % slug)
    set_root(proot)
    if persist:
        save_active()
    return proot


def _apply_env():
    v = os.environ.get("MG_PROJECT")
    if not v:
        return
    if os.path.isabs(v):
        set_root(v)
        return
    proot = find(v)
    if proot is None:
        raise SystemExit("MG_PROJECT=%r: no such project under %s"
                         % (v, projects_dir()))
    set_root(proot)


_apply_env()
