"""Dual-horizon verifier + typed diagnosis (controller-side components).

These tables are the VERIFIER's knowledge — the analog of the paper's LLM
Verify/Diagnose judgments. They are never passed to the planner. The
controller arms differ only in whether these components are switched on.
"""

from .planner import Goal
from . import world as W

# template -> (acceptable terminal effects, prerequisite effects)
TERMINAL_DESC = {
    "venmo_request": ({"payment_request_exists"}, {"contact_found", "token_exists"}),
    "venmo_request_inv": ({"payment_request_exists"}, {"contact_found", "token_exists"}),
    "schedule_meeting": ({"meeting_scheduled"}, {"contact_found", "calendar_connected"}),
    "upload_file": ({"file_uploaded"}, {"folder_exists"}),
    "share_file": ({"file_shared_read"}, {"file_exists"}),
    "decline_meeting": ({"meeting_declined"}, {"meeting_exists"}),
    "send_message": ({"message_sent"}, {"contact_found"}),
    "star_contact": ({"contact_starred"}, {"contact_found"}),
    "create_folder": ({"folder_exists"}, set()),
}


def _prereq_goal_for(missing):
    if missing == "token_exists":
        return Goal("login", ("login", {"service": "venmo"}), "token_exists")
    if missing == "calendar_connected":
        return Goal("connect_calendar", ("connect_calendar", {}),
                    "calendar_connected")
    if missing == "folder_exists":
        return Goal("create_folder", ("create_folder", {"folder": None}),
                    "folder_exists")
    return None


def readiness_gap(goal, state):
    """First unmet readiness condition for an action, or None if ready.
    Returns (missing_effect, prereq_goal_or_None)."""
    name, args = goal.action
    if name == "create_payment_request" or name == "create_transaction":
        if "venmo" not in state["tokens"]:
            return "token_exists", _prereq_goal_for("token_exists")
        if args["to"] not in state["contacts"]:
            return "contact_found", None
    elif name == "schedule_meeting":
        if not state["calendar_connected"]:
            return "calendar_connected", _prereq_goal_for("calendar_connected")
        if args["with"] not in state["contacts"]:
            return "contact_found", None
    elif name == "upload_file":
        if args["folder"] not in state["folders"]:
            pg = Goal("create_folder",
                      ("create_folder", {"folder": args["folder"]}),
                      "folder_exists")
            return "folder_exists", pg
    elif name in ("send_message", "star_contact", "search_contact"):
        who = args.get("to") or args.get("name")
        if who not in state["contacts"]:
            return "contact_found", None
    elif name == "share_file":
        if args["file"] not in state["files"]:
            return "file_exists", None
    elif name in ("decline_meeting", "delete_meeting"):
        if args["id"] not in state["meetings"]:
            return "meeting_exists", None
    return None


def verify(goal, state, template_id):
    """Dual-horizon verification. Returns (aligned, ready, prereq_goal)."""
    acceptable, prereqs = TERMINAL_DESC[template_id]
    aligned = goal.effect in acceptable or goal.effect in prereqs
    gap = readiness_gap(goal, state)
    ready = gap is None
    prereq = gap[1] if gap else None
    return aligned, ready, prereq


def diagnose(error_type, goal):
    """Typed failure attribution -> (operation, prereq_goal_or_None).
    Operations: 'push', 'retry', 'backtrack'. The pushed prerequisite is
    derived from the failing goal's own action arguments (e.g. the folder
    that was missing), never from hidden task data."""
    if error_type == W.AUTH:
        return "push", _prereq_goal_for("token_exists")
    if error_type == W.CAL_NOT_CONNECTED:
        return "push", _prereq_goal_for("calendar_connected")
    if error_type == W.FOLDER_MISSING:
        folder = goal.action[1]["folder"]
        return "push", Goal("create_folder",
                            ("create_folder", {"folder": folder}),
                            "folder_exists")
    if error_type == W.ARG_ERROR:
        return "retry", None
    return "backtrack", None
