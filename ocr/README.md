# `ocr/` — give a scanned book a text layer without touching the scan

A page-image PDF holds pictures of pages and no words. The extractor reads it,
finds nothing, and the book sits in your library returning nothing forever. These
scripts read the pictures and write the words underneath them.

They exist in this shape because the obvious tool broke things. `ocrmypdf
--force-ocr` re-encodes every page, and pointed at files that already held text
it grew one book from 4.2 MB to 1.24 GB and wrote a second copy of the words into
73 others. Nothing here can do that:

- every run writes a **new** ` - OCR.pdf` and never opens the original for writing;
- the runner **refuses** any source that already yields text;
- **no page is re-encoded.** Tesseract reads a rendered image, and the words it
  recognises go back onto the original page object as invisible text (render mode
  3). The page still rasterises to identical pixels, so the added bytes are words,
  not a second copy of the scan.

## The scripts

| File | What it does |
|---|---|
| `detect_lang.py` | Reads one page of each book and scores it against stopword sets, so each book gets the right `-l` setting. Writes `ocr_languages.tsv`. |
| `run_ocr_copies.sh` | The wrapper. Checks the tools exist, prints a kill card, and calls the runner in 15-minute budgets until the work list drains — or until a full pass finishes no book, which means the remainder fail the same way every time. |
| `ocr_to_copy.py` | The runner. Renders each page at 300 dpi, OCRs it, merges the text layer, writes the new file. Resumable to the page: a run cut off mid-book restarts at the next page. Each book runs inside its own `try/except`, so one bad book costs one book. |
| `ocr_trim_borders.py` | For scans that sit inside a white or dark frame. OCRs only the cropped page and then pushes every word box back by the crop offset, so the words land in the right place on the full page. |
| `alexandria_optimize.py` | The shared library: text-layer construction, quarantine-first writes, the ledger. |

## Running it

```bash
export ALEX_PDF_ROOT=/path/to/your/PDF        # the folder holding your books
source /path/to/RAG_system/rag_env/bin/activate
python3 detect_lang.py                        # writes ocr_languages.tsv
cp ocr_languages.tsv ocr_worklist.txt         # edit to taste: one path + TAB + lang per line
./run_ocr_copies.sh
```

Needs `pdftoppm` and `pdfinfo` (poppler), `tesseract` with the language packs you
plan to use, and `pypdf`, `Pillow`, `reportlab`, `numpy` in the active Python.

Afterwards, fold the new text in with an incremental index run — from the
dashboard's **Update Index** button, or by asking Claude to call the RAG server's
`update_index` tool.

## When a book comes out nearly empty

Measure words per page before you trust a run. A. E. Waite's *Lives of
Alchemystical Philosophers* (1888) came out of a 42-book run at 25 words a page,
and 279 of its 315 pages held no text at all, while every other book in the run
measured between 132 and 863. Its pages render as a gray scan inside a pure-white
frame, and tesseract reads the whole image as one picture and returns nothing —
no error, no warning, just an empty page. Cropping the frame away gave the same
page 310 words, and the book 95,699 in place of 7,934.

`ocr_trim_borders.py` is the fix. It fills the work directory with corrected
hOCR, and then `ocr_to_copy.py` merges it exactly as it would its own.

## One file you cannot OCR at 300 dpi

A single tall image — an infographic, a scanned scroll — can render past what
Pillow will open. A 5,120 × 22,888 page at 300 dpi comes to 2.03 billion pixels,
and Pillow refuses anything over 0.18 billion. Hold those out of the work list,
or render them lower and raise `Image.MAX_IMAGE_PIXELS` deliberately.
