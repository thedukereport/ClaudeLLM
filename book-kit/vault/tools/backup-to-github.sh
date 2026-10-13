#!/bin/bash
#
# backup-to-github.sh — push the chapters and the working files to the author's own GitHub repository.
#
#   tools/backup-to-github.sh              # stage, show what changed, ask, push
#   tools/backup-to-github.sh -m "message" # same, with your own commit message
#   tools/backup-to-github.sh --dry-run    # show what WOULD be sent; no commit, no push
#   tools/backup-to-github.sh --print-gitignore   # print the default .gitignore
#
# WHERE IT PUSHES
#   To the remote named `origin` in the vault's own git settings
#   (`git remote get-url origin`). No repository name is written in this
#   script. Set it once:
#
#     1. Create an EMPTY, PRIVATE repository on GitHub. The ledgers and the
#        working notes are notes on an unpublished manuscript; keep it private.
#     2. git -C "<your vault>" init
#        git -C "<your vault>" remote add origin https://github.com/<you>/<repo>.git
#     3. Run this script.
#
# WHAT GETS PUSHED
#   The manuscript (Chapters/, Appendices/) and the apparatus that reads and
#   checks it: Fact Check/ (ledgers, Claims, the event log), Methodology/,
#   Handoffs/, Skills/, tools/, tests/, book.toml, and the .md state files at
#   the top of the vault. All of it is text that diffs readably.
#
#   In the system this kit comes from, only the two manuscript folders went up
#   at first. Losing the vault would have left the chapters and destroyed
#   every record of what had been verified, what was locked and what was still
#   open, along with the scripts and the bug fixes recorded in their comments.
#
#   The author's scope for the repository: nothing goes on GitHub that is not
#   essential. Never PDFs, images, audio, the library, caches, `_to_delete/`,
#   or `.bak` files. Git keeps each version of a binary whole, so those belong
#   in a snapshot (tools/snapshot-vault.sh), never in version history.
#
# THE .gitignore IS AN ALLOWLIST
#   It ignores everything at the top of the vault, then re-admits by FOLDER and
#   PATTERN, never by file name: a list of names must be edited for each new
#   file, and forgetting is invisible. Anything new you add at the top is out
#   by default. This script writes the default only when there is no
#   .gitignore at all: a file the author may edit is not the tool's to
#   overwrite. (The original rewrote it on every run, and three times deleted
#   a repair someone had just committed.)
#
# THE GUARDS (each one stops the commit and unstages everything)
#   1. Nothing outside the allowlist. Git itself says what is ignored, so there
#      is one list, never a second copy of it that drifts.
#   2. No binaries or data files, whatever the .gitignore says.
#   3. Out loud, without stopping: every text file the .gitignore is leaving
#      out, grouped by folder. Silence is the failure mode: twice in the
#      original system a whole folder of scripts was never backed up and a
#      person found it by accident.
#
# AUTHENTICATION
#   This script never handles credentials. git uses whatever you already have:
#   an SSH key, a credential helper, or the gh CLI. With none, the push prompts
#   or fails, and nothing local is harmed.

set -u
set -o pipefail

BRANCH="main"
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_gitignore() {
cat <<'EOF'
# Allowlist: ignore everything at the top of the vault, then re-admit only what
# the backup holds. Written by tools/backup-to-github.sh when no .gitignore
# exists; yours to edit after that. Re-admit FOLDERS and PATTERNS, never file
# names, so the next new file is in by default.
/*
!/.gitignore
!/book.toml
!/book.toml.example
!/*.md
!/Chapters/
!/Appendices/
!/Fact Check/
!/Methodology/
!/Handoffs/
!/Skills/
!/tools/
!/tests/

# Never in the repository, wherever they appear. Git keeps each version of a
# binary whole, so the repository would grow and never shrink; these belong in
# a snapshot (tools/snapshot-vault.sh).
*.pdf
*.epub
*.mobi
*.azw3
*.docx
*.png
*.jpg
*.jpeg
*.gif
*.webp
*.heic
*.mp3
*.m4a
*.wav
*.mp4
*.mov
*.zip
*.gz
*.tar
*.db
*.sqlite
*.sqlite3

# Local safety copies and scratch. Version history does their job.
*.bak
*.bak-*
_*
_to_delete/
__pycache__/
*.pyc
*.log
.ellipsis-cache/
.preflight/

# Operating-system and filesystem cruft. Do NOT add a global "*" rule here: a
# catch-all plus "!*/" re-admits directories at every level and git then
# descends into the whole vault (in the original system: 1,140 entries staged
# instead of 46).
.DS_Store
._*
.fuse_hidden*
Icon?
.obsidian/workspace*
EOF
}

DRY_RUN=0
COMMIT_MSG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run|-n) DRY_RUN=1; shift ;;
        -m|--message)  COMMIT_MSG="${2:-}"; shift 2 ;;
        --print-gitignore) print_gitignore; exit 0 ;;
        -h|--help)     sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# The vault and its chapter folder come from bookconfig, never from this file.
CONF="$(python3 - "$TOOLS" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import bookconfig as B
print(B.VAULT)
print(B.CHAPTERS)
print("\n".join(str(r) for r in B.LIBRARY_ROOTS))
PY
)" || { echo "ERROR: could not read the settings (book.toml)."; exit 1; }
VAULT="$(printf '%s\n' "$CONF" | sed -n 1p)"
CHAPTERS="$(printf '%s\n' "$CONF" | sed -n 2p)"
LIBS="$(printf '%s\n' "$CONF" | sed -n '3,$p')"

cd "$VAULT" || { echo "ERROR: cannot enter vault at $VAULT"; exit 1; }
[ -d "$CHAPTERS" ] || { echo "ERROR: $CHAPTERS not found. Is $VAULT the vault?"; exit 1; }

# ------------------------------------------------------------------ the remote
if [ ! -d .git ]; then
    echo "The vault is not a git repository yet. To back it up:"
    echo "  1. Create an empty PRIVATE repository on GitHub."
    echo "  2. git -C \"$VAULT\" init -b $BRANCH"
    echo "     git -C \"$VAULT\" remote add origin https://github.com/<you>/<repo>.git"
    echo "  3. Run this script again."
    exit 1
fi
if ! REMOTE_URL="$(git remote get-url origin 2>/dev/null)"; then
    echo "This vault's git repository has no remote called 'origin'. Add yours:"
    echo "  git -C \"$VAULT\" remote add origin https://github.com/<you>/<repo>.git"
    exit 1
fi
BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "$BRANCH")"

echo "Vault:  $VAULT"
echo "Remote: $REMOTE_URL  (branch $BRANCH)"
echo

if [ ! -f .gitignore ]; then
    echo "No .gitignore — writing the default allowlist."
    print_gitignore > .gitignore
fi

if ! git config user.email >/dev/null 2>&1; then
    echo "NOTE: no git identity set. If the commit fails, run:"
    echo "  git config --global user.name  \"Your Name\""
    echo "  git config --global user.email \"you@example.com\""
    echo
fi

# --------------------------------------------------------------------- stage
git add -A || { echo "git add failed. Nothing committed."; exit 1; }

STAGED_LIST="$(git -c core.quotepath=false diff --cached --name-only)" || { git reset -q; exit 1; }
STAGED=$(printf '%s' "$STAGED_LIST" | grep -c . || true)

# Guard 1: nothing outside the allowlist.
#
# This guard once kept its own copy of the allowlist as a regex, and the copy
# drifted from .gitignore twice: both times a correct backup stopped dead on
# files .gitignore admitted. So it keeps no list. It asks git.
#
# And for four days it passed everything: plain `git check-ignore` answers
# "not ignored" for any path already in the index, and every path asked about
# had just been staged. `--no-index` asks the .gitignore itself. It asks only
# about ADDED and RENAMED paths: `git add -A` never adds an untracked ignored
# file, but a rename into an ignored folder, or `git add -f`, does. A file
# tracked before the allowlist tightened is already in the repository, and an
# edit to it is not a stray.
STRAY=""
while IFS= read -r f; do
    [ -z "$f" ] && continue
    if git check-ignore -q --no-index -- "$f" 2>/dev/null; then
        STRAY="${STRAY}${f}
"
    fi
done <<EOF
$(git -c core.quotepath=false diff --cached --name-only --diff-filter=AR)
EOF
STRAY=$(printf '%s' "$STRAY")
if [ -n "$STRAY" ]; then
    echo "STOPPING — files outside the allowlist are staged:"
    echo "$STRAY" | sed 's/^/  /'
    echo
    echo "The .gitignore allowlist excludes these. Nothing has been committed."
    git reset -q
    exit 1
fi

# Guard 2: binaries and data files. Everything admitted is text. One of these
# reaching the index means a rule was loosened by mistake, and git keeps every
# version of a binary whole.
BIN=$(printf '%s\n' "$STAGED_LIST" \
    | grep -iE '\.(pdf|epub|mobi|azw3|docx?|xlsx?|pptx?|png|jpe?g|gif|webp|heic|tiff?|mp3|m4a|wav|mp4|mov|zip|gz|tar|7z|db|sqlite3?|pkl|npy|bin)$' || true)
if [ -n "$BIN" ]; then
    echo "STOPPING — binary or data files are staged:"
    echo "$BIN" | sed 's/^/  /'
    echo
    echo "Keep these in a snapshot (tools/snapshot-vault.sh), not in git. Nothing has been committed."
    git reset -q
    exit 1
fi

# Guard 3: say out loud what is being LEFT BEHIND. Grouped by folder, because
# the first version listed every file, and a warning that long is a warning
# nobody reads. The library, backups and recovery folders are meant to be out.
LEFT=$(git -c core.quotepath=false ls-files --others --ignored --exclude-standard \
    | grep -E '\.(md|sh|py|jsonl|json|tsv|toml|skill)$' \
    | grep -vE '(^|/)_recovery/|(^|/)_Backups|(^|/)_to_delete/|\.bak|^\.obsidian/|(^|/)_[^/]*$|(^|/)__pycache__/' || true)
if [ -n "$LIBS" ] && [ -n "$LEFT" ]; then
    while IFS= read -r lib; do
        [ -z "$lib" ] && continue
        rel="${lib#"$VAULT"/}"
        [ "$rel" = "$lib" ] && continue          # the library is outside the vault
        LEFT=$(printf '%s\n' "$LEFT" | grep -v "^$rel/" || true)
    done <<EOF
$LIBS
EOF
fi
if [ -n "$LEFT" ]; then
    LEFTN=$(printf '%s\n' "$LEFT" | wc -l | tr -d ' ')
    echo "NOT BACKED UP — $LEFTN text file(s) ignored by .gitignore, by folder:"
    printf '%s\n' "$LEFT" \
        | awk -F/ '{ if (NF==1) print "(vault top)"; else print $1 }' \
        | sort | uniq -c | sort -rn \
        | awk '{ n=$1; $1=""; sub(/^ /,""); printf "  %5d  %s\n", n, $0 }'
    echo
    echo "  Example: $(printf '%s\n' "$LEFT" | head -1)"
    echo
    echo "If a folder above belongs in the repository, re-admit THE FOLDER in .gitignore,"
    echo "not a file name, so the next new file is in by default. Then re-run."
    echo "Continuing without them."
    echo
fi

if [ "$STAGED" -eq 0 ]; then
    # Nothing new to commit, but an earlier run may have committed and not
    # pushed (a declined prompt, a failed push). Check before saying "nothing
    # to do", or the script strands work it already committed.
    AHEAD=0
    if git rev-parse --verify -q "origin/$BRANCH" >/dev/null 2>&1; then
        AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)
    elif git rev-parse --verify -q HEAD >/dev/null 2>&1; then
        AHEAD=$(git rev-list --count HEAD 2>/dev/null || echo 0)   # never pushed
    fi
    if [ "${AHEAD:-0}" -gt 0 ]; then
        echo "No new changes to commit, but $AHEAD commit(s) have not been pushed."
        if [ "$DRY_RUN" -eq 1 ]; then echo "--dry-run: not pushed."; exit 0; fi
        printf "Push them now? [y/N] "
        read -r reply || reply=""
        case "$reply" in
            [yY]|[yY][eE][sS])
                if git push -u origin "$BRANCH"; then
                    echo; echo "Done. Backed up at $REMOTE_URL"; exit 0
                fi
                echo; echo "Push failed. The commit(s) are safe locally."; exit 1 ;;
            *)
                echo; echo "Not pushed. To send later:"
                echo "  git -C \"$VAULT\" push -u origin $BRANCH"; exit 0 ;;
        esac
    fi
    echo "No changes since the last backup, and nothing waiting to push."
    exit 0
fi

echo "Changes to be backed up — $STAGED file(s):"
git -c core.quotepath=false diff --cached --name-status | sed 's/^/  /'
echo

if [ "$DRY_RUN" -eq 1 ]; then
    echo "--dry-run: nothing committed, nothing pushed."
    git reset -q
    exit 0
fi

# -------------------------------------------------------------------- commit
[ -z "$COMMIT_MSG" ] && COMMIT_MSG="Backup $(date '+%Y-%m-%d %H:%M') — $STAGED file(s)"
git commit -q -m "$COMMIT_MSG" || { echo "Commit failed — see the message above."; exit 1; }
echo "Committed: $COMMIT_MSG"
echo

# ---------------------------------------------------------------------- push
echo "About to push to:"
echo "  $REMOTE_URL  (branch $BRANCH)"
printf "Push now? [y/N] "
read -r reply || reply=""
case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *)
        echo
        echo "Not pushed. The commit is saved locally. To send it later:"
        echo "  git -C \"$VAULT\" push -u origin $BRANCH"
        exit 0 ;;
esac

echo
if git push -u origin "$BRANCH"; then
    echo
    echo "Done. Backed up at $REMOTE_URL"
else
    echo
    echo "Push failed. The commit is safe locally; nothing was lost."
    echo "Common causes:"
    echo "  - no credentials configured (an SSH key, a token, or 'gh auth login')"
    echo "  - the repository does not exist yet: create it empty on GitHub, then re-run"
    echo "  - the remote has commits you do not: git -C \"$VAULT\" pull --rebase origin $BRANCH"
    exit 1
fi
