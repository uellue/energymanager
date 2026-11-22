# Kaizen ledger

What leaves a debrief: proposals with decisions, the fate of earlier ones, what did not fit in the plugin's skills, and notes for the next debrief. The full reports are private, in `.claude/debriefs/`.

Public: may become (private for now), asked 2026-11-21.
Message size: comfortable, a bit long ("Was about right. A bit on the long side perhaps."), asked 2026-11-21.

## Proposals
### 2026-11-21 (first debrief: setup, requirements, walk-through S1)
| # | Proposal | Destination | Effort | Decision / status |
|---|---|---|---|---|
| 1 | At session start, if the start directory is not the project's repo but one lies below it, say which directory to start in and why (instructions, memory, transcripts load from there); the first rollout in a new repo ends with "start the next session in <repo>" | kaizen plugin (SessionStart hook, update skill) | medium | sent upstream 2026-11-21 (uellue/skills#17) |
| 2 | Order questions by uncertainty and cost (lean startup): ask only what blocks the next step, mark the rest "learn from the pilot" with the step that answers it, and ask once which level of detail the stage needs | kaizen plugin (requirements, walkthrough) | medium | sent upstream 2026-11-21 (uellue/skills#17) |
| 3 | Add `design/research/` to the `context:` block of `openspec/config.yaml`; the plugin's template names it too | project; kaizen plugin template | small | project part done 2026-11-21 (accepted); plugin part in uellue/skills#17 |
| 4 | Pre-commit check against private data (private IPs, coordinates, serial-number patterns, tokens) before the first code that handles credentials; a small regex script avoids a new dependency | project hook | small | open |
| 5 | Evaluate whether Matt Pocock's `research` skill would have served the four research briefs better: rerun one brief through it and compare | backlog | small | done 2026-11-21: one rerun (Daikin power readout, Opus) with only the skill's text and the question, a 120-word brief against 399 words. Same key conclusions, deeper on Daikin's own sources (page numbers, "energy is an estimate", Modbus write risk), unverified points marked without being told; 93 k tokens, 4.7 min against 99 k, 5.9 min; 1,778 words against a 600-word limit. Missed: release dates, the issue with the 25 % error, DCOM. Lean: use `research` for fact-finding and add three lines (mark unverified, never invent citations, folder `design/research/` and a length). One run only |
| 6 | Install Python packaging (`python3-venv` and pip, or `uv`, a new tool) before the first code | environment | small | accepted 2026-11-21; already in place (`python3-venv` and pip 25.1.1 installed, a venv test passed) |
| 7 | Memory: `grep` here is a ugrep wrapper that rejects bounded repeats over fetched HTML; use `python3 -I` with `re` | agent memory | small | done 2026-11-21 (accepted); saved in the home folder's memory, so it applies to sessions started there (see row 1) |
| 8 | Ship a script that lists open markers and empty sections of `requirements.md` for the hand-over check (written by hand twice) | kaizen plugin (requirements) | small | sent upstream 2026-11-21 (uellue/skills#17) |
| 9 | Before asking a setup question, check whether the machine already answers it (config files, environment) | kaizen plugin (standing instructions) | small | sent upstream 2026-11-21 (uellue/skills#17) |

## Skill friction
- 2026-11-21, update (first rollout): the step "work on a branch" assumes existing commits; in an empty repository the setup became the first commit on `main`. The rollout offers `AGENTS.md` without saying that Claude Code only reads `CLAUDE.md`, so an import is needed.
- 2026-11-21, requirements: the principal answered in solution terms several times (loss functions, generic ODE core) and deferred many details "to practice". The frontier rounds worked, but the hand-over list grew long; a "deferred to practice" marker separate from [unknown] would fit this project better.
- 2026-11-21, walkthrough: the persona is real and present, so the walk turned into a second requirements round; most questions concerned the platform (Home Assistant, Docker, the vendor's ports) rather than the persona's experience, and a quick check against the docs answered more than imagining did.
- 2026-11-21, debrief: started from the home directory, so `transcript.py locate` found no checkout and the repo had to be inferred from the first message; three small sessions (13–200 kB rendered) did not need reader agents and were read directly.

## Notes for the next debrief
- 2026-11-21: first rollout of kaizen 0.6.1-dev.2; no issue tracker yet, so no first look at issues (the first `/kaizen:sync` starts from here once a tracker exists).
