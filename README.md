# verify-backtrack

An open, scripted implementation of the **Verify–Backtrack Loop (VBL)**
control structure from arXiv 2610.41564 (*"Verify–Backtrack Loop: Structured
Precondition Recovery for Long-Horizon Language Agents"*, Liu et al., Oct
2026) — built from scratch, with **zero LLM calls, zero GPU, fully
deterministic** scripted agents on a simulated service world.

> **Scope — read this first.** This is a SCRIPTED ANALOG, not a reproduction
> of the paper. The paper evaluates LLM backbones (Qwen3.5-9B, GPT-4o,
> DeepSeek-V3.2) on AppWorld, ALFWorld, and ScienceWorld. This repo tests the
> paper's *control-structure claim* — that an explicit goal stack plus
> dual-horizon verification plus typed failure diagnosis recovers from
> latent-precondition and wrong-decomposition failures where free-text retry
> cannot — using deterministic scripted policies on a simulated service
> world. No paper number is claimed as reproduced. The live author-code
> recheck on 2 Nov 2026 found no author package (see PAPER.md §1).

## The idea in one paragraph

Long-horizon failure is usually a recovery problem, not a trajectory-length
problem. When a prerequisite is missing (a login token, a calendar
connection, a folder) or a decomposition is wrong (sending money when the
goal is to *request* money), trying another plausible action rarely helps.
ReAct-style recovery is free-form text with no explicit control state. VBL
instead maintains a **bounded goal stack** and, on goal activation, after
failure, or after a material state change, verifies two horizons — does the
active goal contribute to the terminal goal, and is it feasible now? — then
routes typed failures to explicit operations: **Push** (insert a missing
prerequisite), **Pop** (remove a completed/failed goal), **retry**, or
**BacktrackTo** the parent (discard an invalid decomposition and re-plan).

## What is in here

- `vbl/world.py` — simulated service world (auth, contacts, payments,
  calendar, files, meetings) with typed errors as the only failure signal.
- `vbl/tasks.py` — 180 generated tasks (seed 20261102) in three families:
  latent precondition (A), wrong decomposition / goal inversion (B), clean
  control (C). The planner receives only task text + template + params —
  preconditions live in the environment and are never shown to the planner
  (latency is enforced by construction and unit-tested).
- `vbl/planner.py` — fixed scripted decomposition table (the LLM-planner
  stand-in; `_inv` entries encode its mis-decompositions).
- `vbl/verifier.py` — dual-horizon verification + typed diagnosis
  (controller-side components, never visible to the planner).
- `vbl/arms.py` — four arms on identical task streams: `retry` (free-text
  retry baseline), `veronly`, `diagonly`, `vbl` (full loop).
- `vbl/run.py` — headline runner: Wilson CIs, paired bootstrap CIs
  (10,000 resamples), determinism digest.
- `tests/` — 20 unit tests, including the planner/environment separation
  tests that enforce precondition latency.
- `PREREG.md` — bars locked BEFORE any headline number (any failure = KILL).

## Results (measured, seed 20261102, n=180 tasks)

| arm | success | A (latent) | B (wrong decomp) | C (clean) |
|---|---|---|---|---|
| retry (ReAct-style) | 60/180 = 33.3% | 0/60 | 0/60 | 60/60 |
| verification-only | 60/180 = 33.3% | 0/60 | 0/60 | 60/60 |
| diagnosis-only | 120/180 = 66.7% | 60/60 | 0/60 | 60/60 |
| **full VBL** | **180/180 = 100%** | 60/60 | 60/60 | 60/60 |

- vbl − retry = **+66.7pp**, paired-bootstrap 95% CI [59.4, 73.3]pp.
- vbl − verification-only = **+66.7pp**, 95% CI [59.4, 73.3]pp.
- vbl − diagnosis-only = **+33.3pp**, 95% CI [26.7, 40.6]pp.
- Retry-arm recovery on latent-precondition tasks: **0%** (Wilson 95% CI
  [0, 6.0%]) vs VBL 100% — free-text retry never recovers, exactly the
  paper's disease structure, in analog form.
- Determinism: seed rerun byte-identical
  (`sha256 dc5e1b64907c84631c5996ad51898e2285ae29c592527c570dafb0e7e72789d6`).

## Run it

```bash
python3 -m unittest discover -s tests -v   # 20/20 green
python3 -m vbl.run results.json            # headline run (~5 s, CPU only)
```

## Differentiation from `soei`

`soei` (#109) is a post-hoc hash-chained evidence *ledger* that audits
already-made completion claims. This is a live *control* loop whose stack
transitions change what the agent does next, mid-episode. Ledger = proof
after the fact; goal stack = recovery during the episode.

## License

MIT. The paper's authors are not affiliated with this implementation.
