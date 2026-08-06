#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from perseus_mcp_server import discover, parse_tei, fold, HERE, INDEX, AUTHORS

DONE = HERE / "index-done.list"
t0 = time.time()
done = set(DONE.read_text().splitlines()) if DONE.exists() else set()
mode = "a" if done else "w"
n_new = 0
with INDEX.open(mode, encoding="utf-8") as out, DONE.open("a") as dl:
    for w in discover():
        key = str(w["file"].relative_to(HERE))
        if key in done:
            continue
        for loc, txt in parse_tei(w["file"]):
            rec = {"a": w["aslug"], "w": w["title"], "g": w["lang"],
                   "l": loc, "t": txt, "f": fold(txt)}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        dl.write(key + "\n"); dl.flush(); out.flush()
        done.add(key); n_new += 1
        if time.time() - t0 > 33:
            print(f"SLICE: {n_new} files this pass, {len(done)} total done")
            sys.exit(0)
# complete: write catalog
catalog = {}
for w in discover():
    entry = catalog.setdefault(w["aslug"], {"author": w["author"], "works": {}})
    wk = entry["works"].setdefault(w["title"], {"id": w["id"], "files": {}})
    wk["files"][w["lang"]] = str(w["file"].relative_to(HERE))
AUTHORS.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
print(f"COMPLETE: {len(done)} files indexed; catalog written")
