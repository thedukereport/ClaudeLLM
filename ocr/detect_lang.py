#!/usr/bin/env python3
"""Pick the OCR language for each scan by reading one page of it.

The handoff says much of this archive is not English and warns that English-only
OCR will read it poorly — it turns every French accent into a digit ("veut 2 la
raison", "dimanche 4"). Guessing from the title fails too: half the anti-masonic
French works in here are English translations, Dupanloup among them.

So read one page with plain English OCR — which still gets most letters right
whatever the language — and score the words against stopword sets. The winner
becomes that book's -l setting.
"""
import os, re, subprocess, sys, time

# The work list carries the paths of the machine that wrote it. Set
# ALEX_PDF_ROOT when you run this somewhere else (a sandbox mount, another
# disk) and those paths are rewritten to the root you name.
HERE = os.path.dirname(os.path.abspath(__file__))
MAC = os.environ.get("ALEX_PDF_MAC_ROOT", "/Volumes/PRO-BLADE/Alexandria/PDF")
MOUNT = os.environ.get("ALEX_PDF_ROOT", os.path.dirname(HERE))
os.environ["TESSDATA_PREFIX"] = os.path.join(HERE, ".tessdata")
WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)

STOP = {
 "eng": "the of and to in a is that it was for as with on his by at from not are this but had which have were or been their",
 "fra": "le la les de des du et est une dans que qui pour pas sur au aux ce cette il elle nous vous ils sont plus avec par",
 "ita": "il lo la le gli dei della delle che non per con una sono anche come più questo quella nel alla dal degli negli",
 "por": "de do da os as um uma que não para com por mais como mas ao seu sua ou pelo pela nos nas dos das",
 "lat": "et in est non ad cum qui quae quod sed ut ex de per se hoc esse autem enim atque nec ab si",
}
STOP = {k: set(v.split()) for k, v in STOP.items()}


def page_text(path, pg):
    stem = os.path.join("/tmp", f"d{os.getpid()}")
    subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(pg), "-l", str(pg), path, stem],
                   capture_output=True, timeout=300)
    pngs = [f for f in os.listdir("/tmp") if f.startswith(os.path.basename(stem) + "-")]
    if not pngs:
        return ""
    png = os.path.join("/tmp", pngs[0])
    subprocess.run(["tesseract", png, stem, "-l", "eng", "--psm", "3"], capture_output=True,
                   timeout=300, env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    try:
        t = open(stem + ".txt", errors="ignore").read()
    except OSError:
        t = ""
    for f in (png, stem + ".txt"):
        try: os.remove(f)
        except OSError: pass
    return t


def detect(path, n):
    scores = {k: 0 for k in STOP}
    total = 0
    for frac in (0.35, 0.55, 0.75):
        t = page_text(path, max(1, int(n * frac)))
        w = [x.lower() for x in WORD.findall(t)]
        total += len(w)
        for k, s in STOP.items():
            scores[k] += sum(1 for x in w if x in s)
    if total < 60:
        return "eng", 0.0
    best = max(scores, key=scores.get)
    return best, scores[best] / total


def main():
    rows = []
    for l in open("zero_chunk_verify.tsv"):
        f = l.rstrip("\n").split("\t")
        if len(f) >= 5 and f[0] == "image-only" and not f[4].endswith("blank.pdf"):
            rows.append((f[4], int(f[1])))
    done = {}
    if os.path.exists("ocr_languages.tsv"):
        for l in open("ocr_languages.tsv"):
            f = l.rstrip("\n").split("\t")
            if len(f) >= 2: done[f[0]] = f[1]
    out = open("ocr_languages.tsv", "a", buffering=1)
    stop = time.time() + float(os.environ.get("BUDGET", "35"))
    for mac, n in rows:
        if mac in done: continue
        if time.time() > stop:
            print(f"BUDGET ({len(done)}/{len(rows)})", flush=True); return
        lang, conf = detect(mac.replace(MAC, MOUNT), n)
        done[mac] = lang
        out.write(f"{mac}\t{lang}\t{conf:.3f}\n")
        print(f"  {lang}  {conf:5.1%}  {os.path.basename(mac)[:56]}", flush=True)
    print("all detected", flush=True)

main()
