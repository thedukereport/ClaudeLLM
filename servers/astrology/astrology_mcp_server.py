#!/usr/bin/env python3
"""
Astrology — MCP Server (offline, Swiss Ephemeris via kerykeion)

Gives Claude offline astrological calculation tools: natal charts, the current
(or dated) sky, and synastry (relationship) comparison. All computation is local
— kerykeion uses pyswisseph's built-in ephemeris, so NO internet is needed once
installed. Birth data is given as coordinates + timezone (no geonames lookups).

Run with a Python env that has kerykeion installed, e.g.:
    /Volumes/PRO-BLADE/Astrology/astro_env/bin/python \
        /Volumes/PRO-BLADE/Astrology/astrology_mcp_server.py

CLI test:
    astrology_mcp_server.py natal "Ada" 1990 6 15 14 30 40.7128 -74.0060 America/New_York
    astrology_mcp_server.py sky
Stdlib + kerykeion only. Same newline-delimited JSON-RPC stdio pattern as the
other Alexandria MCP servers.

Note: astrology is not an empirical science. These tools report the standard
astronomical/astrological figures (positions, houses, aspects); interpretation
is the user's own.
"""

import json
import sys

try:
    import warnings
    warnings.filterwarnings("ignore")
    from kerykeion import AstrologicalSubjectFactory, NatalAspects, SynastryAspects
    _KERR = None
except Exception as e:  # pragma: no cover
    AstrologicalSubjectFactory = None
    _KERR = e

SIGNS = {"Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
         "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
         "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces"}

# planets/points shown, in traditional order
BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
          "uranus", "neptune", "pluto", "mean_north_lunar_node", "chiron"]
BODY_LABEL = {"mean_north_lunar_node": "N.Node", "chiron": "Chiron"}

HOUSE_ORD = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
             "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth"]
_ORD = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th"]
HOUSE_SHORT = {f"{w}_House": _ORD[i] for i, w in enumerate(HOUSE_ORD)}


def _deg(pos):
    """Degrees-within-sign float → 'DD°MM''."""
    d = int(pos)
    m = int(round((pos - d) * 60))
    if m == 60:
        d, m = d + 1, 0
    return f"{d:2d}°{m:02d}'"


def _label(key):
    return BODY_LABEL.get(key, key.capitalize())


def build_subject(p, default_name="Subject"):
    """Build an offline AstrologicalSubjectModel from a birth-data dict.
    Requires lat, lng, tz_str; date/time default to fields present."""
    if AstrologicalSubjectFactory is None:
        raise RuntimeError(f"kerykeion not installed: {_KERR}")
    req = ("year", "month", "day", "hour", "minute", "lat", "lng", "tz_str")
    missing = [k for k in req if p.get(k) in (None, "")]
    if missing:
        raise ValueError("missing birth fields: " + ", ".join(missing)
                         + " (need date/time + lat, lng, tz_str)")
    return AstrologicalSubjectFactory.from_birth_data(
        name=str(p.get("name", default_name)),
        year=int(p["year"]), month=int(p["month"]), day=int(p["day"]),
        hour=int(p["hour"]), minute=int(p["minute"]),
        lat=float(p["lat"]), lng=float(p["lng"]), tz_str=str(p["tz_str"]),
        city=str(p.get("city", "")), nation=str(p.get("nation", "")),
        zodiac_type=p.get("zodiac_type", "Tropical"),
        houses_system_identifier=p.get("house_system", "P"),
        online=False, suppress_geonames_warning=True)


def _planet_lines(d):
    out = []
    for key in BODIES:
        b = d.get(key)
        if not b:
            continue
        sign = SIGNS.get(b["sign"], b["sign"])
        house = HOUSE_SHORT.get(b.get("house", ""), "")
        retro = " ℞" if b.get("retrograde") else "  "
        hs = f"  ({house} house)" if house else ""
        out.append(f"  {_label(key):8} {_deg(b['position'])} {sign:11}{retro}{hs}")
    return out


def _angle_lines(d):
    out = []
    for key, lab in (("ascendant", "Asc"), ("medium_coeli", "MC")):
        b = d.get(key)
        if b:
            out.append(f"  {lab:8} {_deg(b['position'])} {SIGNS.get(b['sign'], b['sign'])}")
    return out


def _aspect_lines(aspects, limit=40):
    out = []
    for a in aspects[:limit]:
        mv = a.get("aspect_movement", "")
        mv = f" ({mv.lower()})" if mv else ""
        out.append(f"  {a['p1_name']:8} {a['aspect']:12} {a['p2_name']:8} "
                   f" orb {a['orbit']:.1f}°{mv}")
    return out


def _header(d):
    diurnal = "day chart" if d.get("is_diurnal") else "night chart"
    zt = d.get("zodiac_type", "Tropical")
    hs = d.get("houses_system_name", d.get("houses_system_identifier", "Placidus"))
    return (f"Born : {d['year']:04d}-{d['month']:02d}-{d['day']:02d} "
            f"{d['hour']:02d}:{d['minute']:02d}  {d.get('tz_str','')}  "
            f"@ {d.get('lat')},{d.get('lng')}\n"
            f"UTC  : {d.get('iso_formatted_utc_datetime','?')}  |  "
            f"Julian day {d.get('julian_day','?')}\n"
            f"Frame: {zt} zodiac · {hs} houses · {diurnal}")


# ── tools ───────────────────────────────────────────────────────────

def natal_chart(args):
    s = build_subject(args, args.get("name", "Subject"))
    d = s.model_dump()
    asp = NatalAspects(s).relevant_aspects
    lp = d.get("lunar_phase", {}) or {}
    lines = [f"Natal chart — {d.get('name')}", _header(d), "",
             "Planets & points:", *_planet_lines(d), "",
             "Angles:", *_angle_lines(d), "",
             f"Lunar phase: {lp.get('moon_phase_name','?')} {lp.get('moon_emoji','')}", "",
             f"Aspects ({len(asp)}):", *_aspect_lines(asp)]
    return "\n".join(lines)


def sky(args):
    """Current (or dated) sky as a chart. If no date given, uses now (UTC);
    location defaults to Greenwich unless lat/lng/tz_str supplied."""
    if AstrologicalSubjectFactory is None:
        raise RuntimeError(f"kerykeion not installed: {_KERR}")
    has_date = all(args.get(k) not in (None, "") for k in ("year", "month", "day", "hour", "minute"))
    loc = dict(lat=float(args.get("lat", 51.4769)), lng=float(args.get("lng", -0.0005)),
               tz_str=str(args.get("tz_str", "Etc/GMT")))
    if has_date:
        s = build_subject({**args, **loc, "name": args.get("name", "Sky")}, "Sky")
        title = "Sky"
    else:
        s = AstrologicalSubjectFactory.from_current_time(
            name="Sky", online=False, suppress_geonames_warning=True, **loc)
        title = "Current sky (now)"
    d = s.model_dump()
    asp = NatalAspects(s).relevant_aspects
    return "\n".join([f"{title}", _header(d), "", "Planets & points:",
                      *_planet_lines(d), "", f"Aspects ({len(asp)}):", *_aspect_lines(asp)])


def synastry(args):
    p1, p2 = args.get("person1"), args.get("person2")
    if not p1 or not p2:
        return "ERROR: provide 'person1' and 'person2', each with name + birth data (date/time, lat, lng, tz_str)."
    a = build_subject(p1, "Person 1")
    b = build_subject(p2, "Person 2")
    cross = SynastryAspects(a, b).relevant_aspects
    da, db = a.model_dump(), b.model_dump()
    lines = [f"Synastry — {da.get('name')}  ×  {db.get('name')}",
             f"{da.get('name')}: Sun {SIGNS.get(da['sun']['sign'])} {_deg(da['sun']['position'])}, "
             f"Moon {SIGNS.get(da['moon']['sign'])}, Asc {SIGNS.get(da['ascendant']['sign'])}",
             f"{db.get('name')}: Sun {SIGNS.get(db['sun']['sign'])} {_deg(db['sun']['position'])}, "
             f"Moon {SIGNS.get(db['moon']['sign'])}, Asc {SIGNS.get(db['ascendant']['sign'])}",
             "", f"Cross-aspects ({len(cross)}):"]
    for a_ in cross[:60]:
        mv = a_.get("aspect_movement", "")
        mv = f" ({mv.lower()})" if mv else ""
        lines.append(f"  {da.get('name')[:10]:10} {a_['p1_name']:8} {a_['aspect']:12} "
                     f"{db.get('name')[:10]:10} {a_['p2_name']:8}  orb {a_['orbit']:.1f}°{mv}")
    return "\n".join(lines)


# ── MCP plumbing ────────────────────────────────────────────────────

_BIRTH_PROPS = {
    "name": {"type": "string"},
    "year": {"type": "integer"}, "month": {"type": "integer"}, "day": {"type": "integer"},
    "hour": {"type": "integer"}, "minute": {"type": "integer"},
    "lat": {"type": "number", "description": "Latitude, decimal degrees (N +, S −)"},
    "lng": {"type": "number", "description": "Longitude, decimal degrees (E +, W −)"},
    "tz_str": {"type": "string", "description": "IANA timezone, e.g. 'America/New_York'"},
    "city": {"type": "string"}, "nation": {"type": "string"},
    "zodiac_type": {"type": "string", "description": "Tropical (default) or Sidereal"},
    "house_system": {"type": "string", "description": "Swiss code; 'P'=Placidus (default), 'W'=Whole Sign, 'K'=Koch, 'R'=Regiomontanus"},
}

TOOLS = [
    {"name": "natal_chart",
     "description": ("Compute an offline natal (birth) chart: planet & point positions "
                     "by sign/degree/house, the Ascendant & Midheaven, lunar phase, and "
                     "the aspect grid. Give date/time as numbers plus lat, lng and an IANA "
                     "tz_str (no city lookup needed). Tropical/Placidus by default; "
                     "zodiac_type and house_system are optional."),
     "inputSchema": {"type": "object", "properties": _BIRTH_PROPS,
                     "required": ["year", "month", "day", "hour", "minute", "lat", "lng", "tz_str"]}},
    {"name": "sky",
     "description": ("The current sky as a chart (planetary positions + aspects) — or, if "
                     "you pass a date/time, the sky at that moment. Optional lat/lng/tz_str "
                     "(defaults to Greenwich/UTC). Useful for transits and 'what's the sky "
                     "doing now'."),
     "inputSchema": {"type": "object", "properties": _BIRTH_PROPS}},
    {"name": "synastry",
     "description": ("Relationship (synastry) comparison of two birth charts: the cross-"
                     "aspects between person 1's and person 2's planets. Each person is an "
                     "object with name + birth data (year..minute, lat, lng, tz_str)."),
     "inputSchema": {"type": "object",
                     "properties": {"person1": {"type": "object", "properties": _BIRTH_PROPS},
                                    "person2": {"type": "object", "properties": _BIRTH_PROPS}},
                     "required": ["person1", "person2"]}},
]


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        if name == "natal_chart":
            text = natal_chart(args)
        elif name == "sky":
            text = sky(args)
        elif name == "synastry":
            text = synastry(args)
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "astrology", "version": "1.0.0"}}


HANDLERS = {"initialize": handle_initialize,
            "tools/list": lambda p: {"tools": TOOLS},
            "tools/call": handle_tools_call}


def process_message(msg):
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params", {})
    if msg_id is None:
        return None
    h = HANDLERS.get(method)
    if h:
        try:
            return {"jsonrpc": "2.0", "id": msg_id, "result": h(params)}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    if len(sys.argv) > 1:  # CLI test mode
        cmd = sys.argv[1]
        if cmd == "natal" and len(sys.argv) >= 11:
            a = sys.argv
            print(natal_chart({"name": a[2], "year": a[3], "month": a[4], "day": a[5],
                               "hour": a[6], "minute": a[7], "lat": a[8], "lng": a[9], "tz_str": a[10]}))
        elif cmd == "sky":
            print(sky({}))
        else:
            print(__doc__)
        return
    print(f"[astrology] MCP server starting "
          f"({'kerykeion OK' if AstrologicalSubjectFactory else 'kerykeion MISSING'})", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[astrology] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
