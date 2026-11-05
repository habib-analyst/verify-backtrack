"""Headline runner: paired arms on the fixed task stream, Wilson CIs on
rates, paired bootstrap (10,000 resamples) CIs on differences, determinism
check via sha256 of the results file. Pure stdlib, deterministic."""

import hashlib
import json
import math
import random
import sys

from .arms import ARMS
from .tasks import generate_tasks, planner_view, SEED

ARM_ORDER = ["retry", "veronly", "diagonly", "vbl"]
N_BOOT = 10000


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def paired_bootstrap_ci(a, b, seed=987654321, n_boot=N_BOOT):
    """95% percentile CI on mean(a) - mean(b), paired by task index."""
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(n_boot):
        sa = sb = 0
        for _ in range(n):
            i = rng.randrange(n)
            sa += a[i]
            sb += b[i]
        diffs.append((sa - sb) / n)
    diffs.sort()
    lo = diffs[int(0.025 * n_boot)]
    hi = diffs[int(0.975 * n_boot) - 1]
    return lo, hi


def run_all(seed=SEED):
    tasks = generate_tasks(seed)
    per_task = []  # [{arm: 0/1, ...}, ...] in task order
    details = {}
    for task in tasks:
        view = planner_view(task)
        row = {}
        for arm, fn in ARMS.items():
            r = fn(task, view)
            row[arm] = 1 if r["success"] else 0
        per_task.append(row)
        details[task.id] = {"family": task.family, "template": task.template,
                            **{a: per_task[-1][a] for a in ARM_ORDER}}
    return tasks, per_task, details


def summarize(tasks, per_task):
    n = len(tasks)
    out = {"n_tasks": n}
    fams = {}
    for t in tasks:
        fams.setdefault(t.family, []).append(t)
    for arm in ARM_ORDER:
        vals = [r[arm] for r in per_task]
        k = sum(vals)
        lo, hi = wilson(k, n)
        out[arm] = {"success": k, "rate": k / n, "wilson95": [lo, hi]}
        for fam, ftasks in fams.items():
            idx = [i for i, t in enumerate(tasks) if t.family == fam]
            fk = sum(per_task[i][arm] for i in idx)
            flo, fhi = wilson(fk, len(idx))
            out[arm][f"family_{fam}"] = {"success": fk, "n": len(idx),
                                         "rate": fk / len(idx),
                                         "wilson95": [flo, fhi]}
    # G2: retry recovery on family A vs vbl recovery on family A
    a_idx = [i for i, t in enumerate(tasks) if t.family == "A"]
    r_rec = sum(per_task[i]["retry"] for i in a_idx) / len(a_idx)
    v_rec = sum(per_task[i]["vbl"] for i in a_idx) / len(a_idx)
    r_lo, r_hi = wilson(sum(per_task[i]["retry"] for i in a_idx), len(a_idx))
    out["g2"] = {"retry_recovery_A": r_rec, "retry_wilson95": [r_lo, r_hi],
                 "vbl_recovery_A": v_rec}
    # G3: paired bootstrap differences
    for other in ["retry", "veronly", "diagonly"]:
        a = [r["vbl"] for r in per_task]
        b = [r[other] for r in per_task]
        lo, hi = paired_bootstrap_ci(a, b)
        out[f"vbl_minus_{other}"] = {
            "pp": (sum(a) - sum(b)) / n,
            "boot95": [lo, hi]}
    return out


def main():
    tasks, per_task, details = run_all()
    summary = summarize(tasks, per_task)
    payload = {"seed": SEED, "arm_order": ARM_ORDER,
               "summary": summary, "per_task": details}
    text = json.dumps(payload, indent=1, sort_keys=True)
    path = sys.argv[1] if len(sys.argv) > 1 else "results.json"
    with open(path, "w") as f:
        f.write(text + "\n")
    digest = hashlib.sha256(text.encode()).hexdigest()
    print(f"wrote {path}  sha256={digest}")
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    main()
