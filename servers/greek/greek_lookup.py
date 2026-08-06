#!/usr/bin/env python3
"""
Greek lookup tool — LSJ (Perseus) + SBLGNT (Faithlife) + TAGNT (STEPBible) + LXX (Perseus/Swete).

Reframing Reality uses the Byzantine textform as primary standard (see
feedback_byzantine_standard.md). Use 'verse-byz' for the project standard;
'verse' (SBLGNT) and 'editions' (multi-edition) remain for reference.

Usage:
  greek_lookup.py verse-byz <reference>        # Byzantine reading + divergence flag (PRIMARY NT)
  greek_lookup.py lsj <greek-or-translit>      # LSJ entry
  greek_lookup.py verse <reference>            # SBLGNT verse(s) [reference]
  greek_lookup.py editions <reference>         # Multi-edition NT view (NA, SBL, TH, Treg, WH, Byz, TR)
  greek_lookup.py lxx <reference> [grc1|grc2]  # LXX verse(s), Swete edition — e.g. 'Gen 14:13'
  greek_lookup.py lxx-editions <reference>     # LXX multi-edition (LXX + Theodotion for Dan/Sus/Bel)
  greek_lookup.py lxx-search <word> [max] [book]  # LXX concordance search (diacritic-insensitive)
  greek_lookup.py lxx-books                    # List all 57 LXX books with abbreviations
  greek_lookup.py smith-geo <name>             # William Smith's Dictionary of Greek and Roman Geography
  greek_lookup.py smith-bio <name>             # William Smith's Dictionary of Greek and Roman Biography and Mythology
  greek_lookup.py smith-ant <term>             # William Smith's Dictionary of Greek and Roman Antiquities
  greek_lookup.py smith-search <name>          # Search all three Smith dictionaries at once
  greek_lookup.py middle-liddell <word>        # Liddell-Scott Intermediate Greek lexicon (Middle Liddell)
  greek_lookup.py build-propnoun <geo|bio|cn|ml|all>   # Rebuild one/all proper-noun indices
  greek_lookup.py build-index                  # Rebuild LSJ index
  greek_lookup.py build-tagnt                  # Rebuild TAGNT verse index
"""
import os, sys, re, json, unicodedata
from pathlib import Path

ROOT = Path(__file__).parent
LSJ_DIR = ROOT / "lsj-xml"
SBLGNT_TEXT_DIR = ROOT / "sblgnt" / "data" / "sblgnt" / "text"
TAGNT_DIR = ROOT / "tagnt"
INDEX_FILE = ROOT / "lsj-index.json"
TAGNT_INDEX_FILE = ROOT / "tagnt-index.json"

# ──────────────────────────────────────────────────────────────────────
# Beta-code conversion (Unicode Greek → Perseus beta-code key)
# ──────────────────────────────────────────────────────────────────────
UNI_TO_BETA = {
    'α':'a','β':'b','γ':'g','δ':'d','ε':'e','ζ':'z','η':'h','θ':'q',
    'ι':'i','κ':'k','λ':'l','μ':'m','ν':'n','ξ':'c','ο':'o','π':'p',
    'ρ':'r','σ':'s','ς':'s','τ':'t','υ':'u','φ':'f','χ':'x','ψ':'y','ω':'w',
    'Α':'*a','Β':'*b','Γ':'*g','Δ':'*d','Ε':'*e','Ζ':'*z','Η':'*h','Θ':'*q',
    'Ι':'*i','Κ':'*k','Λ':'*l','Μ':'*m','Ν':'*n','Ξ':'*c','Ο':'*o','Π':'*p',
    'Ρ':'*r','Σ':'*s','Τ':'*t','Υ':'*u','Φ':'*f','Χ':'*x','Ψ':'*y','Ω':'*w',
}
# Combining diacritic → beta-code suffix
COMBINING = {
    '́':'/',   # acute
    '̀':'\\',  # grave
    '͂':'=',   # circumflex (perispomeni)
    '̔':'(',   # rough breathing
    '̓':')',   # smooth breathing
    'ͅ':'|',   # iota subscript
    '̈':'+',   # diaeresis
}

def to_beta(text):
    """Convert Unicode Greek to Perseus beta-code lookup key."""
    if not text:
        return ""
    # Already beta-code?
    if all(c.isascii() for c in text):
        return text.lower().replace('q','q').strip()
    decomp = unicodedata.normalize('NFD', text)
    out = []
    for c in decomp:
        if c in UNI_TO_BETA:
            out.append(UNI_TO_BETA[c])
        elif c in COMBINING:
            out.append(COMBINING[c])
        elif c.isalpha():
            out.append(c.lower())
    result = ''.join(out)
    # Perseus order: acute/grave/circumflex BEFORE diaeresis
    import re as _re
    result = _re.sub(r'\+([/=\\])', r'\1+', result)
    return result

# ──────────────────────────────────────────────────────────────────────
# LSJ index: key → (file, byte_offset, byte_length)
# ──────────────────────────────────────────────────────────────────────
def build_index():
    """Scan all LSJ XML files, record entryFree positions, save JSON index."""
    index = {}
    files = sorted(LSJ_DIR.glob('grc.lsj.perseus-eng*.xml'),
                   key=lambda p: int(re.search(r'eng(\d+)', p.name).group(1)))
    for fpath in files:
        with open(fpath, 'rb') as f:
            data = f.read()
        # Find every <entryFree ... key="..."> ... </entryFree>
        for m in re.finditer(rb'<entryFree\b[^>]*\bkey="([^"]+)"[^>]*>', data):
            key = m.group(1).decode('utf-8', errors='replace')
            start = m.start()
            # Find matching </entryFree>
            end_m = re.search(rb'</entryFree>', data[start:])
            if not end_m:
                continue
            end = start + end_m.end()
            entry = (fpath.name, start, end - start)
            # Multiple entries may share a key; store list
            if key in index:
                if isinstance(index[key], list):
                    index[key].append(entry)
                else:
                    index[key] = [index[key], entry]
            else:
                index[key] = entry
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f)
    return index

def load_index():
    if not INDEX_FILE.exists():
        return build_index()
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def lookup_lsj(term):
    """Return LSJ entry text for a Greek term (Unicode or beta-code)."""
    index = load_index()
    key = to_beta(term)
    if key not in index:
        # Try variants: strip final accent, etc.
        variants = [key, key.rstrip('/=\\'), key.replace('s', 'sigma_').replace('sigma_', 's')]
        for v in variants:
            if v in index:
                key = v
                break
        else:
            return None, None
    entries = index[key]
    if not isinstance(entries, list) or (isinstance(entries, list) and len(entries) == 3 and isinstance(entries[0], str)):
        # single entry tuple
        entries = [entries]
    results = []
    for fname, offset, length in entries:
        with open(LSJ_DIR / fname, 'rb') as f:
            f.seek(offset)
            raw = f.read(length).decode('utf-8', errors='replace')
        results.append(raw)
    return key, results

# ──────────────────────────────────────────────────────────────────────
# XML cleanup for human-readable output
# ──────────────────────────────────────────────────────────────────────
def clean_xml(raw, max_len=8000):
    """Strip XML markup, return readable LSJ entry text."""
    # Convert beta-code in <orth>, <foreign>, etc. to Greek
    txt = raw
    # Remove bibl elements (citations) for cleaner output
    txt = re.sub(r'<bibl\b[^>]*>.*?</bibl>', '[cite]', txt, flags=re.DOTALL)
    # Remove all other tags
    txt = re.sub(r'<[^>]+>', ' ', txt)
    # Collapse whitespace
    txt = re.sub(r'\s+', ' ', txt).strip()
    if len(txt) > max_len:
        txt = txt[:max_len] + f'\n... [truncated; full entry is {len(txt)} chars]'
    return txt

# ──────────────────────────────────────────────────────────────────────
# SBLGNT verse lookup
# ──────────────────────────────────────────────────────────────────────
SBL_BOOKS = {
    'matt':'Matt','mark':'Mark','luke':'Luke','john':'John',
    'matthew':'Matt',
    'acts':'Acts','rom':'Rom','romans':'Rom',
    '1cor':'1Cor','2cor':'2Cor','gal':'Gal','eph':'Eph','phil':'Phil',
    'col':'Col','1thess':'1Thess','2thess':'2Thess','1tim':'1Tim','2tim':'2Tim',
    'titus':'Titus','phlm':'Phlm','heb':'Heb','jas':'Jas','james':'Jas',
    '1pet':'1Pet','2pet':'2Pet','1john':'1John','2john':'2John','3john':'3John',
    'jude':'Jude','rev':'Rev','revelation':'Rev',
}

def lookup_verse(reference):
    """Return SBLGNT text for a reference like 'Matt 6:6' or 'Matt 6:6-9'."""
    m = re.match(r'(\d?\s*[A-Za-z]+)\s*(\d+):(\d+)(?:-(\d+))?', reference.strip())
    if not m:
        return None
    book_raw, ch, v1, v2 = m.groups()
    book_key = book_raw.lower().replace(' ', '')
    book = SBL_BOOKS.get(book_key)
    if not book:
        return None
    fpath = SBLGNT_TEXT_DIR / f'{book}.txt'
    if not fpath.exists():
        return None
    v1 = int(v1)
    v2 = int(v2) if v2 else v1
    results = []
    with open(fpath, 'r', encoding='utf-8') as f:
        for line in f:
            m2 = re.match(rf'^{book}\s+{ch}:(\d+)\s+(.+)', line)
            if m2:
                vnum = int(m2.group(1))
                if v1 <= vnum <= v2:
                    results.append(f'{book} {ch}:{vnum} {m2.group(2).strip()}')
    return '\n'.join(results) if results else None

# ──────────────────────────────────────────────────────────────────────
# TAGNT multi-edition lookup (STEPBible Translators Amalgamated GNT)
#   Source: github.com/STEPBible/STEPBible-Data (CC BY 4.0)
#   Editions tracked: NA28, NA27, SBL, Tyn (THGNT), Treg, WH, Byz, TR
# ──────────────────────────────────────────────────────────────────────
TAGNT_EDITIONS = ['NA28', 'NA27', 'SBL', 'Tyn', 'Treg', 'WH', 'Byz', 'TR']
TAGNT_FULL_SET = set(TAGNT_EDITIONS)
TAGNT_RENDER_ORDER = ['NA28', 'SBL', 'Tyn', 'Treg', 'WH', 'Byz', 'TR']

# TAGNT book abbreviations ↔ SBLGNT book names
TAGNT_TO_SBL = {
    'Mat':'Matt','Mrk':'Mark','Luk':'Luke','Jhn':'John',
    'Act':'Acts','Rom':'Rom',
    '1Co':'1Cor','2Co':'2Cor','Gal':'Gal','Eph':'Eph',
    'Php':'Phil','Col':'Col','1Th':'1Thess','2Th':'2Thess',
    '1Ti':'1Tim','2Ti':'2Tim','Tit':'Titus','Phm':'Phlm',
    'Heb':'Heb','Jas':'Jas','1Pe':'1Pet','2Pe':'2Pet',
    '1Jn':'1John','2Jn':'2John','3Jn':'3John','Jud':'Jude','Rev':'Rev',
}
SBL_TO_TAGNT = {v: k for k, v in TAGNT_TO_SBL.items()}

def _normalize_ref_to_tagnt(reference):
    """'Matt 6:13' or 'Mat 6:13' or 'Mat.6.13' → ('Mat', '6', 13, 13)."""
    m = re.match(r'(\d?\s*[A-Za-z]+)\s*(\d+)[:.](\d+)(?:-(\d+))?', reference.strip())
    if not m:
        return None, None, None, None
    book_raw, ch, v1, v2 = m.groups()
    book_key = book_raw.lower().replace(' ', '')
    sbl = SBL_BOOKS.get(book_key)
    tagnt_book = SBL_TO_TAGNT.get(sbl) if sbl else None
    if not tagnt_book:
        for tb in TAGNT_TO_SBL:
            if tb.lower() == book_key:
                tagnt_book = tb
                break
    if not tagnt_book:
        return None, None, None, None
    return tagnt_book, ch, int(v1), int(v2) if v2 else int(v1)

def build_tagnt_index():
    """Parse TAGNT txt files, build per-verse JSON index."""
    verses = {}
    files = sorted(TAGNT_DIR.glob('TAGNT_*.txt'))
    if not files:
        raise FileNotFoundError(f'No TAGNT_*.txt files in {TAGNT_DIR}')
    # Type codes include parens/mixed chars — N(k)O, N(K)O — so \S+, not \w+.
    # The old \w+ regex silently DROPPED every such word from every edition
    # (caught 2026-07-06: Mat 19:16 lost its verb, Luk 4:18 lost εὐαγγελίσασθαι).
    word_head_re = re.compile(r'^(\w+\.\d+\.\d+)#(\d+)=(\S+)$')
    greek_re = re.compile(r'(\S+)\s+\(([^)]+)\)')
    n_words = 0
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.rstrip('\n').rstrip('\r')
                if not line or line.startswith('#') or line.startswith('Word'):
                    continue
                parts = line.split('\t')
                if len(parts) < 6:
                    continue
                head_m = word_head_re.match(parts[0].strip())
                if not head_m:
                    continue
                ref, wn, wtype = head_m.groups()
                greek_field = parts[1].strip()
                gm = greek_re.match(greek_field)
                if gm:
                    greek, translit = gm.group(1), gm.group(2)
                else:
                    greek, translit = greek_field, ''
                english = parts[2].strip() if len(parts) > 2 else ''
                editions_field = parts[5].strip() if len(parts) > 5 else ''
                # Word-order suffixes (TR»4, Byz»3): the word IS in that
                # edition, N positions later. Membership tests broke on the
                # raw form and mis-reported divergences (Mat 26:23 τὴν χεῖρα
                # was reported "absent from Byz" — it moves, it doesn't vanish).
                eds, order_marks = [], {}
                for e in editions_field.split('+'):
                    if not e:
                        continue
                    if '»' in e:
                        name, _, off = e.partition('»')
                        eds.append(name)
                        try:
                            order_marks[name] = int(off)
                        except ValueError:
                            pass
                    else:
                        eds.append(e)
                # Column 6 holds the textual variant: the form OTHER editions
                # read, e.g. 'ἔχω (t=echō) I may have - G2192=V-PAS-1S in: TR+Byz'.
                # Ignoring it lost the Byzantine form wherever Byz reads a
                # different word than the critical text.
                var_field = parts[6].strip() if len(parts) > 6 else ''
                var_greek, var_eds = '', []
                if var_field and ' in: ' in var_field:
                    left, _, right = var_field.rpartition(' in: ')
                    var_eds = [e.split('»')[0] for e in right.strip().split('+') if e.strip()]
                    var_greek = left.split(' (')[0].strip()
                spelling_variants = parts[7].strip() if len(parts) > 7 else ''
                verses.setdefault(ref, []).append({
                    'n': int(wn),
                    'type': wtype,
                    'greek': greek,
                    'translit': translit,
                    'english': english,
                    'editions': eds,
                    'ord': order_marks,
                    'var_greek': var_greek,
                    'var_eds': var_eds,
                    'sv': spelling_variants,
                })
                n_words += 1
    for ref in verses:
        verses[ref].sort(key=lambda w: w['n'])
    with open(TAGNT_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(verses, f, ensure_ascii=False)
    return verses, n_words

def load_tagnt_index():
    if not TAGNT_INDEX_FILE.exists():
        verses, _ = build_tagnt_index()
        return verses
    with open(TAGNT_INDEX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _word_in(w, ed):
    """Is this word present in the given edition (main reading OR textual variant)?"""
    return ed in w['editions'] or ed in w.get('var_eds', [])

def _word_form(w, ed):
    """The form the given edition actually reads, or None if absent."""
    if ed in w['editions']:
        sv = _parse_spelling_variants(w['sv'])
        return sv.get(ed, w['greek'])
    if ed in w.get('var_eds', []):
        return w.get('var_greek') or w['greek']
    return None

def _edition_sequence(words, ed):
    """Words of a verse in the ORDER the given edition reads them, with the
    forms that edition reads. »N order marks move a word to after word n+N."""
    seq = []
    for w in words:
        form = _word_form(w, ed)
        if form is None:
            continue
        off = w.get('ord', {}).get(ed, 0)
        # Unmoved words sort at (n, 0); moved words sort just AFTER their
        # target position (n+off, 1), preserving their relative order.
        key = (w['n'] + off, 1 if off else 0, w['n'])
        seq.append((key, form))
    return [form for _, form in sorted(seq)]

def _parse_spelling_variants(sv_field):
    """'Tyn: Ἑσρώμ ; +TR: Δαβὶδ ;' → {'Tyn': 'Ἑσρώμ', 'TR': 'Δαβὶδ'}."""
    out = {}
    if not sv_field:
        return out
    for chunk in re.split(r'\s*;\s*', sv_field):
        chunk = chunk.strip().lstrip('+').strip()
        if not chunk:
            continue
        m = re.match(r'([A-Za-z]+)\s*:\s*(.+)', chunk)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out

def lookup_byzantine(reference):
    """Return Byzantine reading for a verse or range, with divergence flag.

    Output format per verse:
      Mat.5.22 [Byz] ἐγὼ δὲ λέγω ὑμῖν ὅτι πᾶς ὁ ὀργιζόμενος ... εἰκῆ ...
      (Divergence from modern critical: word 12 εἰκῆ — present in Byz+TR+Treg; absent in NA28+SBL+Tyn+WH)
    """
    tagnt_book, ch, v1, v2 = _normalize_ref_to_tagnt(reference)
    if not tagnt_book:
        return None
    verses = load_tagnt_index()
    MODERN = {'NA28', 'NA27', 'SBL', 'Tyn', 'Treg', 'WH'}
    output = []
    for v in range(v1, v2 + 1):
        ref = f"{tagnt_book}.{ch}.{v}"
        words = verses.get(ref)
        if not words:
            output.append(f"{ref} [Byz] (no data)")
            continue
        # Build Byzantine reading (variant- and word-order-aware)
        byz_text = ' '.join(_edition_sequence(words, 'Byz'))
        output.append(f"{ref} [Byz] {byz_text}")
        # Note divergences from modern critical consensus
        divergences = []
        for w in words:
            ed_set = {e for e in TAGNT_EDITIONS if _word_in(w, e)}
            in_byz = 'Byz' in ed_set
            in_modern_majority = len(ed_set & MODERN) >= 4  # 4 of 6 modern editions
            byz_form = _word_form(w, 'Byz')
            crit_form = _word_form(w, 'NA28') or _word_form(w, 'SBL')
            if in_byz and not in_modern_majority:
                divergences.append(
                    f"  + word {w['n']} '{byz_form}' ({w['english']}): "
                    f"in Byz; absent from most modern critical editions ({'+'.join(sorted(MODERN - ed_set))})"
                )
            elif in_modern_majority and not in_byz:
                divergences.append(
                    f"  - word {w['n']} '{w['greek']}' ({w['english']}): "
                    f"in modern critical ({'+'.join(e for e in TAGNT_EDITIONS if e in ed_set)}); absent from Byz"
                )
            elif in_byz and in_modern_majority and byz_form and crit_form and byz_form.strip(',;··.') != crit_form.strip(',;··.'):
                divergences.append(
                    f"  ≠ word {w['n']}: Byz reads '{byz_form}', critical reads '{crit_form}'"
                )
            if w.get('ord', {}).get('Byz'):
                divergences.append(
                    f"  ≈ word {w['n']} '{byz_form}': position differs in Byz (word-order variant; "
                    f"rendered order above follows Byz)"
                )
        if divergences:
            output.append("  (Divergences from modern critical:)")
            output.extend(divergences)
    return '\n'.join(output) if output else None

def lookup_editions(reference):
    """Render multi-edition view for a verse or verse range."""
    tagnt_book, ch, v1, v2 = _normalize_ref_to_tagnt(reference)
    if not tagnt_book:
        return None
    verses = load_tagnt_index()
    output = []
    found_any = False
    for v in range(v1, v2 + 1):
        ref = f"{tagnt_book}.{ch}.{v}"
        words = verses.get(ref)
        if not words:
            output.append(f"=== {ref} ===")
            output.append("(no data — verse not in TAGNT, may be a versification difference)")
            output.append("")
            continue
        found_any = True
        output.append(f"=== {ref} — Multi-edition view ===")
        full_agreement = all(
            set(w['editions']) == TAGNT_FULL_SET and not w['sv'] and not w.get('var_eds')
            for w in words
        )
        if full_agreement:
            text = ' '.join(w['greek'] for w in words)
            output.append('All editions agree (NA28 NA27 SBL Tyn Treg WH Byz TR):')
            output.append(f'  {text}')
            output.append('')
            continue
        # Per-edition rendering (variant- and word-order-aware)
        for ed in TAGNT_RENDER_ORDER:
            ed_words = _edition_sequence(words, ed)
            label = f'{ed:>5s}:'
            if ed_words:
                output.append(f'{label} {" ".join(ed_words)}')
            else:
                output.append(f'{label} (verse absent in this edition)')
        # Divergences
        divergences = []
        for w in words:
            ed_set = set(w['editions'])
            if ed_set != TAGNT_FULL_SET:
                only_in = '+'.join(e for e in TAGNT_EDITIONS if e in ed_set)
                absent = '+'.join(e for e in TAGNT_EDITIONS if e not in ed_set)
                divergences.append(
                    f"  Word {w['n']} ({w['greek']}, '{w['english']}'): "
                    f"only in {only_in}; absent from {absent}"
                )
            if w['sv']:
                divergences.append(
                    f"  Word {w['n']} ({w['greek']}): spelling variants — {w['sv']}"
                )
        if divergences:
            output.append('')
            output.append('Divergences:')
            output.extend(divergences)
        output.append('')
    return '\n'.join(output).rstrip() if found_any or output else None

# ──────────────────────────────────────────────────────────────────────
# LXX (Septuagint) verse lookup and search
#   Source: Perseus Digital Library, edited by Henry Barclay Swete
#           (University of Leipzig / First Thousand Years of Greek project)
#   Format: TEI XML, tlg0527.tlgNNN.1st1K-grc1.xml
# ──────────────────────────────────────────────────────────────────────
LXX_DIR = ROOT / "lxx_septuagint"

# Book abbreviation → TLG code. Multiple abbreviations map to the same code.
LXX_BOOKS = {
    'gen': 'tlg001', 'genesis': 'tlg001', 'gn': 'tlg001',
    'ex': 'tlg002', 'exod': 'tlg002', 'exodus': 'tlg002',
    'lev': 'tlg003', 'leviticus': 'tlg003', 'lv': 'tlg003',
    'num': 'tlg004', 'numbers': 'tlg004', 'nm': 'tlg004', 'nu': 'tlg004',
    'deut': 'tlg005', 'deuteronomy': 'tlg005', 'dt': 'tlg005', 'dtn': 'tlg005',
    'josh': 'tlg006', 'joshua': 'tlg006', 'jos': 'tlg006', 'jsh': 'tlg006',
    'judg': 'tlg008', 'judges': 'tlg008', 'jgs': 'tlg008', 'jdg': 'tlg008',
    'ruth': 'tlg010', 'rth': 'tlg010', 'ru': 'tlg010',
    # Kingdoms use LXX numbering (Bas A = 1 Sam, Bas B = 2 Sam, Bas C = 1 Ki, Bas D = 2 Ki)
    '1sam': 'tlg011', '1sm': 'tlg011', '1samuel': 'tlg011', '1kgdms': 'tlg011',
    '2sam': 'tlg012', '2sm': 'tlg012', '2samuel': 'tlg012', '2kgdms': 'tlg012',
    '1kgs': 'tlg013', '1ki': 'tlg013', '1kings': 'tlg013', '3kgdms': 'tlg013',
    '2kgs': 'tlg014', '2ki': 'tlg014', '2kings': 'tlg014', '4kgdms': 'tlg014',
    '1chr': 'tlg015', '1chron': 'tlg015', '1chronicles': 'tlg015', '1par': 'tlg015',
    '2chr': 'tlg016', '2chron': 'tlg016', '2chronicles': 'tlg016', '2par': 'tlg016',
    '1esd': 'tlg017', '1esdras': 'tlg017',
    '2esd': 'tlg018', '2esdras': 'tlg018', 'ezra': 'tlg018', 'ezr': 'tlg018', 'neh': 'tlg018',
    'esth': 'tlg019', 'esther': 'tlg019', 'est': 'tlg019',
    'jdt': 'tlg020', 'judith': 'tlg020',
    'tob': 'tlg021', 'tobit': 'tlg021', 'tb': 'tlg021',
    '1mac': 'tlg023', '1macc': 'tlg023', '1maccabees': 'tlg023', '1mc': 'tlg023',
    '2mac': 'tlg024', '2macc': 'tlg024', '2maccabees': 'tlg024', '2mc': 'tlg024',
    '3mac': 'tlg025', '3macc': 'tlg025', '3maccabees': 'tlg025', '3mc': 'tlg025',
    '4mac': 'tlg026', '4macc': 'tlg026', '4maccabees': 'tlg026', '4mc': 'tlg026',
    'ps': 'tlg027', 'psa': 'tlg027', 'psalm': 'tlg027', 'psalms': 'tlg027',
    'ode': 'tlg028', 'odes': 'tlg028',
    'prov': 'tlg029', 'proverbs': 'tlg029', 'pr': 'tlg029', 'prv': 'tlg029',
    'song': 'tlg031', 'songofsongs': 'tlg031', 'ss': 'tlg031',
    'cant': 'tlg031', 'canticles': 'tlg031',
    'job': 'tlg032', 'jb': 'tlg032',
    'wis': 'tlg033', 'wisdom': 'tlg033', 'wisdomofsolomon': 'tlg033',
    'sir': 'tlg034', 'sirach': 'tlg034', 'ecclesiasticus': 'tlg034', 'eccli': 'tlg034',
    'pssol': 'tlg035', 'psalmsofsolomon': 'tlg035',
    'hos': 'tlg036', 'hosea': 'tlg036',
    'amos': 'tlg037', 'am': 'tlg037',
    'mic': 'tlg038', 'micah': 'tlg038',
    'joel': 'tlg039', 'jl': 'tlg039',
    'obad': 'tlg040', 'obadiah': 'tlg040', 'ob': 'tlg040',
    'jon': 'tlg041', 'jonah': 'tlg041',
    'nah': 'tlg042', 'nahum': 'tlg042',
    'hab': 'tlg043', 'habakkuk': 'tlg043',
    'zeph': 'tlg044', 'zephaniah': 'tlg044', 'zep': 'tlg044',
    'hag': 'tlg045', 'haggai': 'tlg045',
    'zech': 'tlg046', 'zechariah': 'tlg046', 'zec': 'tlg046',
    'mal': 'tlg047', 'malachi': 'tlg047',
    'isa': 'tlg048', 'isaiah': 'tlg048', 'is': 'tlg048',
    'jer': 'tlg049', 'jeremiah': 'tlg049',
    'bar': 'tlg050', 'baruch': 'tlg050',
    'lam': 'tlg051', 'lamentations': 'tlg051',
    'epjer': 'tlg052', 'epistleofjeremiah': 'tlg052', 'letjer': 'tlg052',
    'ezk': 'tlg053', 'ezek': 'tlg053', 'ezekiel': 'tlg053',
    'sus': 'tlg054', 'susanna': 'tlg054',
    'sus-th': 'tlg055', 'susanna-th': 'tlg055', 'susth': 'tlg055',
    'dan': 'tlg056', 'daniel': 'tlg056',
    'dan-th': 'tlg057', 'daniel-th': 'tlg057', 'danth': 'tlg057',
    'bel': 'tlg058', 'belanddragon': 'tlg058',
    'bel-th': 'tlg059', 'belanddragon-th': 'tlg059', 'belth': 'tlg059',
}

# TLG code → (canonical English title, Greek title). Loaded from manifest.json.
_LXX_MANIFEST_CACHE = None
def _load_lxx_manifest():
    global _LXX_MANIFEST_CACHE
    if _LXX_MANIFEST_CACHE is not None:
        return _LXX_MANIFEST_CACHE
    mf = LXX_DIR / 'manifest.json'
    with open(mf, 'r', encoding='utf-8') as f:
        mdata = json.load(f)
    # Build tlg_code → list of files (some have grc1, grc2 variants)
    by_code = {}
    for w in mdata.get('works', []):
        code = w['tlg_code']
        by_code.setdefault(code, []).append(w)
    _LXX_MANIFEST_CACHE = by_code
    return by_code

def _resolve_lxx_book(book_raw):
    """Book abbreviation → TLG code, or None."""
    key = book_raw.lower().replace(' ', '').replace('.', '')
    return LXX_BOOKS.get(key)

def _lxx_file_for(tlg_code, prefer_variant='grc1'):
    """Return the XML file path for a TLG code, preferring grc1 by default."""
    manifest = _load_lxx_manifest()
    if tlg_code not in manifest:
        return None
    works = manifest[tlg_code]
    # Prefer the variant asked for
    for w in works:
        if prefer_variant in w['file']:
            return LXX_DIR / w['file']
    return LXX_DIR / works[0]['file']

def _strip_apparatus(xml_snippet):
    """Remove notes, page/line breaks, and other apparatus markup from a verse's XML."""
    txt = xml_snippet
    # Drop <note>...</note> completely (footnotes, marginal apparatus)
    txt = re.sub(r'<note\b[^>]*>.*?</note>', '', txt, flags=re.DOTALL)
    # Drop <lb .../> and <pb .../> and other empty self-closing tags
    txt = re.sub(r'<(lb|pb|milestone)\b[^>]*/?>', ' ', txt)
    # Keep text inside <p>, <hi>, <emph>, <foreign>; strip the tags
    txt = re.sub(r'</?(p|hi|emph|foreign|q|quote|said|seg)\b[^>]*>', '', txt)
    # Strip any remaining tags conservatively
    txt = re.sub(r'<[^>]+>', ' ', txt)
    # Collapse whitespace
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def _extract_verse_xml(xml_data, chapter, verse):
    """Find the verse's inner XML content (without the wrapping <div>) inside chapter."""
    # Find the chapter's div
    ch_pat = re.compile(
        rb'<div\b[^>]*\bsubtype="chapter"[^>]*\bn="' + str(chapter).encode() + rb'"[^>]*>',
    )
    ch_m = ch_pat.search(xml_data)
    if not ch_m:
        return None
    # Chapter body ends at the next chapter div or the end of the edition div
    chapter_start = ch_m.end()
    next_ch = re.search(
        rb'<div\b[^>]*\bsubtype="chapter"',
        xml_data[chapter_start:],
    )
    chapter_end = chapter_start + (next_ch.start() if next_ch else len(xml_data) - chapter_start)
    chapter_body = xml_data[chapter_start:chapter_end]
    # Find the verse within the chapter
    v_pat = re.compile(
        rb'<div\b[^>]*\bsubtype="verse"[^>]*\bn="' + str(verse).encode() + rb'"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    v_m = v_pat.search(chapter_body)
    if not v_m:
        return None
    return v_m.group(1).decode('utf-8', errors='replace')

def _parse_lxx_ref(reference):
    """'Gen 14:13' or 'Gen.14.13' or 'Gen 14:13-15' → (tlg_code, ch, v1, v2)."""
    m = re.match(r'(\d?\s*[A-Za-z][A-Za-z\-]*)\s*(\d+)[:.](\d+)(?:-(\d+))?', reference.strip())
    if not m:
        return None, None, None, None
    book_raw, ch, v1, v2 = m.groups()
    tlg_code = _resolve_lxx_book(book_raw)
    if not tlg_code:
        return None, None, None, None
    return tlg_code, int(ch), int(v1), int(v2) if v2 else int(v1)

def lookup_lxx_verse(reference, edition='grc1'):
    """Return LXX text for a reference like 'Gen 14:13' or 'Ex 1:15-22'.

    edition: 'grc1' (default; Swete for most books, LXX version for
    Daniel/Susanna/Bel) or 'grc2' (Theodotion for Daniel/Susanna/Bel,
    alternate manuscript for Isaiah/Sirach).
    """
    tlg_code, ch, v1, v2 = _parse_lxx_ref(reference)
    if not tlg_code:
        return None
    fpath = _lxx_file_for(tlg_code, prefer_variant=edition)
    if not fpath or not fpath.exists():
        return None
    with open(fpath, 'rb') as f:
        xml_data = f.read()
    manifest = _load_lxx_manifest()
    title = manifest[tlg_code][0]['title']
    lines = []
    for v in range(v1, v2 + 1):
        raw = _extract_verse_xml(xml_data, ch, v)
        if raw is None:
            lines.append(f"{title} {ch}:{v} (no data)")
        else:
            text = _strip_apparatus(raw)
            lines.append(f"{title} {ch}:{v} [LXX] {text}")
    return '\n'.join(lines) if lines else None

def lookup_lxx_editions(reference):
    """Return all available editions of a verse (grc1 + grc2 if both exist)."""
    tlg_code, ch, v1, v2 = _parse_lxx_ref(reference)
    if not tlg_code:
        return None
    manifest = _load_lxx_manifest()
    works = manifest.get(tlg_code, [])
    if not works:
        return None
    title = works[0]['title']
    out = [f"=== {title} {ch}:{v1}{'-'+str(v2) if v2 != v1 else ''} — Multi-edition view ==="]
    for w in works:
        fpath = LXX_DIR / w['file']
        with open(fpath, 'rb') as f:
            xml_data = f.read()
        variant = 'grc2' if 'grc2' in w['file'] else 'grc1'
        label = f"{variant} ({w['title']})"
        for v in range(v1, v2 + 1):
            raw = _extract_verse_xml(xml_data, ch, v)
            if raw is None:
                out.append(f"[{label}] {ch}:{v}: (no data)")
            else:
                text = _strip_apparatus(raw)
                out.append(f"[{label}] {ch}:{v}: {text}")
    return '\n'.join(out)

# ── Classical corpus search (all authors) ──────────────────────────
# The ~46 author directories (Plato ... Galen, Ptolemy, patristics) hold
# ~250MB of TEI XML — too much to fold per query. build_corpus_index()
# extracts plain text once into corpus-index.jsonl segments keyed by
# author / work / location (Stephanus, Bekker, chapter, Book); queries
# stream that file. Rebuild after adding an author: greek_lookup.py build-corpus

CORPUS_INDEX_FILE = SCRIPT_DIR / 'corpus-index.jsonl' if 'SCRIPT_DIR' in dir() else Path(__file__).resolve().parent / 'corpus-index.jsonl'
CORPUS_EXCLUDE = {'lxx_septuagint', 'sblgnt', 'tagnt', 'lsj-xml', 'lexica',
                  'proper-nouns', '__pycache__'}

_CORPUS_TAG_RE = re.compile(
    r'<div[^>]*subtype="([^"]+)"[^>]*\bn="([^"]+)"[^>]*>'
    r'|<milestone[^>]*unit="([^"]+)"[^>]*\bn="([^"]+)"[^>]*/?>'
    r'|<note\b.*?</note>'
    r'|<[^>]+>',
    re.DOTALL)


def _corpus_extract_segments(xml_text):
    """Yield (location, text) segments from a TEI file. Location = last-seen
    textpart div (chapter/section/Book) + last milestone (Stephanus/page)."""
    div_loc, mile_loc = '', ''
    buf = []
    pos = 0
    def flush():
        text = re.sub(r'\s+', ' ', ''.join(buf)).strip()
        buf.clear()
        if len(text) >= 20:
            loc = ', '.join(x for x in (div_loc, mile_loc) if x)
            return (loc or '—', text)
        return None
    for m in _CORPUS_TAG_RE.finditer(xml_text):
        buf.append(xml_text[pos:m.start()])
        pos = m.end()
        if m.group(1) and m.group(1) != 'edition':          # textpart div
            seg = flush()
            if seg: yield seg
            div_loc = f"{m.group(1)} {m.group(2)}"
            mile_loc = ''
        elif m.group(3):                                     # milestone
            seg = flush()
            if seg: yield seg
            mile_loc = f"{m.group(3)} {m.group(4)}"
    buf.append(xml_text[pos:])
    seg = flush()
    if seg: yield seg


def build_corpus_index(only_author=None):
    """One-time (or incremental per-author) build of corpus-index.jsonl."""
    base = Path(__file__).resolve().parent
    out_path = base / 'corpus-index.jsonl'
    mode = 'w'
    if only_author and out_path.exists():
        # incremental: drop that author's lines, append fresh
        kept = [l for l in out_path.read_text(encoding='utf-8').splitlines()
                if json.loads(l)['a'] != only_author]
        out_path.write_text('\n'.join(kept) + ('\n' if kept else ''), encoding='utf-8')
        mode = 'a'
    n_seg = n_work = 0
    with open(out_path, mode, encoding='utf-8') as out:
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.name in CORPUS_EXCLUDE:
                continue
            if only_author and d.name != only_author:
                continue
            mpath = d / 'manifest.json'
            if not mpath.exists():
                continue
            manifest = json.loads(mpath.read_text(encoding='utf-8'))
            works = manifest.get('works', [])
            for w in works:
                fpath = d / Path(w.get('file', w.get('path', ''))).name
                if not fpath.exists():
                    continue
                xml_text = fpath.read_text(encoding='utf-8', errors='replace')
                title = w.get('title', fpath.stem)
                for loc, text in _corpus_extract_segments(xml_text):
                    rec = {'a': d.name, 'w': title, 'l': loc, 't': text,
                           'f': _fold_diacritics(text).lower()}
                    out.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    n_seg += 1
                n_work += 1
                print(f"  {d.name}: {title} indexed", file=sys.stderr)
    print(f"Corpus index: {n_work} works, {n_seg} segments → {out_path}")


def list_corpus_authors():
    base = Path(__file__).resolve().parent
    authors = sorted(d.name for d in base.iterdir()
                     if d.is_dir() and d.name not in CORPUS_EXCLUDE
                     and (d / 'manifest.json').exists())
    return f"{len(authors)} searchable authors:\n" + '\n'.join(f"  {a}" for a in authors)


def search_corpus(word, author=None, max_results=25, context_chars=100):
    """Diacritic- and case-insensitive substring search across every indexed
    classical author. Returns citations (author, work, location) + context."""
    base = Path(__file__).resolve().parent
    idx = base / 'corpus-index.jsonl'
    if not idx.exists():
        return ("Corpus index missing — run: greek_lookup.py build-corpus "
                "(one-time, a few minutes)")
    needle = _fold_diacritics(unicodedata.normalize('NFC', word)).lower()
    results = []
    truncated = False
    with open(idx, 'r', encoding='utf-8') as f:
        for line in f:
            if author and f'"a": "{author}' not in line and f'"a":"{author}' not in line:
                continue
            if needle not in line:          # cheap prefilter on raw line
                continue
            rec = json.loads(line)
            pos = rec['f'].find(needle)
            if pos < 0:
                continue
            # map folded position → display position by folding a prefix walk
            disp = rec['t']
            cnt, dpos = 0, 0
            for i, chd in enumerate(disp):
                if cnt >= pos:
                    dpos = i
                    break
                if unicodedata.category(unicodedata.normalize('NFD', chd)[0]) != 'Mn':
                    cnt += len(_fold_diacritics(chd))
            c1 = max(0, dpos - context_chars)
            c2 = min(len(disp), dpos + len(needle) + context_chars)
            ctx = ('…' if c1 else '') + disp[c1:c2] + ('…' if c2 < len(disp) else '')
            results.append(f"[{rec['a']}] {rec['w']}, {rec['l']}\n    {ctx}")
            if len(results) >= max_results:
                truncated = True
                break
    if not results:
        return (f"No occurrences of '{word}' in the classical corpus"
                + (f" (author={author})" if author else "") + ".")
    head = (f"Corpus search for '{word}'"
            + (f" in {author}" if author else "")
            + f" — {len(results)} result(s)"
            + (" (truncated; raise --max or filter by --author)" if truncated else "")
            + ":\n")
    return head + '\n'.join(results)


def _fold_diacritics(s):
    """Strip Greek diacritics (breathings, accents, iota subscript) for search-only matching.
    Preserves letter case initially; caller can lower() if diacritic-and-case-insensitive."""
    # Normalize to NFD (decompose combining marks), drop combining marks, recompose
    decomp = unicodedata.normalize('NFD', s)
    stripped = ''.join(c for c in decomp if unicodedata.category(c) != 'Mn')
    return unicodedata.normalize('NFC', stripped)

def search_lxx(word, max_results=50, context_chars=80, book_filter=None, ignore_diacritics=True):
    """Find every LXX occurrence of a Greek substring; report citations + context.

    ignore_diacritics: if True (default), search folds accents/breathings/iota subscripts
    on both needle and haystack. Enables finding περάτῃ with a search for 'περατ' or
    'περατη'. Set False for exact-form matching."""
    manifest = _load_lxx_manifest()
    # Normalize search word
    needle_raw = unicodedata.normalize('NFC', word)
    if ignore_diacritics:
        needle = _fold_diacritics(needle_raw).lower()
    else:
        needle = needle_raw
    results = []
    # Iterate books in TLG order
    for code in sorted(manifest.keys()):
        for w in manifest[code]:
            if book_filter and book_filter.lower() not in w['title'].lower():
                continue
            fpath = LXX_DIR / w['file']
            with open(fpath, 'r', encoding='utf-8') as f:
                raw = f.read()
            # Walk chapter+verse divs, look for the needle
            # This is slow-ish but LXX is only ~600k words total.
            for ch_m in re.finditer(
                r'<div\b[^>]*\bsubtype="chapter"[^>]*\bn="(\d+)"[^>]*>',
                raw,
            ):
                chapter = ch_m.group(1)
                ch_start = ch_m.end()
                next_ch = re.search(
                    r'<div\b[^>]*\bsubtype="chapter"',
                    raw[ch_start:],
                )
                ch_end = ch_start + (next_ch.start() if next_ch else len(raw) - ch_start)
                for v_m in re.finditer(
                    r'<div\b[^>]*\bsubtype="verse"[^>]*\bn="(\d+)"[^>]*>(.*?)</div>',
                    raw[ch_start:ch_end],
                    re.DOTALL,
                ):
                    verse = v_m.group(1)
                    verse_text = _strip_apparatus(v_m.group(2))
                    verse_display = unicodedata.normalize('NFC', verse_text)
                    if ignore_diacritics:
                        haystack = _fold_diacritics(verse_display).lower()
                    else:
                        haystack = verse_display
                    if needle in haystack:
                        # Find position in haystack, then map back to verse_display for context
                        pos = haystack.find(needle)
                        c1 = max(0, pos - context_chars)
                        c2 = min(len(verse_display), pos + len(needle) + context_chars)
                        context = verse_display[c1:c2]
                        if c1 > 0:
                            context = '…' + context
                        if c2 < len(verse_display):
                            context = context + '…'
                        results.append({
                            'reference': f"{w['title']} {chapter}:{verse}",
                            'context': context,
                        })
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break
    if not results:
        return f"No LXX occurrences of '{word}' found."
    out = [f"LXX search for '{word}' — {len(results)}"
           + (f' (max, further hits exist)' if len(results) >= max_results else '')
           + ':', '']
    for r in results:
        out.append(f"{r['reference']}: {r['context']}")
    return '\n'.join(out)

def list_lxx_books():
    """Return the LXX book list with TLG codes and Greek/English titles."""
    manifest = _load_lxx_manifest()
    # Build reverse map: tlg_code → canonical English name from LXX_BOOKS
    canonical = {}
    for eng, code in LXX_BOOKS.items():
        # Prefer longer / more standard names
        if code not in canonical or len(eng) > len(canonical[code]):
            canonical[code] = eng
    out = ['LXX books available in the greek-resources server:', '']
    out.append(f"{'TLG code':<10} {'Greek title':<40} {'Ref abbr':<20}")
    out.append('-' * 75)
    for code in sorted(manifest.keys()):
        for w in manifest[code]:
            variant = 'grc2' if 'grc2' in w['file'] else 'grc1'
            marker = f"{code}/{variant}" if variant == 'grc2' else code
            out.append(f"{marker:<10} {w['title']:<40} {canonical.get(code, '(unknown)'):<20}")
    return '\n'.join(out)

# ══════════════════════════════════════════════════════════════════════
# PROPER-NOUN LOOKUPS — William Smith's three dictionaries + Middle Liddell
# Source: Perseus canonical-pdlrefwk, CC-BY-SA-4.0
#   Smith, Geography         (10,292 entries) — proper nouns of place
#   Smith, Biography & Myth  (19,893 entries) — proper nouns of person / god / hero
#   Smith, Antiquities       (3,409 entries)  — Greco-Roman institutions, customs, terms
#   Middle Liddell (LSJ Int) (36,494 entries) — intermediate Greek-English lexicon
# ══════════════════════════════════════════════════════════════════════
PROPNOUN_DIR = ROOT / "proper-nouns"

PROPNOUN_XML = {
    'geo': PROPNOUN_DIR / "smith-geography.xml",
    'bio': PROPNOUN_DIR / "smith-biography.xml",
    'cn':  PROPNOUN_DIR / "smith-antiquities.xml",
    'ml':  PROPNOUN_DIR / "middle-liddell.xml",
}

PROPNOUN_INDEX_FILE = {
    'geo': ROOT / "smith-geo-index.json",
    'bio': ROOT / "smith-bio-index.json",
    'cn':  ROOT / "smith-ant-index.json",
    'ml':  ROOT / "middle-liddell-index.json",
}

PROPNOUN_LABEL = {
    'geo': "Smith, Dictionary of Greek and Roman Geography (1854)",
    'bio': "Smith, Dictionary of Greek and Roman Biography and Mythology",
    'cn':  "Smith, Dictionary of Greek and Roman Antiquities (1890)",
    'ml':  "Liddell-Scott, Intermediate Greek-English Lexicon (Middle Liddell)",
}

# Per-corpus locators — where to find the entry-start byte offsets in the XML
# Each returns a list of (key, start_offset, end_offset) tuples.
def _scan_smith_entries(data, kind_suffix):
    """Smith uses <div type='entry' xml:id='X-KIND'> OR
    <div type='textpart' subtype='entry' xml:id='X-KIND-N'>.
    Linear one-pass token walk: find every <div> open and </div> close,
    then match entry-open divs to their matching close by depth-tracking."""
    # One linear scan for every div token (open OR close).
    tokens = []  # list of (position_end, kind, xml_id_or_None)
    for m in re.finditer(rb'<div\b([^>]*)>|</div>', data):
        if m.group(0).startswith(b'</'):
            tokens.append((m.start(), m.end(), 'close', None, None))
        else:
            attrs = m.group(1) or b''
            xml_id = None
            entry_flag = False
            id_m = re.search(rb'\bxml:id="([^"]+)"', attrs)
            if id_m:
                xml_id = id_m.group(1).decode('utf-8', errors='replace')
            # entry classification: either type="entry" or subtype="entry"
            if re.search(rb'\btype="entry"', attrs) or re.search(rb'\bsubtype="entry"', attrs):
                entry_flag = True
            tokens.append((m.start(), m.end(), 'open', xml_id, entry_flag))

    hits = []
    stack = []  # entries currently open, as (key, start_offset, depth_at_open)
    depth = 0
    for start, end, ttype, xml_id, entry_flag in tokens:
        if ttype == 'open':
            depth += 1
            if entry_flag and xml_id:
                stack.append((xml_id, start, depth))
        else:  # close
            # Pop any entry frames that were opened at this depth
            while stack and stack[-1][2] == depth:
                key, ent_start, _ = stack.pop()
                hits.append((key, ent_start, end))
            depth -= 1
    return hits

def _scan_middle_liddell_entries(data):
    """Middle Liddell uses <entry ... key='beta-code'>...</entry>."""
    hits = []
    for m in re.finditer(rb'<entry\b[^>]*\bkey="([^"]+)"[^>]*>', data):
        key = m.group(1).decode('utf-8', errors='replace')
        start = m.start()
        end_m = re.search(rb'</entry>', data[start:])
        if not end_m:
            continue
        hits.append((key, start, start + end_m.end()))
    return hits

def build_propnoun_index(kind):
    """Build a key→[(offset, length), ...] index for one proper-noun XML."""
    xml_path = PROPNOUN_XML[kind]
    if not xml_path.exists():
        return {}
    with open(xml_path, 'rb') as f:
        data = f.read()
    if kind == 'ml':
        hits = _scan_middle_liddell_entries(data)
    else:
        hits = _scan_smith_entries(data, kind)
    index = {}
    for key, start, end in hits:
        entry = (start, end - start)
        if key in index:
            existing = index[key]
            # normalize to list of tuples
            if isinstance(existing, list) and existing and isinstance(existing[0], list):
                existing.append(list(entry))
                index[key] = existing
            elif isinstance(existing, list):
                # already a single tuple as list
                index[key] = [existing, list(entry)]
            else:
                index[key] = [list(existing), list(entry)]
        else:
            index[key] = list(entry)
    with open(PROPNOUN_INDEX_FILE[kind], 'w', encoding='utf-8') as f:
        json.dump(index, f)
    return index

def load_propnoun_index(kind):
    idx_file = PROPNOUN_INDEX_FILE[kind]
    if not idx_file.exists():
        return build_propnoun_index(kind)
    with open(idx_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def _clean_smith_entry(raw, max_len=6000):
    """Convert a Smith TEI XML entry to readable plain text.
    Preserves Greek text; strips markup; converts beta-code labels to Greek."""
    txt = raw
    # Convert Greek-labelled runs from beta-code to Unicode where used.
    # Note: xml:lang="greek" attribute may be split across lines with intervening
    # whitespace before the closing >; allow any whitespace/attrs before it.
    def beta_to_uni(m):
        return _beta_to_greek(m.group(1))
    txt = re.sub(r'<label\b[^>]*\bxml:lang="greek"[^>]*>\s*([^<]+?)\s*</label>',
                 beta_to_uni, txt, flags=re.DOTALL)
    txt = re.sub(r'<foreign\b[^>]*\bxml:lang="greek"[^>]*>\s*([^<]+?)\s*</foreign>',
                 beta_to_uni, txt, flags=re.DOTALL)
    txt = re.sub(r'<orth\b[^>]*\blang="greek"[^>]*>\s*([^<]+?)\s*</orth>',
                 beta_to_uni, txt, flags=re.DOTALL)
    # Preserve <head> as bold-ish markers by wrapping
    txt = re.sub(r'<head>(.*?)</head>', r'\n**\1**\n', txt, flags=re.DOTALL)
    # <bibl> content becomes bracketed citations
    txt = re.sub(r'<bibl\b[^>]*>(.*?)</bibl>', r'[\1]', txt, flags=re.DOTALL)
    # Remove titles/etc.
    txt = re.sub(r'<title\b[^>]*>(.*?)</title>', r'\1', txt, flags=re.DOTALL)
    # Remove all other tags
    txt = re.sub(r'<[^>]+>', ' ', txt)
    # HTML entities — convert common named entities to Unicode
    _ENTITY_MAP = {
        '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'",
        '&aacute;': 'á', '&eacute;': 'é', '&iacute;': 'í', '&oacute;': 'ó', '&uacute;': 'ú',
        '&Aacute;': 'Á', '&Eacute;': 'É', '&Iacute;': 'Í', '&Oacute;': 'Ó', '&Uacute;': 'Ú',
        '&acute;': '́', '&grave;': '̀', '&circ;': '̂', '&macr;': '̄',
        '&ntilde;': 'ñ', '&Ntilde;': 'Ñ', '&ccedil;': 'ç', '&Ccedil;': 'Ç',
        '&auml;': 'ä', '&euml;': 'ë', '&iuml;': 'ï', '&ouml;': 'ö', '&uuml;': 'ü',
        '&Auml;': 'Ä', '&Ouml;': 'Ö', '&Uuml;': 'Ü',
        '&ecirc;': 'ê', '&ocirc;': 'ô', '&ucirc;': 'û', '&acirc;': 'â', '&icirc;': 'î',
        '&nbsp;': ' ', '&mdash;': '—', '&ndash;': '–', '&hellip;': '…',
        '&lsquo;': '‘', '&rsquo;': '’', '&ldquo;': '“', '&rdquo;': '”',
        '&larr;': '←', '&rarr;': '→', '&uarr;': '↑', '&darr;': '↓',
        '&deg;': '°',
    }
    for ent, uni in _ENTITY_MAP.items():
        txt = txt.replace(ent, uni)
    txt = re.sub(r'&([a-zA-Z]+);', r'[\1]', txt)  # remaining named entities visible
    # Collapse whitespace
    txt = re.sub(r'[ \t]+', ' ', txt)
    txt = re.sub(r'\n[ \t]+', '\n', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt).strip()
    if len(txt) > max_len:
        txt = txt[:max_len] + f'\n... [truncated; full entry is {len(txt)} chars]'
    return txt

# Reverse map: Perseus beta-code (in Smith / Middle Liddell keys) → Unicode Greek
# Force σ (medial) rather than ς — post-processed to final sigma below.
_BETA_TO_UNI = {}
for k, v in UNI_TO_BETA.items():
    if v == 's' and k == 'ς':
        continue  # skip ς so σ wins the reverse map
    _BETA_TO_UNI[v] = k

_BETA_DIACRITIC = {
    '/': '́',   # acute
    '\\': '̀',  # grave
    '=': '͂',   # circumflex (perispomeni)
    '(': '̔',   # rough breathing
    ')': '̓',   # smooth breathing
    '|': 'ͅ',   # iota subscript
    '+': '̈',   # diaeresis
}

def _beta_to_greek(beta):
    """Convert Perseus beta-code text to Unicode Greek. Best-effort.
    Handles both '*e(' (star-letter-diacritic) and '*(e' (star-diacritic-letter)
    orderings for capitalized letters with breathings."""
    if not beta:
        return ""
    beta = beta.strip()
    out = []
    i = 0
    n = len(beta)
    while i < n:
        c = beta[i]
        cap = False
        prefix_diacritics = ''
        if c == '*':
            cap = True
            i += 1
            # Perseus alt convention: diacritics BEFORE the letter, e.g. '*(e' = Ἑ
            while i < n and beta[i] in _BETA_DIACRITIC:
                prefix_diacritics += _BETA_DIACRITIC[beta[i]]
                i += 1
            if i >= n:
                break
            c = beta[i]
        target = _BETA_TO_UNI.get(c.lower())
        if target is None:
            # Non-letter (space, punct) — pass through
            out.append(c)
            i += 1
            continue
        if cap:
            target = target.upper()
        # Consume trailing diacritic marks (standard convention: after letter)
        suffix_diacritics = ''
        j = i + 1
        while j < n and beta[j] in _BETA_DIACRITIC:
            suffix_diacritics += _BETA_DIACRITIC[beta[j]]
            j += 1
        composed = unicodedata.normalize('NFC', target + prefix_diacritics + suffix_diacritics)
        out.append(composed)
        i = j
    result = ''.join(out)
    # Word-final sigma: σ at end of word (before space/punct or EOL) → ς
    result = re.sub(r'σ(?=[\s.,;·:!?)\]}»›"]|$)', 'ς', result)
    return result

def _clean_middle_liddell_entry(raw, max_len=4000):
    """Middle Liddell entries are already Unicode Greek in <orth>."""
    txt = raw
    txt = re.sub(r'<orth\b[^>]*>([^<]+)</orth>', r'**\1**', txt)
    # Convert any beta-code <ref>...</ref> to Greek Unicode
    def beta_ref(m):
        return _beta_to_greek(m.group(1))
    txt = re.sub(r'<ref[^>]*lang="greek"[^>]*>([^<]+)</ref>', beta_ref, txt)
    # Trans → readable
    txt = re.sub(r'<tr\b[^>]*>([^<]+)</tr>', r'"\1"', txt)
    # Bibl → bracketed
    txt = re.sub(r'<bibl\b[^>]*>(.*?)</bibl>', r'[\1]', txt, flags=re.DOTALL)
    txt = re.sub(r'<usg\b[^>]*>(.*?)</usg>', r'\1', txt, flags=re.DOTALL)
    # Numbered sense levels — add labels
    txt = re.sub(r'<sense\b[^>]*\bn="(\d+)"[^>]*>', r'\n \1. ', txt)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = txt.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    txt = re.sub(r'[ \t]+', ' ', txt)
    txt = re.sub(r'\n{2,}', '\n', txt).strip()
    if len(txt) > max_len:
        txt = txt[:max_len] + f'\n... [truncated; full is {len(txt)} chars]'
    return txt

def _propnoun_key_variants(word, kind):
    """Given a user-typed word, produce candidate exact keys for the index."""
    w = word.strip()
    variants = []
    if kind == 'ml':
        # Middle Liddell — beta-code key like 'a)aptos', 'e(bdomos'
        beta = to_beta(w)
        variants = [beta, beta.rstrip('/=\\'), beta.rstrip('12345')]
        variants.append(beta.replace('sigma_', 's').replace('s ', ''))
        # Perseus convention: capital-with-diacritic writes diacritic BEFORE
        # the letter, not after. My to_beta produces '*e(' — also try '*(e'.
        # Fix: swap '*X<diacritic>' → '*<diacritic>x'
        alt = re.sub(r'\*([a-z])([/(=\\)|+]+)', r'*\2\1', beta)
        if alt != beta:
            variants.append(alt)
            variants.append(alt.rstrip('/=\\'))
    else:
        # Smith — kebab-case ASCII, suffix -geo/-bio/-cn
        lw = w.lower()
        lw = re.sub(r"[’'`\"]", '', lw)
        lw = re.sub(r'\s+', '-', lw)
        lw = re.sub(r'[^a-z0-9-]', '', lw)
        suffix = f'-{kind}'
        # 1) exact form as-typed (with suffix)
        variants.append(f'{lw}{suffix}')
        # 2) with '-1' variants for biography
        variants.append(f'{lw}{suffix}-1')
        # 3) common -us / -a / -is Latin ending swaps
        for stripped in [re.sub(r'us$', '', lw), re.sub(r'a$', '', lw),
                         re.sub(r'is$', '', lw), re.sub(r'es$', '', lw)]:
            if stripped != lw and stripped:
                variants.append(f'{stripped}{suffix}')
                variants.append(f'{stripped}us{suffix}')
                variants.append(f'{stripped}a{suffix}')
        # 4) canonical form (e.g. 'homer' → 'homerus')
        variants.append(f'{lw}us{suffix}')
        variants.append(f'{lw}us{suffix}-1')
    # Dedupe preserving order
    seen = set()
    out = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out

def _read_entry(kind, offset, length):
    with open(PROPNOUN_XML[kind], 'rb') as f:
        f.seek(offset)
        return f.read(length).decode('utf-8', errors='replace')

def _entries_for_key(kind, key):
    """Read all raw entries stored under `key` from the given corpus."""
    index = load_propnoun_index(kind)
    if key not in index:
        return []
    stored = index[key]
    # Stored may be [offset, length] or [[offset,length],...]
    if isinstance(stored[0], list):
        pairs = stored
    else:
        pairs = [stored]
    return [(key, _read_entry(kind, off, ln)) for off, ln in pairs]

def lookup_smith(kind, word, max_entries=8):
    """Look up a proper noun in Smith's Geography/Biography/Antiquities."""
    if kind not in ('geo', 'bio', 'cn'):
        return None
    index = load_propnoun_index(kind)
    if not index:
        return f"(Corpus '{kind}' not indexed — run 'build-propnoun {kind}' first.)"
    variants = _propnoun_key_variants(word, kind)
    seen_keys = set()
    hits = []
    # Strip trailing '-N' numbering from variants to get stem forms
    stems = set()
    for v in variants:
        stems.add(v)
        m = re.match(r'(.+)-\d+$', v)
        if m:
            stems.add(m.group(1))
    # Enumerate matching keys: exact stem match OR '<stem>-N' numbered variants
    for k in index.keys():
        for s in stems:
            if k == s or k.startswith(s + '-') and re.match(r'^' + re.escape(s) + r'-\d+$', k):
                if k not in seen_keys:
                    seen_keys.add(k)
                    for h in _entries_for_key(kind, k):
                        hits.append(h)
                break
    if not hits:
        return None
    label = PROPNOUN_LABEL[kind]
    out = [f'=== {label} ===',
           f'Query: "{word}" — {len(hits)} entry match(es)', '']
    for i, (key, raw) in enumerate(hits[:max_entries], 1):
        if len(hits) > 1:
            out.append(f'--- Entry {i}: {key} ---')
        out.append(_clean_smith_entry(raw))
        out.append('')
    if len(hits) > max_entries:
        out.append(f'... [{len(hits) - max_entries} more entries omitted]')
    return '\n'.join(out).strip()

def lookup_middle_liddell(word):
    """Look up a Greek word in the Middle Liddell (Liddell-Scott Intermediate)."""
    index = load_propnoun_index('ml')
    if not index:
        return "(Middle Liddell not indexed — run 'build-propnoun ml' first.)"
    variants = _propnoun_key_variants(word, 'ml')
    hits = []
    for v in variants:
        if v in index:
            for h in _entries_for_key('ml', v):
                hits.append(h)
            break
    if not hits:
        return None
    label = PROPNOUN_LABEL['ml']
    out = [f'=== {label} ===',
           f'Query: "{word}" — {len(hits)} sense(s)', '']
    for i, (key, raw) in enumerate(hits, 1):
        if len(hits) > 1:
            out.append(f'--- Sense {i} ---')
        out.append(_clean_middle_liddell_entry(raw))
    return '\n'.join(out).strip()

def search_smith_all(word, max_results=40):
    """Substring search across all three Smith dictionaries — key match + head match."""
    word_lc = word.lower().strip()
    word_beta = to_beta(word)  # for Greek forms
    hits = []
    for kind in ('geo', 'bio', 'cn'):
        index = load_propnoun_index(kind)
        if not index:
            continue
        # 1) Key substring hits (fast — no XML read)
        for k in index.keys():
            if word_lc in k.lower():
                hits.append((kind, k, 'key'))
                if len(hits) >= max_results * 3:
                    break
        # 2) If we still need more, scan file for word_lc in text (slow — do only if key hits are few)
    if not hits:
        # Fallback — search actual XML text for the substring
        for kind in ('geo', 'bio', 'cn'):
            xml_path = PROPNOUN_XML[kind]
            if not xml_path.exists():
                continue
            with open(xml_path, 'rb') as f:
                blob = f.read().decode('utf-8', errors='replace')
            index = load_propnoun_index(kind)
            for k, stored in index.items():
                # Read only the entry blob to check for word
                pairs = stored if isinstance(stored[0], list) else [stored]
                for off, ln in pairs:
                    snippet = blob[off:off+ln].lower()
                    if word_lc in snippet:
                        hits.append((kind, k, 'body'))
                        break
                if len(hits) >= max_results:
                    break
            if len(hits) >= max_results:
                break
    if not hits:
        return f"No Smith entries match '{word}'."
    out = [f"Smith-dictionaries search for '{word}' — {len(hits)} match(es)"
           + (f' (max, more may exist)' if len(hits) >= max_results else '') + ':', '']
    seen = set()
    for kind, key, source in hits[:max_results]:
        pair = (kind, key)
        if pair in seen:
            continue
        seen.add(pair)
        corpus = {'geo': 'GEO', 'bio': 'BIO', 'cn': 'ANT'}[kind]
        out.append(f"  [{corpus}] {key}   ({source} match)")
    out.append('')
    out.append("Look up a specific hit with: proper_noun_geo(word), proper_noun_bio(word), proper_noun_ant(word).")
    return '\n'.join(out)

# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'build-index':
        idx = build_index()
        print(f'Built LSJ index: {len(idx)} keys → {INDEX_FILE}')
    elif cmd == 'lsj':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py lsj <term>')
            sys.exit(1)
        term = sys.argv[2]
        key, entries = lookup_lsj(term)
        if not entries:
            print(f'No LSJ entry found for "{term}" (beta-code key tried: "{to_beta(term)}")')
            sys.exit(1)
        print(f'=== LSJ entry for "{term}" (key="{key}") ===')
        for i, entry in enumerate(entries, 1):
            if len(entries) > 1:
                print(f'\n--- Sense {i} of {len(entries)} ---')
            print(clean_xml(entry))
    elif cmd == 'verse':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py verse "<reference>"')
            sys.exit(1)
        ref = ' '.join(sys.argv[2:])
        result = lookup_verse(ref)
        if not result:
            print(f'No SBLGNT text found for "{ref}"')
            sys.exit(1)
        print(result)
    elif cmd == 'build-tagnt':
        verses, n_words = build_tagnt_index()
        print(f'Built TAGNT index: {len(verses)} verses, {n_words} words → {TAGNT_INDEX_FILE}')
    elif cmd == 'editions':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py editions "<reference>"')
            sys.exit(1)
        ref = ' '.join(sys.argv[2:])
        result = lookup_editions(ref)
        if not result:
            print(f'No TAGNT data found for "{ref}"')
            sys.exit(1)
        print(result)
    elif cmd == 'verse-byz':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py verse-byz "<reference>"')
            sys.exit(1)
        ref = ' '.join(sys.argv[2:])
        result = lookup_byzantine(ref)
        if not result:
            print(f'No TAGNT data found for "{ref}"')
            sys.exit(1)
        print(result)
    elif cmd == 'lxx':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py lxx "<reference>" [grc1|grc2]')
            sys.exit(1)
        # Accept an optional edition marker as the last argument
        if sys.argv[-1] in ('grc1', 'grc2'):
            edition = sys.argv[-1]
            ref = ' '.join(sys.argv[2:-1])
        else:
            edition = 'grc1'
            ref = ' '.join(sys.argv[2:])
        result = lookup_lxx_verse(ref, edition=edition)
        if not result:
            print(f'No LXX data found for "{ref}"')
            sys.exit(1)
        print(result)
    elif cmd == 'lxx-editions':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py lxx-editions "<reference>"')
            sys.exit(1)
        ref = ' '.join(sys.argv[2:])
        result = lookup_lxx_editions(ref)
        if not result:
            print(f'No LXX data found for "{ref}"')
            sys.exit(1)
        print(result)
    elif cmd == 'lxx-search':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py lxx-search "<word>" [max_results] [book_filter]')
            sys.exit(1)
        word = sys.argv[2]
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 50
        book_filter = sys.argv[4] if len(sys.argv) > 4 else None
        result = search_lxx(word, max_results=max_results, book_filter=book_filter)
        print(result)
    elif cmd == 'lxx-books':
        print(list_lxx_books())
    elif cmd == 'build-propnoun':
        target = sys.argv[2] if len(sys.argv) > 2 else 'all'
        kinds = ['geo', 'bio', 'cn', 'ml'] if target == 'all' else [target]
        for k in kinds:
            if k not in PROPNOUN_XML:
                print(f'Unknown kind "{k}" — use geo|bio|cn|ml|all')
                continue
            if not PROPNOUN_XML[k].exists():
                print(f'{k}: XML missing at {PROPNOUN_XML[k]} — skipped')
                continue
            idx = build_propnoun_index(k)
            print(f'{k}: {len(idx)} entries indexed → {PROPNOUN_INDEX_FILE[k].name}')
    elif cmd == 'smith-geo':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py smith-geo "<name>"')
            sys.exit(1)
        name = ' '.join(sys.argv[2:])
        result = lookup_smith('geo', name)
        if not result:
            print(f'No Smith Geography entry found for "{name}"')
            sys.exit(1)
        print(result)
    elif cmd == 'smith-bio':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py smith-bio "<name>"')
            sys.exit(1)
        name = ' '.join(sys.argv[2:])
        result = lookup_smith('bio', name)
        if not result:
            print(f'No Smith Biography entry found for "{name}"')
            sys.exit(1)
        print(result)
    elif cmd == 'smith-ant':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py smith-ant "<term>"')
            sys.exit(1)
        term = ' '.join(sys.argv[2:])
        result = lookup_smith('cn', term)
        if not result:
            print(f'No Smith Antiquities entry found for "{term}"')
            sys.exit(1)
        print(result)
    elif cmd == 'smith-search':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py smith-search "<name>"')
            sys.exit(1)
        # Optional max_results as last numeric arg
        args = sys.argv[2:]
        if len(args) > 1 and args[-1].isdigit():
            max_r = int(args[-1])
            name = ' '.join(args[:-1])
        else:
            max_r = 40
            name = ' '.join(args)
        print(search_smith_all(name, max_results=max_r))
    elif cmd == 'middle-liddell':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py middle-liddell <word>')
            sys.exit(1)
        word = sys.argv[2]
        result = lookup_middle_liddell(word)
        if not result:
            print(f'No Middle Liddell entry for "{word}" (beta-code tried: "{to_beta(word)}")')
            sys.exit(1)
        print(result)
    elif cmd == 'build-corpus':
        only = sys.argv[2] if len(sys.argv) > 2 else None
        build_corpus_index(only_author=only)
    elif cmd == 'corpus-search':
        if len(sys.argv) < 3:
            print('Usage: greek_lookup.py corpus-search <greek> [--author slug] [--max N]')
            sys.exit(1)
        word = sys.argv[2]
        author = None
        maxr = 25
        args_rest = sys.argv[3:]
        for i, a in enumerate(args_rest):
            if a == '--author' and i + 1 < len(args_rest):
                author = args_rest[i + 1]
            if a == '--max' and i + 1 < len(args_rest):
                maxr = int(args_rest[i + 1])
        result = search_corpus(word, author=author, max_results=maxr)
        print(result)
    elif cmd == 'corpus-authors':
        print(list_corpus_authors())
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == '__main__':
    main()
