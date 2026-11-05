"""Simulated service world for the verify-backtrack scripted analog.

State is a plain dict. Actions are deterministic functions of state and return
( ok, error_type_or_None, state_changed ). Typed errors are the ONLY failure
signal, mirroring the paper's execution-feedback-only protocol. The terminal
goal predicate is evaluated only by the environment (``check_terminal``);
agents never receive it.
"""

# --- error types -----------------------------------------------------------
AUTH = "auth_required"            # a login token is missing
CAL_NOT_CONNECTED = "calendar_not_connected"
FOLDER_MISSING = "folder_missing"
ARG_ERROR = "arg_error"            # transient / malformed arguments
NOT_FOUND = "not_found"


def fresh_state(task):
    """Initial world state for a task. Preconditions live ONLY here."""
    st = {
        "tokens": set(task.initial_tokens),
        "contacts": set(task.contacts),
        "payment_requests": [],   # (to, amount, note)
        "transactions": [],       # (to, amount, note)
        "calendar_connected": task.initial_calendar,
        "folders": set(task.initial_folders),
        "files": dict(task.initial_files),       # name -> folder
        "shared": {},             # file -> mode ("read" | "edit")
        "meetings": dict(task.initial_meetings),  # id -> status
        "starred": set(),
        "messages": [],           # (to, text)
    }
    return st


def act(state, action):
    """Execute one action. Returns (ok, error_type_or_None, changed)."""
    name, args = action
    if name == "login":
        state["tokens"].add(args["service"])
        return True, None, True
    if name == "connect_calendar":
        state["calendar_connected"] = True
        return True, None, True
    if name == "create_folder":
        state["folders"].add(args["folder"])
        return True, None, True
    if name == "search_contact":
        if args["name"] in state["contacts"]:
            return True, None, False
        return False, NOT_FOUND, False
    if name == "create_payment_request":
        if "venmo" not in state["tokens"]:
            return False, AUTH, False
        if args["to"] not in state["contacts"]:
            return False, NOT_FOUND, False
        state["payment_requests"].append((args["to"], args["amount"], args["note"]))
        return True, None, True
    if name == "create_transaction":
        if "venmo" not in state["tokens"]:
            return False, AUTH, False
        if args["to"] not in state["contacts"]:
            return False, NOT_FOUND, False
        state["transactions"].append((args["to"], args["amount"], args["note"]))
        return True, None, True
    if name == "schedule_meeting":
        if not state["calendar_connected"]:
            return False, CAL_NOT_CONNECTED, False
        if args["with"] not in state["contacts"]:
            return False, NOT_FOUND, False
        state["meetings"][args["id"]] = "scheduled"
        return True, None, True
    if name == "upload_file":
        if args["folder"] not in state["folders"]:
            return False, FOLDER_MISSING, False
        state["files"][args["file"]] = args["folder"]
        return True, None, True
    if name == "send_message":
        if args["to"] not in state["contacts"]:
            return False, NOT_FOUND, False
        state["messages"].append((args["to"], args["text"]))
        return True, None, True
    if name == "star_contact":
        if args["name"] not in state["contacts"]:
            return False, NOT_FOUND, False
        state["starred"].add(args["name"])
        return True, None, True
    if name == "share_file":
        if args["file"] not in state["files"]:
            return False, NOT_FOUND, False
        state["shared"][args["file"]] = args["mode"]
        return True, None, True
    if name == "decline_meeting":
        if args["id"] not in state["meetings"]:
            return False, NOT_FOUND, False
        state["meetings"][args["id"]] = "declined"
        return True, None, True
    if name == "delete_meeting":
        if args["id"] not in state["meetings"]:
            return False, NOT_FOUND, False
        del state["meetings"][args["id"]]
        return True, None, True
    raise ValueError(f"unknown action {name!r}")


def check_terminal(state, task):
    """Terminal predicate, evaluated by the environment only."""
    return task.terminal_check(state)
