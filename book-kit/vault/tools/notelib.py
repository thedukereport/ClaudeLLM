#!/usr/bin/env python3
"""notelib.py — two small helpers the footnote checks share: the block-id pattern and the work-title finder.

    import notelib
    notelib.BID.sub("", text)    text with every <!-- b:xxxxxx --> block id removed
    notelib.sources(text)        {italic work titles in text}

WHY THIS FILE EXISTS
    In the system this kit comes from, these two lived in larger modules that
    served the retired proposal sheets. check-note-content.py and
    assess-notes.py used only these two, so only these two were kept.
"""
import re

# THE BLOCK-ID COMMENT. tools/blockid.py writes `<!-- b:xxxxxx -->` into each
# block as its durable address. It renders to nothing and is not prose, so the
# note checks take it out before they read or count a note.
BID = re.compile(r"<!--\s*b:[a-z0-9]{6}\s*-->")


def sources(s):
    """The italicised work titles in a passage, as a set.

    A TITLE IS FOUND BY SPLITTING ON THE MARKER, NOT BY PAIRING WITH A REGEX.
    A pattern like `\\*([^*\\n]{6,}?)\\*` skips a span shorter than its minimum
    and resumes mid-string, so it pairs the CLOSING asterisk of one italic with
    the OPENING asterisk of the next, and returns the prose between two short
    italic words as a "title". Splitting cannot mis-pair: in well-formed
    markdown every odd-numbered piece is inside a span. Bold markers (`**`) are
    taken out of the running first, because a naive search reads straight
    across bold.

    What is NOT a title, each found the hard way in the original system:
      * a single italic word: a foreign term, not a work;
      * an italic span ending in a colon: emphasis addressed to the reader;
      * a long italic span, or one holding quotation marks or a second
        sentence: an italicised block quotation;
      * bold italic: emphasis;
      * an all-lowercase span: an ordinary phrase italicised for emphasis.
        A title has a capital letter in it.
    """
    s = (s or "").replace("**", "\x00")
    pieces = s.split("*")
    out = set()
    for i in range(1, len(pieces), 2):
        x = pieces[i]
        if len(x) < 6 or " " not in x.strip() or x.rstrip().endswith(":"):
            continue
        if len(x) > 120 or '"' in x or "“" in x or ". " in x:
            continue
        if x.startswith("\x00") or x.endswith("\x00"):
            continue
        if not any(c.isupper() for c in x):
            continue
        out.add(x)
    return out
