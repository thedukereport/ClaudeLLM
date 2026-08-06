#!/usr/bin/env python3
"""
Build scriptures.sqlite — a unified, searchable corpus of open religious texts
for the combined `scriptures` MCP server.

Corpora (each row is tagged with its own license):
  quran    Arabic (verified) + English + transliteration, sura/aya
           source: risan/quran-json (Tanzil-derived Arabic). PUBLIC / permissive.
  enoch    1 Enoch, R. H. Charles translation, chapter/verse.
           source: Wikisource. PUBLIC DOMAIN.
  tanakh   Hebrew + English, book/chapter/verse.   source: Sefaria export (merged).
  talmud   Bavli, Hebrew/Aramaic + English, daf/line. source: Sefaria export (merged).
  mishnah  Hebrew + English, chapter/mishnah.        source: Sefaria export (merged).
           Sefaria texts: CC BY-NC 4.0 — PERSONAL RESEARCH, not for resale.
  gnostic  Pistis Sophia, G.R.S. Mead translation, book/chapter (best effort).
           source: Wikisource. PUBLIC DOMAIN.

Stdlib only (urllib, sqlite3, json, re) — no pip, runs on any Python 3.8+.
Downloads are cached under ./sources/ and skipped if already present, so the
script is resumable: re-run it and it picks up where it stopped.

Usage:
  python3 build_scriptures.py                     # everything
  python3 build_scriptures.py --only quran,enoch  # subset
  python3 build_scriptures.py --sefaria-limit 3   # first N books each (testing)
  python3 build_scriptures.py --rebuild-db-only   # skip downloads, rebuild sqlite
"""

import os, re, sys, json, time, sqlite3, argparse, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC  = HERE / "sources"
DB   = HERE / "scriptures.sqlite"
UA   = {"User-Agent": "scriptures-build/1.0 (local research corpus)"}
SRC.mkdir(exist_ok=True)

CC_BY_NC = "CC BY-NC 4.0 (Sefaria) — personal research, not for redistribution/resale"
PD       = "Public domain"
QURAN_LIC= "Tanzil-derived verified Arabic (free redistribution); English translation bundled by quran-json"

# ---------------------------------------------------------------- helpers
def fetch(url, tries=4, timeout=45):
    url = urllib.parse.quote(url, safe=":/?&=%,'()")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last

def cache_get(url, cache_path):
    p = SRC / cache_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes()
    data = fetch(url)
    p.write_bytes(data)
    return data

_TAG = re.compile(r"(?s)<[^>]+>")
_WS  = re.compile(r"[ \t]+")
def strip_html(s):
    if not isinstance(s, str):
        s = " ".join(x for x in s if isinstance(x, str)) if isinstance(s, list) else str(s)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    # drop footnote bodies Sefaria stores inline
    s = re.sub(r'(?is)<i class="footnote">.*?</i>', "", s)
    s = re.sub(r'(?is)<sup class="footnote-marker">.*?</sup>', "", s)
    s = _TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">")
           .replace("&quot;", '"').replace("&#39;", "'").replace("&thinsp;", " "))
    s = _WS.sub(" ", s)
    return s.strip()

# ---------------------------------------------------------------- QURAN
def load_quran(rows):
    url = "https://raw.githubusercontent.com/risan/quran-json/main/dist/quran_en.json"
    data = json.loads(cache_get(url, "quran_en.json"))
    n = 0
    for sura in data:
        sid = sura["id"]; sname = sura["transliteration"]
        head = f"Surah {sid} — {sname} ({sura.get('translation','')})"
        for v in sura["verses"]:
            ref = f"Quran {sid}:{v['id']}"
            rows.append(("quran", f"Surah {sid} {sname}", ref, "ar", head, v["text"], QURAN_LIC))
            rows.append(("quran", f"Surah {sid} {sname}", ref, "en", head, v["translation"], QURAN_LIC))
            n += 1
    return n

# ---------------------------------------------------------------- ENOCH
ROMAN = None
def wiki_wikitext(page):
    u = "https://en.wikisource.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext",
         "format": "json", "formatversion": "2"})
    safe = page.replace("/", "_").replace(" ", "_")
    raw = cache_get(u, f"wikisource/{safe}.json")
    d = json.loads(raw)
    return d.get("parse", {}).get("wikitext", "")

def load_enoch(rows):
    n = 0
    for ch in range(1, 109):
        page = f"The Book of Enoch (Charles)/Chapter {ch:02d}"
        try:
            wt = wiki_wikitext(page)
        except Exception:
            continue
        if not wt:
            continue
        # strip templates {{...}} and headings ===...===
        body = re.sub(r"(?s)\{\{.*?\}\}", "", wt)
        # capture the last heading before the verses as context
        heads = re.findall(r"={2,}\s*(.*?)\s*={2,}", body)
        heading = strip_html(heads[-1]) if heads else ""
        body = re.sub(r"={2,}.*?={2,}", "", body)
        body = re.sub(r"(?i)CHAPTER\s+[IVXLC]+\.?", "", body)
        body = body.strip()
        # split into verses on leading "N. "
        parts = re.split(r"(?m)(?:^|\s)(\d{1,3})\.\s", " " + body)
        # parts = ['', '1', 'text1', '2', 'text2', ...]
        i = 1
        while i + 1 < len(parts):
            vnum = parts[i]; vtext = strip_html(parts[i + 1])
            if vtext:
                rows.append(("enoch", "1 Enoch",
                             f"Enoch {ch}:{vnum}", "en", heading, vtext, PD))
                n += 1
            i += 2
        if ch % 20 == 0:
            print(f"    enoch: chapter {ch}", flush=True)
    return n

# ---------------------------------------------------------------- SEFARIA
TANAKH = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
          "Judges", "I Samuel", "II Samuel", "I Kings", "II Kings", "Isaiah",
          "Jeremiah", "Ezekiel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah",
          "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
          "Malachi", "Psalms", "Proverbs", "Job", "Song of Songs", "Ruth",
          "Lamentations", "Ecclesiastes", "Esther", "Daniel", "Ezra",
          "Nehemiah", "I Chronicles", "II Chronicles"]
TALMUD = ["Berakhot", "Shabbat", "Eruvin", "Pesachim", "Rosh Hashanah", "Yoma",
          "Sukkah", "Beitzah", "Taanit", "Megillah", "Moed Katan", "Chagigah",
          "Yevamot", "Ketubot", "Nedarim", "Nazir", "Sotah", "Gittin",
          "Kiddushin", "Bava Kamma", "Bava Metzia", "Bava Batra", "Sanhedrin",
          "Makkot", "Shevuot", "Avodah Zarah", "Horayot", "Zevachim",
          "Menachot", "Chullin", "Bekhorot", "Arakhin", "Temurah", "Keritot",
          "Meilah", "Tamid", "Niddah"]
MISHNAH_EXTRA = ["Peah", "Demai", "Kilayim", "Sheviit", "Terumot", "Maasrot",
                 "Maaser Sheni", "Challah", "Orlah", "Bikkurim", "Shekalim",
                 "Middot", "Kinnim", "Kelim", "Oholot", "Negaim", "Parah",
                 "Tahorot", "Mikvaot", "Makhshirin", "Zavim", "Tevul Yom",
                 "Yadayim", "Uktzim", "Avot", "Eduyot"]

def _books_index():
    raw = cache_get(
        "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json",
        "sefaria_books.json")
    return json.loads(raw)["books"]

def _pick(books, cat, path_needle, wanted_titles, lang):
    out = {}
    for b in books:
        if not b.get("categories") or b["categories"][0] != cat:
            continue
        if b["language"] != lang or b["versionTitle"] != "merged":
            continue
        if path_needle not in b["json_url"]:
            continue
        if b["title"] in wanted_titles:
            out[b["title"]] = b["json_url"]
    return out

def _talmud_ref(title, daf_idx, line_idx):
    daf = daf_idx // 2 + 1
    amud = "a" if daf_idx % 2 == 0 else "b"
    return f"{title} {daf}{amud}:{line_idx + 1}"

def load_sefaria(rows, limit=None):
    books = _books_index()
    plan = [
        ("tanakh",  "Tanakh",  "/Tanakh/",       TANAKH, "verse"),
        ("talmud",  "Talmud",  "/Talmud/Bavli/", TALMUD, "daf"),
        ("mishnah", "Mishnah", "/Mishnah/",
         ["Mishnah " + t for t in TALMUD] +      # Mishnah shares tractate names
         ["Mishnah " + t for t in
          ("Peah Demai Kilayim Sheviit Terumot Maasrot Maaser_Sheni Challah "
           "Orlah Bikkurim Shabbat Eruvin Pesachim Shekalim Sukkah Beitzah "
           "Taanit Megillah Middot Kinnim Kelim Oholot Negaim Parah Tahorot "
           "Mikvaot Niddah Makhshirin Zavim Tevul_Yom Yadayim Uktzim Avot "
           "Eduyot Kinnim").replace("_", " ").split()],
         "verse"),
    ]
    total = 0
    for corpus, cat, needle, wanted, kind in plan:
        wanted = set(wanted)
        he = _pick(books, cat, needle, wanted, "Hebrew")
        en = _pick(books, cat, needle, wanted, "English")
        titles = sorted(set(he) | set(en))
        if limit:
            titles = titles[:limit]
        print(f"  {corpus}: {len(titles)} books", flush=True)
        for ti, title in enumerate(titles, 1):
            for lang, url in (("he", he.get(title)), ("en", en.get(title))):
                if not url:
                    continue
                safe = url.split("/sefaria-export/")[-1].replace("/", "_")
                try:
                    doc = json.loads(cache_get(url, f"sefaria/{safe}"))
                except Exception as e:
                    print(f"    ! {title} {lang}: {e}", flush=True)
                    continue
                text = doc.get("text", [])
                for a, section in enumerate(text):
                    if not section:
                        continue
                    for b, seg in enumerate(section):
                        body = strip_html(seg)
                        if not body:
                            continue
                        if kind == "daf":
                            ref = _talmud_ref(title, a, b)
                        else:
                            ref = f"{title} {a + 1}:{b + 1}"
                        rows.append((corpus, title, ref, lang, "", body, CC_BY_NC))
                        total += 1
            if ti % 10 == 0:
                print(f"    {corpus}: {ti}/{len(titles)}", flush=True)
    return total

# ---------------------------------------------------------------- GNOSTIC (best effort)
def load_gnostic(rows):
    """Pistis Sophia (Mead, 1921) from Wikisource — book/chapter. Best effort."""
    n = 0
    # Mead's Pistis Sophia is organized in numbered chapters 1..147 as subpages.
    for ch in range(1, 148):
        page = f"Pistis Sophia (Mead)/Chapter {ch}"
        try:
            wt = wiki_wikitext(page)
        except Exception:
            continue
        if not wt:
            continue
        body = re.sub(r"(?s)\{\{.*?\}\}", "", wt)
        body = re.sub(r"={2,}.*?={2,}", "", body)
        body = strip_html(body)
        if len(body) < 30:
            continue
        rows.append(("gnostic", "Pistis Sophia",
                     f"Pistis Sophia {ch}", "en", "", body, PD))
        n += 1
        if ch % 40 == 0:
            print(f"    gnostic: chapter {ch}", flush=True)
    return n

# ---------------------------------------------------------------- DB
def build_db(rows):
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript("""
      PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE docs(
        id INTEGER PRIMARY KEY, corpus TEXT, book TEXT, ref TEXT,
        lang TEXT, heading TEXT, body TEXT, license TEXT);
      CREATE INDEX idx_ref  ON docs(ref);
      CREATE INDEX idx_book ON docs(corpus, book);
      CREATE VIRTUAL TABLE docs_fts USING fts5(
        body, ref UNINDEXED, book UNINDEXED, corpus UNINDEXED,
        content='docs', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
    """)
    con.executemany(
        "INSERT INTO docs(corpus,book,ref,lang,heading,body,license) "
        "VALUES(?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO docs_fts(docs_fts) VALUES('rebuild')")
    con.commit()
    stats = con.execute(
        "SELECT corpus, lang, COUNT(*) FROM docs GROUP BY corpus, lang "
        "ORDER BY corpus, lang").fetchall()
    con.close()
    return stats

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="quran,enoch,tanakh,talmud,mishnah,gnostic",
                    help="comma list: quran,enoch,tanakh,talmud,mishnah,gnostic")
    ap.add_argument("--sefaria-limit", type=int, default=None,
                    help="only first N books of each Sefaria corpus (testing)")
    ap.add_argument("--rebuild-db-only", action="store_true",
                    help="(reserved) — this build always re-reads cache")
    args = ap.parse_args()
    want = set(x.strip() for x in args.only.split(",") if x.strip())

    rows = []
    t0 = time.perf_counter()
    if "quran" in want:
        print("Quran ...", flush=True);   print("  ayat:", load_quran(rows), flush=True)
    if "enoch" in want:
        print("Enoch ...", flush=True);   print("  verses:", load_enoch(rows), flush=True)
    if want & {"tanakh", "talmud", "mishnah"}:
        print("Sefaria ...", flush=True)
        # temporarily narrow the plan to requested corpora
        keep = want & {"tanakh", "talmud", "mishnah"}
        global load_sefaria
        print("  segments:", load_sefaria_filtered(rows, keep, args.sefaria_limit), flush=True)
    if "gnostic" in want:
        print("Gnostic ...", flush=True); print("  chapters:", load_gnostic(rows), flush=True)

    print(f"\nTotal rows: {len(rows):,}  ({time.perf_counter()-t0:.0f}s to gather)")
    print("Building sqlite + FTS5 ...", flush=True)
    stats = build_db(rows)
    print("\nscriptures.sqlite built:")
    for corpus, lang, c in stats:
        print(f"  {corpus:8} {lang}  {c:>8,}")
    print(f"\n-> {DB}")

def load_sefaria_filtered(rows, keep, limit):
    """Wrapper so --only can restrict which Sefaria corpora load."""
    books = _books_index()
    from types import SimpleNamespace
    total = 0
    plan_all = {
        "tanakh":  ("Tanakh",  "/Tanakh/",       TANAKH, "verse"),
        "talmud":  ("Talmud",  "/Talmud/Bavli/", TALMUD, "daf"),
        "mishnah": ("Mishnah", "/Mishnah/",
                    ["Mishnah " + t for t in (TALMUD + MISHNAH_EXTRA)],
                    "verse"),
    }
    for corpus in ("tanakh", "talmud", "mishnah"):
        if corpus not in keep:
            continue
        cat, needle, wanted, kind = plan_all[corpus]
        wanted = set(wanted)
        he = _pick(books, cat, needle, wanted, "Hebrew")
        en = _pick(books, cat, needle, wanted, "English")
        titles = sorted(set(he) | set(en))
        if limit:
            titles = titles[:limit]
        print(f"  {corpus}: {len(titles)} books", flush=True)
        for ti, title in enumerate(titles, 1):
            for lang, url in (("he", he.get(title)), ("en", en.get(title))):
                if not url:
                    continue
                safe = url.split("/sefaria-export/")[-1].replace("/", "_")
                try:
                    doc = json.loads(cache_get(url, f"sefaria/{safe}"))
                except Exception as e:
                    print(f"    ! {title} {lang}: {e}", flush=True)
                    continue
                for a, section in enumerate(doc.get("text", [])):
                    if not section:
                        continue
                    for b, seg in enumerate(section):
                        body = strip_html(seg)
                        if not body:
                            continue
                        ref = (_talmud_ref(title, a, b) if kind == "daf"
                               else f"{title} {a + 1}:{b + 1}")
                        rows.append((corpus, title, ref, lang, "", body, CC_BY_NC))
                        total += 1
            if ti % 10 == 0:
                print(f"    {corpus}: {ti}/{len(titles)}", flush=True)
    return total

if __name__ == "__main__":
    main()
