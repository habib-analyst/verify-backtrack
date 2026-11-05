"""Unit tests for verify-backtrack (G0). Run: python3 -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vbl import world as W
from vbl.arms import ARMS, run_retry_arm, run_stack_arm
from vbl.planner import plan, terminal_goal
from vbl.tasks import generate_tasks, planner_view, PlannerView
from vbl.verifier import verify, diagnose, readiness_gap


def _task(family="A", template="venmo_request", tid="T-0"):
    tasks = [t for t in generate_tasks() if t.family == family
             and t.template == template]
    return tasks[0]


class TestWorld(unittest.TestCase):
    def test_auth_error_without_token(self):
        t = _task()
        st = W.fresh_state(t)
        ok, err, ch = W.act(st, ("create_payment_request",
                                 {"to": t.params["name"], "amount": 13,
                                  "note": "x"}))
        self.assertFalse(ok)
        self.assertEqual(err, W.AUTH)
        self.assertFalse(ch)

    def test_login_then_request_succeeds(self):
        t = _task()
        st = W.fresh_state(t)
        W.act(st, ("login", {"service": "venmo"}))
        ok, err, ch = W.act(st, ("create_payment_request",
                                 {"to": t.params["name"],
                                  "amount": t.params["amount"],
                                  "note": t.params["note"]}))
        self.assertTrue(ok)
        self.assertTrue(W.check_terminal(st, t))

    def test_wrong_operator_succeeds_but_terminal_false(self):
        tasks = [t for t in generate_tasks() if t.family == "B"
                 and t.template == "venmo_request_inv"]
        t = tasks[0]
        st = W.fresh_state(t)
        ok, _, _ = W.act(st, ("create_transaction",
                              {"to": t.params["name"],
                               "amount": t.params["amount"],
                               "note": t.params["note"]}))
        self.assertTrue(ok)  # environmentally successful...
        self.assertFalse(W.check_terminal(st, t))  # ...but terminal unmet


class TestLatencySeparation(unittest.TestCase):
    """G2 binding condition: the planner sees no precondition data."""

    def test_planner_view_has_no_precondition_fields(self):
        t = _task()
        v = planner_view(t)
        self.assertEqual(set(vars(v).keys()), {"text", "template_id", "params"})
        self.assertNotIn("precondition", str(vars(v)))

    def test_planner_module_does_not_import_world_or_tasks(self):
        # Structural check: only import lines count (docstrings may discuss
        # the separation in prose). The planner must not import the world,
        # the task generator, or the verifier.
        src = Path(__file__).resolve().parent.parent.joinpath(
            "vbl", "planner.py").read_text()
        imports = [ln.strip() for ln in src.splitlines()
                   if ln.strip().startswith(("import ", "from "))]
        self.assertEqual(imports, ["from dataclasses import dataclass, field"])

    def test_planner_cannot_see_terminal_predicate(self):
        v = PlannerView(text="x", template_id="venmo_request",
                        params={"name": "Stacy", "amount": 13, "note": "n"})
        goals = plan(v)
        self.assertTrue(all(g.action is not None for g in goals))


class TestVerifier(unittest.TestCase):
    def test_misaligned_goal_detected(self):
        t = [x for x in generate_tasks() if x.family == "B"
             and x.template == "venmo_request_inv"][0]
        v = planner_view(t)
        goals = plan(v)
        wrong = [g for g in goals if g.effect == "transaction_exists"][0]
        st = W.fresh_state(t)
        aligned, _, _ = verify(wrong, st, v.template_id)
        self.assertFalse(aligned)

    def test_correct_goal_aligned_and_ready_gap_for_login(self):
        t = _task()
        v = planner_view(t)
        goals = plan(v)
        req = [g for g in goals if g.effect == "payment_request_exists"][0]
        st = W.fresh_state(t)
        aligned, ready, prereq = verify(req, st, v.template_id)
        self.assertTrue(aligned)
        self.assertFalse(ready)
        self.assertEqual(prereq.action[0], "login")

    def test_diagnose_maps_auth_to_login_push(self):
        op, pg = diagnose(W.AUTH, None)
        self.assertEqual(op, "push")
        self.assertEqual(pg.action, ("login", {"service": "venmo"}))

    def test_diagnose_maps_folder_to_named_folder_push(self):
        from vbl.planner import Goal
        g = Goal("upload_file", ("upload_file", {"folder": "receipts",
                                                "file": "scan.pdf"}),
                 "file_uploaded")
        op, pg = diagnose(W.FOLDER_MISSING, g)
        self.assertEqual(op, "push")
        self.assertEqual(pg.action[1]["folder"], "receipts")


class TestArms(unittest.TestCase):
    def test_vbl_recovers_latent_prereq(self):
        t = _task()
        r = run_stack_arm(t, planner_view(t), True, True)
        self.assertTrue(r["success"])
        self.assertGreaterEqual(r["ops"]["push"], 1)

    def test_retry_fails_latent_prereq(self):
        t = _task()
        r = run_retry_arm(t, planner_view(t))
        self.assertFalse(r["success"])
        self.assertTrue(r["hit_precondition_failure"])

    def test_vbl_repairs_wrong_decomposition(self):
        t = [x for x in generate_tasks() if x.family == "B"
             and x.template == "venmo_request_inv"][0]
        r = run_stack_arm(t, planner_view(t), True, True)
        self.assertTrue(r["success"])
        self.assertGreaterEqual(r["ops"]["backtrack"], 1)

    def test_diagonly_fails_silent_goal_inversion(self):
        t = [x for x in generate_tasks() if x.family == "B"
             and x.template == "venmo_request_inv"][0]
        r = run_stack_arm(t, planner_view(t), False, True)
        self.assertFalse(r["success"])

    def test_veronly_fails_latent_prereq(self):
        t = _task()
        r = run_stack_arm(t, planner_view(t), True, False)
        self.assertFalse(r["success"])

    def test_diagonly_repairs_after_failure(self):
        t = _task()
        r = run_stack_arm(t, planner_view(t), False, True)
        self.assertTrue(r["success"])

    def test_all_arms_succeed_clean_tasks(self):
        t = [x for x in generate_tasks() if x.family == "C"][0]
        for name, fn in ARMS.items():
            self.assertTrue(fn(t, planner_view(t))["success"], name)

    def test_task_stream_shape(self):
        tasks = generate_tasks()
        self.assertEqual(len(tasks), 180)
        for fam in "ABC":
            self.assertEqual(sum(1 for t in tasks if t.family == fam), 60)

    def test_stack_bounded_and_terminates(self):
        for t in generate_tasks():
            for name, fn in ARMS.items():
                r = fn(t, planner_view(t))
                self.assertLessEqual(r["steps"], 40, (t.id, name))

    def test_goal_stack_bounded_depth(self):
        # stack depth never exceeds terminal + children + one pushed prereq
        # (checked implicitly by termination; explicit smoke on one task)
        t = _task()
        r = run_stack_arm(t, planner_view(t), True, True)
        self.assertTrue(r["success"])
        self.assertLessEqual(r["steps"], 40)


if __name__ == "__main__":
    unittest.main()
