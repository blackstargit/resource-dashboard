# Rules

General rules that hold on any project. Imported by `CLAUDE.md`, so they are
always loaded. Project-specific rules and facts live in `CLAUDE.md` and the
files it indexes, never here.

---

## Working with the user

### Prompts are dictated (speech-to-text)

Every prompt is written with speech-to-text. Two kinds of error are common:

1. **Autocorrect substitutions** — a technical term silently replaced by a real
   but wrong word ("ollama" → "lama", "useState" → "use date", "degradation" →
   "depreciation"). It reads as valid English but makes no sense in context.
2. **Transcription errors** — a word garbled into a non-word.

- Read the entire prompt in context before interpreting any single word.
- If a word doesn't fit — technically, semantically, or relative to the
  conversation — assume a dictation error and infer the intended term from
  domain knowledge and the surrounding text.
- Never act on a nonsensical word literally.
- Ask for clarification only if intent is still genuinely ambiguous after
  reasonable inference.

### Explain before acting

Before any non-trivial change (editing config or code, creating files, running
a command with side effects), write 2–4 sentences: what the problem is, why
the proposed change addresses it, and what the change will actually do. Then
make the change. Not after, and never silently — the user wants to be able to
redirect or question the approach before anything happens.

### Settled decisions stay settled

When a decision is recorded as made ("decided", "by decision", "don't
re-propose"), don't reopen it without new evidence — re-arguing wastes the
user's time. When presenting a trade-off, give concrete numbers and absolute
wall-clock times, not just percentages.

---

## Hard limits

- **Never run `sudo`.** Write the command out and give it to the user to run.
  No exceptions.
- **Never build, deploy, restart services, commit or push on your own** —
  only when the user asks for that exact action in that turn. Finish the code
  and tests, then hand over the exact commands (and a commit message).
  Approving a plan that mentions committing is not a request to commit.
- **Never read secret or credential files** (generated keys, credential
  stores). If a task seems to need one, ask.

---

## Before writing code

- **Check the code before claiming what it has or lacks.** Grep for an
  existing mechanism before proposing one, and build on it rather than
  replacing it.
- **Deep dependency checks.** Before modifying or replacing a core piece of
  data (a store slice, a shared type, a DB column, a file format), grep for
  every consumer. Never infer what consumers need from the name alone.
- **State dependency walkthrough.** Before touching application state, auth
  flows or data loading, trace the chronological lifecycle explicitly (e.g.
  app boot → rehydrate → user enters credentials → login success → trigger X)
  to catch temporal bugs.

## While writing code

- **Incremental implementation.** Never write several files in a row without
  compiling. Change one unit → type-check/compile (`tsc`, `py_compile`, …) →
  next. Read the raw compiler output; a wrapper that summarises it can report
  "no errors" over real ones.
- **Static checks are not verification.** Linters and type-checkers have each
  missed real bugs; exercise the real behaviour before calling something done.
- **Delegate large, mechanical, low-judgment changes** (many files, one
  pattern repeated) to a background subagent with a tightly scoped,
  self-contained prompt instead of doing them inline.

---

## Keeping instructions

- **The repo is the memory.** Auto-memory is disabled per project; durable
  lessons (preferences, decisions, gotchas) are written into the repo file
  that owns the topic, never into `~/.claude`, which no other machine sees.
- **One fact, one place.** Don't duplicate a fact across files; link to where
  it lives. General rules go here, project rules in `CLAUDE.md`.
