#!/bin/bash
# OCR the image-only scans named in ocr_worklist.txt into new " - OCR.pdf"
# copies beside them. Every original is left exactly as it was.
#
#   ALEX_PDF_ROOT=/path/to/your/PDF ./run_ocr_copies.sh
#
# ALEX_PDF_ROOT is the folder holding your PDFs. It defaults to the parent of
# this script, which is right when the script sits in a subfolder of the library.
#
# Originals are never opened for writing. To undo the whole job:
#   find "$ALEX_PDF_ROOT" -name '* - OCR.pdf' -newermt '2026-09-15' -delete
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1

ROOT="${ALEX_PDF_ROOT:-$(dirname "$HERE")}"
export ALEX_ROOT="$ROOT"
export ALEX_OUT="$HERE"
export ALEX_QUARANTINE="$HERE/.quarantine_unused"
export ALEX_WORKERS="${ALEX_WORKERS:-4}"          # doc 07 rule 5: workers stay at 4
export TESSDATA_PREFIX="$HERE/.tessdata"
# Homebrew goes AFTER the existing PATH, never before it. `activate` puts the
# venv first, and prepending Homebrew shoves it aside — the venv's python3
# loses to /opt/homebrew/bin/python3, which has none of the packages. That
# mistake cost 135 failed books in July; the order is venv, then Homebrew.
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin"

echo "=============================================================="
echo " OCR image-only scans -> new ' - OCR.pdf' copies"
echo "=============================================================="
echo " books      : $(grep -vc '^\s*\(#\|$\)' ocr_worklist.txt)"
echo " library    : $ROOT"
echo " workers    : $ALEX_WORKERS"
echo " expect the copies to run about 1.7x the size of the originals."
echo " writes     : new files only. No original is opened for writing."
echo " no ocrmypdf, so --force-ocr cannot run."
echo
echo " KILL CARD"
echo "   this script : PID $$"
echo "   stop it     : kill $$"
echo "   stop strays : pkill -9 -f ocr_to_copy.py"
echo "   confirm     : ps -ef | grep -c '[o]cr_to_copy.py'      # expect 0"
echo "=============================================================="
echo

for t in pdftoppm tesseract python3; do
  command -v "$t" >/dev/null || { echo "MISSING: $t — install it and re-run"; exit 1; }
  printf "  %-10s %s\n" "$t" "$(command -v $t)"
done
echo "  languages  $(tesseract --list-langs 2>&1 | tail -n +2 | tr '\n' ' ')"
echo
python3 -c "import pypdf, PIL, reportlab" 2>/dev/null || {
  echo "MISSING python packages — activate the venv first:"
  echo "  source <your RAG_system>/rag_env/bin/activate"; exit 1; }

# Resumable to the page: each finished page leaves an .hocr in .ocrcopy, so a
# stop here costs the page in flight, not the book.
START=$(date +%s)
PREV=-1
while :; do
  python3 ocr_to_copy.py --list ocr_worklist.txt --budget 900
  LEFT=$(ALEX_PDF_ROOT="$ROOT" python3 - <<'PY'
import os
mac=os.environ.get("ALEX_PDF_MAC_ROOT","/Volumes/PRO-BLADE/Alexandria/PDF")
root=os.environ.get("ALEX_PDF_ROOT",
                    os.path.dirname(os.path.dirname(os.path.abspath("ocr_worklist.txt"))))
n=0
for line in open("ocr_worklist.txt"):
    line=line.strip()
    if not line or line.startswith("#"): continue
    p=line.split("\t")[0].replace(mac, root)
    if not os.path.exists(p[:-4]+" - OCR.pdf"): n+=1
print(n)
PY
)
  echo "--- $LEFT book(s) still to do, $(( ($(date +%s)-START)/60 )) min elapsed"
  [ "$LEFT" -eq 0 ] && break
  # A pass that finishes no book will finish none on the next pass either.
  # Without this, one permanently failing book spun the loop for 512 minutes.
  if [ "$LEFT" -eq "$PREV" ]; then
    echo
    echo "STOPPING: a full pass finished no book. $LEFT left, and they fail the"
    echo "same way every time. Read the last lines of ocr_to_copy.log."
    break
  fi
  PREV="$LEFT"
done

echo
echo "Done in $(( ($(date +%s)-START)/60 )) minutes. New files:"
find "$ROOT" -name '* - OCR.pdf' -newer "$HERE/ocr_worklist.txt" | wc -l
echo
echo "Next: fold the new text into the index —"
echo "  cd <your RAG_system> && python3 index_books.py \\"
echo "      --input $ROOT --output $(dirname "$ROOT") --incremental"
