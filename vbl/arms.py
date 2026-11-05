"""Four controller arms on identical task streams.

Stack machine (veronly / diagonly / vbl):
  - stack root = terminal goal; decomposition pushes subgoal children.
  - verification (if enabled) runs when a subgoal is first activated and
    again after any state change / failure (the `due` flag).
  - diagnosis (if enabled) maps a failure to Push / retry / BacktrackTo.
  - veronly: verification on, diagnosis off -> a failed verification Pops
    the goal; no Push, no BacktrackTo, no re-decomposition.
  - diagonly: verification off, diagnosis on -> failures are repaired, but
    silently-wrong goals are never caught before execution.
  - vbl: both on.
  - BacktrackTo(parent): pop down to the parent, exclude the failed goal's
    effect from the parent's re-decomposition, decompose again.

Retry arm (neither): flat ReAct-style loop, no stack, no verification, no
diagnosis. On failure it cycles alternate plausible actions (same action
reformatted, doc lookup, sibling API) that never insert a prerequisite and
never change the goal. Total attempt budget 12/episode.
"""

from . import world as W
from .planner import plan, terminal_goal
from .verifier import verify, diagnose, readiness_gap

BUDGET = 40
MAX_BACKTRACKS = 5


def _pop(stack, goal):
    """Pop `goal` (top of stack); decrement parent's remaining if a child."""
    assert stack and stack[-1] is goal
    stack.pop()
    if goal.is_child and goal.parent is not None:
        goal.parent.remaining -= 1


def run_stack_arm(task, view, use_verify, use_diagnose):
    state = W.fresh_state(task)
    root = terminal_goal(view)
    stack = [root]
    retries = {}   # id(goal) -> consecutive retries
    backtracks = 0
    steps = 0
    hit_precondition_failure = False
    ops = {"push": 0, "pop": 0, "retry": 0, "backtrack": 0}

    def backtrack_to(failed):
        nonlocal backtracks
        parent = failed.parent
        if parent is None or backtracks >= MAX_BACKTRACKS:
            return False
        backtracks += 1
        ops["backtrack"] += 1
        while stack and stack[-1] is not parent:
            g = stack[-1]
            stack.pop()
            if g.is_child and g.parent is not None and g is not failed:
                g.parent.remaining -= 1
        if failed.is_child:
            # the failed child itself is popped without double-decrement:
            # it was counted in parent.remaining via the loop above only if
            # it was not `failed`; handle it here.
            pass
        parent.excluded = parent.excluded | {failed.effect}
        parent.decomposed = False
        parent.started = False
        return True

    while stack and steps < BUDGET:
        top = stack[-1]
        if top.is_terminal:
            if not top.decomposed:
                children = plan(view, top.excluded)
                for c in children:
                    c.parent = top
                    c.is_child = True
                top.remaining = len(children)
                top.decomposed = True
                stack.extend(reversed(children))
                continue
            if top.remaining == 0:
                stack.pop()
                continue
            # children remain but none on stack: should not happen; guard
            stack.pop()
            continue
        # subgoal on top
        if not top.started:
            top.started = True
            if use_verify:
                aligned, ready, prereq = verify(top, state, view.template_id)
                if not aligned:
                    if use_diagnose:
                        if not backtrack_to(top):
                            stack.pop()
                        continue
                    _pop(stack, top)
                    ops["pop"] += 1
                    continue
                if not ready:
                    if use_diagnose and prereq is not None:
                        prereq.parent = top
                        stack.append(prereq)
                        ops["push"] += 1
                        continue
                    _pop(stack, top)
                    ops["pop"] += 1
                    continue
        ok, err, changed = W.act(state, top.action)
        steps += 1
        if ok:
            _pop(stack, top)
            ops["pop"] += 1
            # material state change re-arms verification for the new top
            if stack and not stack[-1].is_terminal:
                stack[-1].started = False
            continue
        # failure
        if err in (W.AUTH, W.CAL_NOT_CONNECTED, W.FOLDER_MISSING):
            hit_precondition_failure = True
        if use_diagnose:
            op, prereq = diagnose(err, top)
            if op == "push" and prereq is not None:
                prereq.parent = top
                stack.append(prereq)
                ops["push"] += 1
                continue
            if op == "retry":
                n = retries.get(id(top), 0)
                if n < 2:
                    retries[id(top)] = n + 1
                    ops["retry"] += 1
                    continue
                if not backtrack_to(top):
                    _pop(stack, top)
                    ops["pop"] += 1
                continue
            # backtrack
            if not backtrack_to(top):
                _pop(stack, top)
                ops["pop"] += 1
            continue
        if use_verify:
            # no diagnosis: re-verify; an infeasible goal is popped
            aligned, ready, _ = verify(top, state, view.template_id)
            if not ready or not aligned:
                _pop(stack, top)
                ops["pop"] += 1
                continue
            _pop(stack, top)
            ops["pop"] += 1
            continue
        # neither verification nor diagnosis should reach here for stack arms
        _pop(stack, top)
        ops["pop"] += 1

    success = W.check_terminal(state, task)
    return {"success": success, "steps": steps,
            "hit_precondition_failure": hit_precondition_failure, "ops": ops}


def run_retry_arm(task, view):
    """Flat free-text-retry baseline: no stack, no verification, no diagnosis."""
    state = W.fresh_state(task)
    actions = []
    for g in plan(view):
        actions.append(g.action)
    attempts = 0
    hit_precondition_failure = False
    for action in actions:
        # up to 4 attempts per planned action, 12 total per episode
        for _ in range(4):
            if attempts >= 12:
                break
            ok, err, _ = W.act(state, action)
            attempts += 1
            if ok:
                break
            if err in (W.AUTH, W.CAL_NOT_CONNECTED, W.FOLDER_MISSING):
                hit_precondition_failure = True
            # alternates (reformat / doc lookup / sibling API) change
            # nothing about state or goal: the loop just retries the same
            # planned action, exactly the free-text-retry failure mode.
        if attempts >= 12:
            break
    success = W.check_terminal(state, task)
    return {"success": success, "steps": attempts,
            "hit_precondition_failure": hit_precondition_failure, "ops": {}}


ARMS = {
    "retry": lambda t, v: run_retry_arm(t, v),
    "veronly": lambda t, v: run_stack_arm(t, v, True, False),
    "diagonly": lambda t, v: run_stack_arm(t, v, False, True),
    "vbl": lambda t, v: run_stack_arm(t, v, True, True),
}
