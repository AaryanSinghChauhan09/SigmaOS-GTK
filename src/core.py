"""GTK library toolkit for SigmaOS-GTK / GTK+ (inspired by gtk, blueman,
celluloid).

Principles: patch series are ordered data validated before application,
the theme bridge is a pure mapping table (single source of truth) with
conflict detection, dependency ordering uses deterministic topological sort
with cycle detection, wrapper generation is pure string building with shell
injection rejected at the door.
"""
import argparse, os, re, sys

ENGINE = {
    "name": "sigma-gtk",
    "summary": "GTK patch series, theme bridge, dependency order, wrappers",
    "language": "python",
    "verbs": ["patches", "theme-bridge", "deps", "wrapper-plan"],
    "principles": ["Single Source of Truth", "Plan Before Act", "Fail-Fast",
                   "Defensive Programming", "KISS", "DRY",
                   "Deterministic Testing"],
}

cli_doc = """\
$ sigma-gtk patches series --patches-dir ./patches
0001-fix-headerbar.patch  -p1  [ok]
0002-gdk-glitch.patch     -p1  [MISSING]
$ sigma-gtk theme-bridge colors.css
@define-color theme_selected_bg_color #5294e2;
$ sigma-gtk deps build-deps.txt
cairo glib gdk-pixbuf pango gtk mpv celluloid
$ sigma-gtk wrapper-plan /usr/bin/celluloid --env GTK_THEME=Mint-Y-Dark
#!/bin/sh
exec "/usr/bin/celluloid" "$@"
"""

_PATCH_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.+-]*\.patch)(?:\s+-p(\d))?$")
_COLOR_RE = re.compile(
    r"^@define-color\s+([A-Za-z0-9_]+)\s+(#[0-9a-fA-F]{3,8}|[A-Za-z]+)\s*;$")
_DEP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_DEP_LINE_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._+-]*)(?:\s*(>=|<=|=|>|<)\s*([0-9][0-9.]*))?$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHELL_NASTIES = " \n;|&$`<>(){}*?[]!~#\\\"'"
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class GtkToolkitError(ValueError):
    pass


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def parse_series(text, patches_dir=None):
    """Parse a quilt-style series file into an ordered patch list."""
    patches, seen = [], set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _PATCH_RE.match(line)
        if not m:
            raise GtkToolkitError(
                f"line {lineno}: bad series entry {line!r} "
                f"(want 'name.patch [-pN]')")
        name, level = m.group(1), int(m.group(2) or 1)
        if level > 6:
            raise GtkToolkitError(
                f"line {lineno}: strip level -p{level} out of range 0..6 "
                f"for {name!r}")
        if name in seen:
            raise GtkToolkitError(f"line {lineno}: duplicate patch {name!r}")
        seen.add(name)
        exists = None
        if patches_dir is not None:
            exists = os.path.isfile(os.path.join(patches_dir, name))
        patches.append({"name": name, "level": level, "exists": exists})
    if not patches:
        raise GtkToolkitError("series file is empty")
    return patches


# GTK4 libadwaita colour names -> GTK3/XApp theme colour names.
BRIDGE_MAP = {
    "accent_color": "theme_selected_bg_color",
    "accent_bg_color": "theme_selected_bg_color",
    "accent_fg_color": "theme_selected_fg_color",
    "window_bg_color": "theme_bg_color",
    "window_fg_color": "theme_fg_color",
    "view_bg_color": "theme_base_color",
    "view_fg_color": "theme_text_color",
    "headerbar_bg_color": "theme_bg_color",
    "card_bg_color": "theme_unfocused_bg_color",
    "destructive_color": "theme_error_color",
}


def _norm_hex(value):
    v = value.lower()
    if len(v) == 4:
        return "#" + "".join(c * 2 for c in v[1:])
    return v


def theme_bridge(colors_text):
    """Map GTK4 @define-color entries onto GTK3 theme colour names."""
    mapped, warnings, seen = {}, [], {}
    for lineno, raw in enumerate(colors_text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = _COLOR_RE.match(line)
        if not m:
            raise GtkToolkitError(f"line {lineno}: cannot parse {line!r}")
        gtk4_name, value = m.group(1), m.group(2)
        if not _HEX_RE.match(value):
            raise GtkToolkitError(f"line {lineno}: bad colour {value!r}")
        gtk3_name = BRIDGE_MAP.get(gtk4_name)
        if gtk3_name is None:
            warnings.append(f"line {lineno}: no GTK3 equivalent for "
                            f"{gtk4_name!r} (skipped)")
            continue
        hexval = _norm_hex(value)
        if gtk3_name in seen and seen[gtk3_name] != hexval:
            raise GtkToolkitError(
                f"line {lineno}: conflicting values for "
                f"{gtk3_name!r}: {seen[gtk3_name]} vs {hexval}")
        seen[gtk3_name] = hexval
        mapped[gtk3_name] = hexval
    if not mapped:
        raise GtkToolkitError("no bridgeable colours found")
    return {"mapped": mapped, "warnings": warnings,
            "lines": [f"@define-color {k} {v};" for k, v in mapped.items()]}


DEP_GRAPH = {
    "cairo": [],
    "glib": [],
    "pango": ["glib", "cairo"],
    "gdk-pixbuf": ["glib"],
    "gtk": ["glib", "pango", "gdk-pixbuf", "cairo"],
    "xapp": ["gtk", "glib"],
    "mpv": ["glib"],
    "blueman": ["gtk", "glib"],
    "celluloid": ["gtk", "mpv"],
}


def parse_deps(text, graph=DEP_GRAPH):
    """Parse dependency lines, then topologically order the closure."""
    roots, seen = [], set()
    constraints = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _DEP_LINE_RE.match(line)
        if not m:
            raise GtkToolkitError(f"line {lineno}: bad dependency {line!r}")
        name = m.group(1)
        if name in seen:
            raise GtkToolkitError(f"line {lineno}: duplicate dependency "
                                  f"{name!r}")
        seen.add(name)
        if m.group(2):
            constraints[name] = m.group(2) + m.group(3)
        roots.append(name)
    if not roots:
        raise GtkToolkitError("dependency list is empty")
    # closure over the graph (unknown names are treated as leaves)
    wanted = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in wanted:
            continue
        wanted.add(name)
        stack.extend(graph.get(name, []))
    # Kahn's algorithm with sorted tie-break -> deterministic order
    remaining = set(wanted)
    order = []
    while remaining:
        ready = sorted(n for n in remaining
                       if not (set(graph.get(n, [])) & remaining))
        if not ready:
            raise GtkToolkitError("dependency cycle involving: " +
                                  ", ".join(sorted(remaining)))
        pick = ready[0]
        remaining.remove(pick)
        order.append(pick)
    return {"order": order, "constraints": constraints, "roots": roots}


def wrapper_plan(binary, env=None, args=()):
    """Generate a shell wrapper; refuses shell metacharacters outright."""
    if not binary or any(c in _SHELL_NASTIES for c in binary):
        raise GtkToolkitError(f"unsafe binary path: {binary!r}")
    env = env or {}
    exports = []
    for key in sorted(env):
        if not _ENV_KEY_RE.match(key):
            raise GtkToolkitError(f"bad env var name: {key!r}")
        value = str(env[key])
        if any(c in value for c in "\n\x00\\\""):
            raise GtkToolkitError(f"unsafe value for {key!r}")
        exports.append(f'export {key}="{value}"')
    extra_parts = []
    for a in args:
        if any(c in a for c in "\n\x00\\\""):
            raise GtkToolkitError(f"unsafe wrapper arg: {a!r}")
        extra_parts.append(f'"{a}"')
    extra = " ".join(extra_parts)
    script_lines = ["#!/bin/sh",
                    "# generated by sigma-gtk; edits will be overwritten"]
    script_lines.extend(exports)
    tail = f'"{binary}" {extra}'.rstrip() if extra else f'"{binary}"'
    script_lines.append(f'exec {tail} "$@"')
    return "\n".join(script_lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("patches", help="list a patch series")
    pa.add_argument("series_file")
    pa.add_argument("--patches-dir", default=None)
    tb = sub.add_parser("theme-bridge", help="GTK4 -> GTK3 colour bridge")
    tb.add_argument("colors_file")
    dp = sub.add_parser("deps", help="topologically order dependencies")
    dp.add_argument("deps_file")
    wp = sub.add_parser("wrapper-plan", help="generate a launcher wrapper")
    wp.add_argument("binary")
    wp.add_argument("--env", action="append", default=[], metavar="K=V")
    wp.add_argument("--arg", action="append", default=[], dest="args")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "patches":
            patches = parse_series(_read(args.series_file),
                                   patches_dir=args.patches_dir)
            missing = 0
            for i, patch in enumerate(patches, 1):
                flag = ""
                if patch["exists"] is not None:
                    flag = "  [ok]" if patch["exists"] else "  [MISSING]"
                    missing += 0 if patch["exists"] else 1
                print(f"{i:03d} {patch['name']:<34} "
                      f"-p{patch['level']}{flag}")
            if missing:
                print(f"{missing} patch(es) missing", file=sys.stderr)
                return 1
        elif args.cmd == "theme-bridge":
            plan = theme_bridge(_read(args.colors_file))
            for line in plan["lines"]:
                print(line)
            for warning in plan["warnings"]:
                print(f"# {warning}", file=sys.stderr)
        elif args.cmd == "deps":
            plan = parse_deps(_read(args.deps_file))
            print(" ".join(plan["order"]))
        elif args.cmd == "wrapper-plan":
            env = {}
            for spec in args.env:
                if "=" not in spec:
                    raise GtkToolkitError(f"--env needs K=V, got {spec!r}")
                key, _, value = spec.partition("=")
                env[key] = value
            print(wrapper_plan(args.binary, env=env, args=args.args),
                  end="")
        return 0
    except (GtkToolkitError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile
    # --- patch series -------------------------------------------------------
    series = ("# series\n"
              "0001-fix-headerbar.patch -p1\n"
              "0002-gdk-glitch.patch\n"
              "\n")
    patches = parse_series(series)
    assert [(p["name"], p["level"]) for p in patches] == \
        [("0001-fix-headerbar.patch", 1), ("0002-gdk-glitch.patch", 1)]
    for bad in ("notes.txt\n", "0001-x.patch -p9\n", "0001-x.patch -p\n",
                "dup.patch\ndup.patch\n", "# empty\n"):
        try:
            parse_series(bad)
        except GtkToolkitError:
            pass
        else:
            raise AssertionError(f"series accepted: {bad!r}")
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "0001-fix-headerbar.patch"), "w").close()
        patches = parse_series(series, patches_dir=d)
        assert [p["exists"] for p in patches] == [True, False]

    # --- theme bridge -------------------------------------------------------
    plan = theme_bridge("@define-color accent_color #5294e2;\n"
                        "@define-color window_bg_color #1e1e2e;\n"
                        "@define-color view_bg_color #fff;\n"
                        "@define-color experimental_zazz #123456;\n")
    assert plan["mapped"] == {
        "theme_selected_bg_color": "#5294e2",
        "theme_bg_color": "#1e1e2e",
        "theme_base_color": "#ffffff",
    }
    assert len(plan["warnings"]) == 1 and "experimental_zazz" in \
        plan["warnings"][0]
    assert plan["lines"][0] == \
        "@define-color theme_selected_bg_color #5294e2;"
    try:
        theme_bridge("@define-color accent_color #5294e2;\n"
                     "@define-color window_bg_color #aaaaaa;\n"
                     "@define-color headerbar_bg_color #bbbbbb;\n")
    except GtkToolkitError as e:
        assert "conflicting values for 'theme_bg_color'" in str(e)
    else:
        raise AssertionError("conflicting bridge accepted")
    for bad in ("@define-color accent_color #zzzzzz;\n",
                "@define-color accent_color notacolour;\n",
                "just words\n",
                "// nothing real\n"):
        try:
            theme_bridge(bad)
        except GtkToolkitError:
            pass
        else:
            raise AssertionError(f"bridge accepted: {bad!r}")

    # --- dependency ordering ------------------------------------------------
    plan = parse_deps("gtk>=3.24\nglib>=2.70\npango\ncelluloid\n")
    # Kahn + sorted tie-break: cairo,glib first; then gdk-pixbuf,mpv;
    # then pango, gtk, celluloid
    assert plan["order"] == ["cairo", "glib", "gdk-pixbuf", "mpv", "pango",
                             "gtk", "celluloid"], plan["order"]
    assert plan["constraints"] == {"gtk": ">=3.24", "glib": ">=2.70"}
    assert parse_deps("xapp\n")["order"] == ["cairo", "glib", "gdk-pixbuf",
                                             "pango", "gtk", "xapp"]
    cyclic = {"a": ["b"], "b": ["a"]}
    for bad, frag in ((lambda: parse_deps("a\n", graph=cyclic), "cycle"),
                      (lambda: parse_deps("dup\ndup\n"), "duplicate"),
                      (lambda: parse_deps("bad name\n"), "bad dependency"),
                      (lambda: parse_deps("# none\n"), "empty"),
                      (lambda: parse_deps("a b c\n"), "bad dependency")):
        try:
            bad()
        except GtkToolkitError as e:
            assert frag in str(e), (frag, str(e))
        else:
            raise AssertionError(f"deps accepted: {frag}")

    # --- wrapper plan -------------------------------------------------------
    script = wrapper_plan("/usr/bin/celluloid",
                          env={"GTK_THEME": "Mint-Y-Dark", "LC_ALL": "C"},
                          args=["--new-window"])
    assert script.startswith("#!/bin/sh\n")
    assert 'export GTK_THEME="Mint-Y-Dark"' in script
    assert script.index('export GTK_THEME') < script.index('export LC_ALL')
    assert script.rstrip().endswith(
        'exec "/usr/bin/celluloid" "--new-window" "$@"')
    assert wrapper_plan("/usr/bin/x").rstrip().endswith(
        'exec "/usr/bin/x" "$@"')
    for bad in (lambda: wrapper_plan("celluloid; rm -rf /"),
                lambda: wrapper_plan("/bin/sh -c whoami"),
                lambda: wrapper_plan("/usr/bin/x", env={"bad key": "v"}),
                lambda: wrapper_plan("/usr/bin/x", env={"K": 'quote"inside'}),
                lambda: wrapper_plan("/usr/bin/x", env={"K": "line\nbreak"}),
                lambda: wrapper_plan("")):
        try:
            bad()
        except GtkToolkitError:
            pass
        else:
            raise AssertionError("unsafe wrapper accepted")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
