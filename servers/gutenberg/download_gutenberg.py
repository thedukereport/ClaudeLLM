#!/usr/bin/env python3
"""
Download the Kiwix Project Gutenberg ZIMs, by Library-of-Congress subject.

Why subsets and not the single bundle: the one-file `gutenberg_en_all` is ~206 GB
and ALL 39 subsets together are ~207 GB — the same corpus, so subsets cost you
nothing in space. What they buy you: each file resumes independently (a dropped
download costs one file, not 206 GB), you can start searching the subjects you
care about while the rest arrive, and the server tags every hit with its subject.

Order is deliberate: small humanities subsets first (Religion, Classics, Law,
Political science...), the 37 GB world-history brick last. Stop any time — the
server works with whatever is already on disk.

Resumable: re-run and it skips completed files and continues partial ones.

    python3 download_gutenberg.py --list          # show plan, download nothing
    python3 download_gutenberg.py --set core      # ~11.3 GB humanities core
    python3 download_gutenberg.py --set all       # everything, ~207 GB
    python3 download_gutenberg.py --set b,pa,d    # pick classes yourself

Stdlib only.
"""
import os, re, sys, ssl, time, argparse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://download.kiwix.org/zim/gutenberg/"
UA = {"User-Agent": "gutenberg-mcp-setup/1.0"}

# python.org's macOS Python ships its own OpenSSL with NO CA certificates, so
# every HTTPS request dies with CERTIFICATE_VERIFY_FAILED. (curl works because it
# uses the system store; urllib doesn't.) Prefer certifi's bundle when present;
# the permanent system-wide fix is to run, once:
#     /Applications/Python\ 3.x/Install\ Certificates.command
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CTX = ssl.create_default_context()


def _open(req, timeout):
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            sys.exit(
                "\nSSL certificate verification failed.\n\n"
                "Your Python has no CA certificates. Fix it once with:\n"
                "    /Applications/Python\\ 3.10/Install\\ Certificates.command\n"
                "(adjust the version), or:\n"
                f"    {sys.executable} -m pip install certifi\n"
                "then re-run this script.\n")
        raise

LCC = {
    "a": "General works", "b": "Philosophy, Psychology, Religion",
    "c": "Archaeology, genealogy, historical sciences", "d": "World history",
    "e": "History of the Americas", "f": "History of the Americas (local)",
    "g": "Geography, Anthropology, Recreation", "h": "Social sciences",
    "j": "Political science", "k": "Law", "l": "Education", "m": "Music",
    "n": "Fine arts", "p": "Language & literature (general)",
    "pa": "Classical (Greek & Latin)", "pb": "Modern & Celtic languages",
    "pc": "Romance languages", "pd": "Germanic languages", "pe": "English language",
    "pf": "West Germanic languages", "pg": "Slavic & Baltic", "ph": "Finno-Ugric, Basque",
    "pj": "Oriental & Semitic", "pk": "Indo-Iranian",
    "pl": "Languages of E. Asia, Africa, Oceania", "pm": "Indigenous & artificial languages",
    "pn": "Literature (general), criticism, drama", "pq": "Romance literatures",
    "pr": "English literature", "ps": "American literature", "pt": "Germanic literature",
    "pz": "Fiction & juvenile literature", "q": "Science", "r": "Medicine",
    "s": "Agriculture", "t": "Technology", "u": "Military science",
    "v": "Naval science", "z": "Bibliography & library science",
}

# humanities-first: what a historian/philologist reaches for, smallest first
CORE = ["pd", "pf", "p", "ph", "pm", "pb", "pk", "pl", "pc", "pg", "pj", "k",
        "j", "pa", "l", "pt", "pe", "c", "b"]   # ~11.3 GB, 11,315 books
PRIORITY = CORE + ["u", "v", "r", "z", "pn", "m", "pq", "h", "s", "g", "a",
                   "f", "e", "t", "pr", "ps", "q", "pz", "n", "d"]


def listing():
    """Newest ZIM per LCC class, from the live Kiwix index."""
    req = urllib.request.Request(BASE, headers=UA)
    html = _open(req, 45).read().decode("utf-8", "replace")
    rows = re.findall(
        r'href="(gutenberg_en_lcc-([a-z]+)_([\d-]+)\.zim)"[^>]*>[^<]*</a>\s*'
        r'[\d-]{10}[^<]*?([\d.]+)([KMG])', html)
    best = {}
    for fn, code, date, num, unit in rows:
        gb = float(num) * {"K": 1/1048576, "M": 1/1024, "G": 1}[unit]
        if code not in best or date > best[code][0]:
            best[code] = (date, fn, gb)
    return best


def fetch(url, dest, expected_gb):
    """Resume a partial file with an HTTP Range request."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers=dict(UA))
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        r = _open(req, 60)
    except urllib.error.HTTPError as e:
        if e.code == 416:            # already complete
            tmp.rename(dest); return True
        raise
    total = have + int(r.headers.get("Content-Length", 0))
    mode = "ab" if have and r.status == 206 else "wb"
    if mode == "wb":
        have = 0
    t0, done = time.time(), have
    with open(tmp, mode) as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); done += len(chunk)
            if done % (64 << 20) < (1 << 20):
                pct = 100 * done / total if total else 0
                mbps = (done - have) / max(1e-6, time.time() - t0) / 1e6
                print(f"      {done/2**30:6.2f} / {total/2**30:5.2f} GB "
                      f"({pct:5.1f}%)  {mbps:4.1f} MB/s", flush=True)
    tmp.rename(dest)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="core",
                    help="'core' (~11.3 GB humanities), 'all' (~207 GB), or a comma list of LCC codes")
    ap.add_argument("--list", action="store_true", help="show the plan and exit")
    ap.add_argument("--dir", default=str(HERE))
    args = ap.parse_args()

    out = Path(args.dir); out.mkdir(parents=True, exist_ok=True)
    best = listing()

    if args.set == "core":
        want = [c for c in CORE if c in best]
    elif args.set == "all":
        want = [c for c in PRIORITY if c in best] + [c for c in best if c not in PRIORITY]
    else:
        want = [c.strip().lower() for c in args.set.split(",") if c.strip().lower() in best]

    plan = [(c, best[c][1], best[c][2]) for c in want]
    todo = [(c, f, g) for c, f, g in plan if not (out / f).exists()]
    print(f"{len(plan)} subset(s) selected, {sum(g for _, _, g in plan):.1f} GB total")
    print(f"{len(plan)-len(todo)} already present; {sum(g for _,_,g in todo):.1f} GB to fetch\n")
    for c, f, g in plan:
        mark = "have" if (out / f).exists() else " -- "
        print(f"  [{mark}] lcc-{c:<3} {g:6.2f} GB  {LCC.get(c,'?')}")
    if args.list:
        return
    print()

    for i, (c, fn, gb) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] lcc-{c} — {LCC.get(c,'?')} ({gb:.2f} GB)", flush=True)
        for attempt in range(1, 6):
            try:
                fetch(BASE + fn, out / fn, gb)
                print(f"      done -> {fn}\n", flush=True); break
            except Exception as e:
                print(f"      attempt {attempt} failed: {e}; retrying...", flush=True)
                time.sleep(3 * attempt)
        else:
            print(f"      GIVING UP on {fn} — re-run to resume\n", flush=True)

    print("All requested subsets present. Restart Claude to pick them up.")


if __name__ == "__main__":
    main()
