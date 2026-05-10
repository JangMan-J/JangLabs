#!/usr/bin/env bash
# UserPromptSubmit hook. Surfacing-only (no blocking).
# Scans the user's prompt for distinctive substrings from each MEMORY.md
# entry's description; for each matched entry, inlines the memory body
# into the per-turn context as a <relevant-memory> block.
#
# Cost discipline: one grep per indexed entry. Caps body output at 2KB per
# memory and 8KB total to avoid drowning context on a heavy match.
set -u

INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
CWD=$(printf '%s'   "$INPUT" | jq -r '.cwd // empty'    2>/dev/null || true)
[ -n "$PROMPT" ] && [ -n "$CWD" ] || exit 0

# Map cwd to memory dir. Encoding: drop leading slash, replace / with -, prepend -.
PROJ_TAG=$(printf '%s' "$CWD" | sed 's|^/||;s|/|-|g')
MEM_DIR=$HOME/.claude/projects/-$PROJ_TAG/memory
MEM_INDEX=$MEM_DIR/MEMORY.md
[ -f "$MEM_INDEX" ] || exit 0

PROMPT_LC=$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Stopwords + memory-meta words that would over-match.
STOP=" the and for that this with from some most all are was were been being has have had will would should could can may might must shall over into onto also more many much such only just like user file claude memory session conversation entry topic note rule about while before after each other their there where when what which whose whom into between"

# Output budget
MAX_PER_MEMORY=2048
MAX_TOTAL=8192
emitted=0

# Iterate index entries: lines beginning with "- [" (one entry per line).
while IFS= read -r line; do
  case "$line" in '- ['*) ;; *) continue ;; esac

  # Split at LAST " — " (em-dash with surrounding spaces). Titles can contain
  # their own em-dashes (e.g. "[Fumble] paru — actually pacman"), so the
  # description is everything after the *final* em-dash separator.
  title_paren="${line% — *}"
  desc="${line##* — }"
  [ "$title_paren" = "$line" ] && continue   # no em-dash → not a parseable entry

  # Extract filename inside (...)
  fname=$(printf '%s' "$title_paren" | sed -n 's/.*(\([^)]*\)).*/\1/p')
  [ -n "$fname" ] || continue

  body_path=$MEM_DIR/$fname
  [ -f "$body_path" ] || continue

  # Extract two distinctive-term pools from the title + description:
  #   (1) lowercase words length >= 4, with stopword filter, substring match
  #   (2) original-case acronyms (>=2 uppercase letters in source), word-boundary match
  # The acronym pass catches domain codes like VDF, JSM, ACP, RDP, HID, SDL that
  # are too short for the general pool but highly distinctive.
  cand_orig="$title_paren $desc"
  words_lc=$(printf '%s' "$cand_orig" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' ' ')
  acronyms_lc=$(printf '%s' "$cand_orig" | grep -oE '[A-Z]{2,}' | tr '[:upper:]' '[:lower:]')

  matched=""
  for w in $words_lc; do
    [ ${#w} -ge 4 ] || continue
    case " $STOP " in *" $w "*) continue ;; esac
    if printf '%s' "$PROMPT_LC" | grep -qF -- "$w"; then matched=$w; break; fi
  done
  if [ -z "$matched" ]; then
    for w in $acronyms_lc; do
      [ ${#w} -ge 2 ] || continue
      if printf '%s' "$PROMPT_LC" | grep -qwF -- "$w"; then matched=$w; break; fi
    done
  fi
  [ -n "$matched" ] || continue

  # Within budget?
  [ "$emitted" -ge "$MAX_TOTAL" ] && break

  # Emit the body, capped per-memory.
  body=$(head -c "$MAX_PER_MEMORY" "$body_path")
  block=$(printf '<relevant-memory file="%s" matched-on="%s">\n%s\n</relevant-memory>\n' "$fname" "$matched" "$body")
  printf '%s' "$block"
  emitted=$(( emitted + ${#block} ))
done < "$MEM_INDEX"

exit 0
