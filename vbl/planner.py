"""Scripted planner: a FIXED decomposition table.

The planner is a stand-in for an LLM planner. It receives ONLY a PlannerView
(text, template_id, params) — never preconditions, never the terminal
predicate, never the verifier's effect tables. Its entries are fixed and
public; the `_inv` templates encode the planner's mis-decomposition for
those episodes (the analog of an LLM picking a goal-inverting operator, as
in the paper's Appendix H case). The variable under test is the CONTROLLER
(verification/diagnosis switches), which is identical across arms except
for those switches — the planner table never changes between arms.
"""

from dataclasses import dataclass, field


@dataclass
class Goal:
    name: str
    action: tuple | None          # (action_name, args) or None for terminal
    effect: str
    parent: "Goal | None" = None
    is_terminal: bool = False
    excluded: frozenset = frozenset()
    decomposed: bool = False
    remaining: int = 0            # decomp children not yet popped
    started: bool = False
    is_child: bool = False        # True iff pushed by a decomposition


def _find(params):
    return Goal("find_contact", ("search_contact", {"name": params["name"]}),
                "contact_found")


def _request(params):
    return Goal("request_payment",
                ("create_payment_request",
                 {"to": params["name"], "amount": params["amount"],
                  "note": params["note"]}),
                "payment_request_exists")


def _send(params):
    return Goal("send_payment",
                ("create_transaction",
                 {"to": params["name"], "amount": params["amount"],
                  "note": params["note"]}),
                "transaction_exists")


def _schedule(params):
    return Goal("schedule_meeting",
                ("schedule_meeting",
                 {"with": params["name"], "id": params["meeting_id"]}),
                "meeting_scheduled")


def _upload(params):
    return Goal("upload_file",
                ("upload_file",
                 {"folder": params["folder"], "file": params["file"]}),
                "file_uploaded")


def _share(params, mode):
    eff = "file_shared_read" if mode == "read" else "file_shared_edit"
    return Goal("share_file", ("share_file", {"file": params["file"],
                                             "mode": mode}), eff)


def _decline(params):
    return Goal("decline_meeting",
                ("decline_meeting", {"id": params["meeting_id"]}),
                "meeting_declined")


def _delete(params):
    return Goal("delete_meeting",
                ("delete_meeting", {"id": params["meeting_id"]}),
                "meeting_deleted")


def _message(params):
    return Goal("send_message",
                ("send_message", {"to": params["name"],
                                  "text": "Running 10 minutes late."}),
                "message_sent")


def _star(params):
    return Goal("star_contact", ("star_contact", {"name": params["name"]}),
                "contact_starred")


def _mkdir(params):
    return Goal("create_folder",
                ("create_folder", {"folder": params["folder"]}),
                "folder_exists")


# template -> ordered candidate lists per subgoal slot. plan() picks the
# first candidate whose effect is not in `excluded` (re-decomposition after
# a BacktrackTo excludes the failed goal's effect).
TABLE = {
    "venmo_request": [[_find], [_request, _send]],
    "venmo_request_inv": [[_find], [_send, _request]],
    "schedule_meeting": [[_find], [_schedule]],
    "upload_file": [[_upload]],
    "share_file": [[lambda p: _share(p, "edit"), lambda p: _share(p, "read")]],
    "decline_meeting": [[_delete, _decline]],
    "send_message": [[_message]],
    "star_contact": [[_star]],
    "create_folder": [[_mkdir]],
}


def plan(view, excluded=frozenset()):
    """Decompose a terminal goal into subgoal Goals (planner-view only)."""
    slots = TABLE[view.template_id]
    goals = []
    for candidates in slots:
        for cand in candidates:
            g = cand(view.params)
            if g.effect not in excluded:
                goals.append(g)
                break
        else:
            # every candidate excluded: slot contributes nothing
            continue
    return goals


def terminal_goal(view):
    return Goal("terminal", None, "terminal", is_terminal=True)
