# Project #126 `verify-backtrack` — PREREGISTRATION (LOCKED before any headline number)

**Locked:** Mon 2 Nov 2026, ~11:35 PKT, BEFORE any experiment run and before any
headline number exists. Lock order (verifiable by mtime):
`PREREG.md` < implementation < tests < headline run (`results.json`).
No amendments after locking; no re-seed, re-tune, re-split, or bar-weakening
after a failure. Decision rule: **ANY locked bar fails → KILL.**

## Source paper (context only, NOT claimed as reproduced)

arXiv 2610.41564, "Verify–Backtrack Loop: Structured Precondition Recovery for
Long-Horizon Language Agents" (Liu, Kang, Kai, Zhong, Yuan, Li, Song; City
University of Hong Kong + Huawei Noah's Ark Lab; submitted 30 Oct 2026).
Paper figures (context only): VBL beats ReAct and reflection controls on every
backbone–benchmark pair; up to +22.07pp over ReAct on AppWorld; removing either
verification or diagnosis degrades performance, in several settings below ReAct.

## Scope statement (appears in every artefact)

SCRIPTED ANALOG ONLY. Zero LLM calls, zero GPU, CPU-only deterministic Python.
The agents are scripted policies, not language models; the environment is a
simulated service world, not AppWorld/ALFWorld/ScienceWorld. Nothing here
reproduces, validates, or transfers the paper's LLM-benchmark numbers. What is
tested is the *control-structure* claim: that explicit goal-stack state +
dual-horizon verification + typed diagnosis recovers from latent-precondition
and wrong-decomposition failures where free-text retry cannot.

## Differentiation from #109 `soei`

`soei` is an append-only hash-chained evidence LEDGER that verifies
already-made completion claims after the fact (audit of a flat event stream).
`verify-backtrack` is a live CONTROL loop: a bounded goal stack whose
verification/diagnosis transitions change what the agent does next, mid-episode.
Ledger = post-hoc proof; goal stack = in-episode recovery. Different mechanism,
different failure mode, different evidence.

## Environment: simulated service world

State: auth tokens, contacts directory, payment requests vs transactions,
calendar connections, folders/files, settings. Actions are deterministic
functions of state; failures carry typed error signals (e.g. HTTP-401-style
"login required"), mirroring the paper's "execution feedback is the only
failure signal". The terminal goal is a predicate over final state, evaluated
only by the environment — never handed to the agent.

## Task stream (seed 20261102, generated, fixed before the run)

180 tasks, 60 per family, identical stream for all four arms (paired design):

- **Family A — latent precondition.** Terminal goal text names a service action
  (e.g. "request $13 from Stacy on Venmo, note 'For yesterday's meal'") but
  does NOT name the prerequisite (login token, calendar connection, folder
  existence, setting enabled). The planner's initial decomposition omits the
  prerequisite by construction. The prerequisite is revealed ONLY by the
  failure observation (typed error) at execution time.
- **Family B — wrong decomposition (goal inversion).** The planner's initial
  decomposition contains a goal whose operator is effect-inverted relative to
  the terminal goal (e.g. `create_transaction` "send money" where the terminal
  goal is a payment REQUEST; the action succeeds environmentally and mutates
  state, but the terminal predicate is never satisfied). No failure signal
  fires; only an alignment check can catch it.
- **Family C — clean control.** Correct decomposition, no latent prerequisite.
  All arms are expected to succeed; guards against arms that break easy tasks.

## Latency guarantee (G2 binding condition)

The planner policy receives ONLY: task text, current active goal, and the
observation history. The environment's precondition table and the verifier's
effect-compatibility table are NEVER passed to the planner. A unit test asserts
this separation (planner inputs contain no precondition entries). If this
separation cannot be maintained — i.e. preconditions are visible to the
planner — the analog proves nothing and the project is KILLED under G2,
regardless of numbers.

## Arms (all scripted, deterministic, same step budget B=40/episode)

1. **`retry` (neither = ReAct-style free-text-retry baseline).** Flat action
   loop, no goal stack, no verification, no diagnosis. On failure it cycles
   through alternate plausible actions (reformatted args, doc lookup, sibling
   API) that never insert the missing prerequisite and never change the goal.
   Up to 12 attempts per episode, then fail.
2. **`veronly` (verification-only ablation).** Bounded goal stack + dual-horizon
   verification on activation / failure / material state change (alignment:
   does the active goal's effect contribute to the terminal goal? readiness:
   is it feasible in current state?). NO typed diagnosis: on a failed
   verification the goal is Popped as failed — no Push of a prerequisite, no
   BacktrackTo, no re-decomposition.
3. **`diagonly` (diagnosis-only ablation).** Typed failure attribution on
   failure (missing-prerequisite → Push; wrong-decomposition → BacktrackTo;
   transient → retry) but NO verification: no alignment/readiness checks on
   activation, so silently-wrong goals are never caught before execution.
4. **`vbl` (full VBL).** Bounded goal stack + dual-horizon verification +
   typed diagnosis → Push / Pop / retry / BacktrackTo-parent, with
   re-decomposition excluding the failed goal after a BacktrackTo.

## Metrics

- Task success: terminal predicate satisfied within budget (per episode).
- Recovery rate (family A): among family-A episodes, fraction that succeed
  after a precondition failure has occurred (every family-A episode hits one
  for the retry arm by construction; for VBL arms the failure is observed
  before recovery).
- Paired bootstrap: 10,000 resamples over task indices (arms paired on the
  same task), 95% percentile CIs on success-rate differences. Wilson 95% CIs
  on single-arm rates.

## Locked bars — ANY failure KILLS

- **G0 — tests + determinism.** Unit tests all green (≥20 tests). Full headline
  run repeated with the same seed produces a byte-identical `results.json`
  (sha256 match). FAIL → KILL.
- **G1 — author code.** COMPLETE live recheck (abs-page code link, GitHub
  search for title/authors, full-text HTML scan incl. figure captions) finds
  no author package. If author code exists → STAND DOWN, KILLED.md, no build.
- **G2 — disease (retry arm fails to recover).** On family A, retry-arm
  recovery rate ≤ 50% AND the upper bound of its Wilson 95% CI is strictly
  below the full-VBL recovery rate on family A. (Pre-registered before any
  run.) FAIL → KILL. Also FAIL if the latency guarantee above is violated.
- **G3 — load-bearing ablation structure.** On overall task success (180
  tasks):
  - (a) vbl − retry ≥ 10pp AND paired-bootstrap 95% CI lower bound > 0.
  - (b) vbl − veronly > 0 with paired-bootstrap 95% CI excluding 0.
  - (c) vbl − diagonly > 0 with paired-bootstrap 95% CI excluding 0.
  FAIL on any of (a)/(b)/(c) → KILL.

## Expected mechanism (prediction, not a bar)

vbl ≈ 100% (succeeds all families); veronly ≈ family C only (cannot Push a
prerequisite, cannot BacktrackTo — pops failed goals); diagonly ≈ families
A+C (repairs after failure, but never catches silent goal inversion);
retry ≈ family C only. The ablations are predicted to separate by mechanism,
not by tuning: no arm-specific parameters are tuned after locking.

## Artefacts on PASS

`PAPER.md` (claim, method, results with numbers, honest scripted-analog
limits), LinkedIn draft (DRAFT ONLY), staged push payload (code + tests +
README + LICENSE, no `.github/workflows`), report `REPO NEEDED:
habib-analyst/verify-backtrack`. No pushes. No edits to RESEARCH_LOG.md or
RESEARCH_AGENDA.md.
