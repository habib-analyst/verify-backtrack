"""Task generation (seed 20261102) and the planner-view separation.

A full Task carries everything the ENVIRONMENT needs, including latent
preconditions (initial state). The planner never sees a Task: it receives a
PlannerView with only (text, template_id, params). The precondition table
lives in this module and in world.py; planner.py imports neither.
"""

import random
from dataclasses import dataclass, field

SEED = 20261102

NAMES = ["Stacy", "Mara", "Devon", "Priya", "Omar", "Lena", "Kofi", "Ines"]
NOTES = ["For yesterday's meal", "Rent split", "Concert tickets", "Book club"]
FOLDERS = ["receipts", "invoices", "travel", "tax2026"]
FILES = ["scan.pdf", "bill.png", "ticket.pdf", "form.docx"]


@dataclass
class Task:
    id: str
    family: str          # "A" latent-prereq | "B" wrong-decomp | "C" clean
    template: str
    text: str
    params: dict
    # --- environment-only fields; NEVER passed to the planner ---------------
    initial_tokens: tuple = ()
    initial_calendar: bool = False
    initial_folders: tuple = ()
    initial_files: dict = field(default_factory=dict)
    initial_meetings: dict = field(default_factory=dict)
    contacts: tuple = ()
    terminal_check: object = None  # callable(state) -> bool


@dataclass(frozen=True)
class PlannerView:
    """Everything the planner is allowed to see. No preconditions, no
    terminal predicate, no effect tables."""
    text: str
    template_id: str
    params: dict


def planner_view(task):
    return PlannerView(text=task.text, template_id=task.template,
                       params=dict(task.params))


def _a1(rng, i):
    name, amount, note = rng.choice(NAMES), rng.choice([13, 25, 40, 7]), rng.choice(NOTES)
    return Task(
        id=f"A1-{i}", family="A", template="venmo_request",
        text=f"Request ${amount} from {name} on Venmo with note '{note}'.",
        params={"name": name, "amount": amount, "note": note},
        contacts=(name,),
        terminal_check=lambda s, n=name, a=amount, no=note:
            (n, a, no) in s["payment_requests"],
    )


def _a2(rng, i):
    name = rng.choice(NAMES)
    return Task(
        id=f"A2-{i}", family="A", template="schedule_meeting",
        text=f"Schedule a meeting with {name} for tomorrow 10am.",
        params={"name": name, "meeting_id": f"m{i}"},
        contacts=(name,),
        terminal_check=lambda s, mid=f"m{i}": s["meetings"].get(mid) == "scheduled",
    )


def _a3(rng, i):
    folder, fname = rng.choice(FOLDERS), rng.choice(FILES)
    return Task(
        id=f"A3-{i}", family="A", template="upload_file",
        text=f"Upload {fname} to the {folder} folder.",
        params={"folder": folder, "file": fname},
        terminal_check=lambda s, f=fname, fo=folder: s["files"].get(f) == fo,
    )


def _b1(rng, i):
    name, amount, note = rng.choice(NAMES), rng.choice([13, 25, 40, 7]), rng.choice(NOTES)
    return Task(
        id=f"B1-{i}", family="B", template="venmo_request_inv",
        text=f"Request ${amount} from {name} on Venmo with note '{note}'.",
        params={"name": name, "amount": amount, "note": note},
        contacts=(name,), initial_tokens=("venmo",),
        terminal_check=lambda s, n=name, a=amount, no=note:
            (n, a, no) in s["payment_requests"],
    )


def _b2(rng, i):
    fname = rng.choice(FILES)
    return Task(
        id=f"B2-{i}", family="B", template="share_file",
        text=f"Share {fname} read-only with the team.",
        params={"file": fname},
        initial_files={fname: "shared"},
        terminal_check=lambda s, f=fname: s["shared"].get(f) == "read",
    )


def _b3(rng, i):
    return Task(
        id=f"B3-{i}", family="B", template="decline_meeting",
        text=f"Decline the meeting invite {i} (do not delete it).",
        params={"meeting_id": f"inv{i}"},
        initial_meetings={f"inv{i}": "scheduled"},
        terminal_check=lambda s, mid=f"inv{i}": s["meetings"].get(mid) == "declined",
    )


def _c1(rng, i):
    name = rng.choice(NAMES)
    return Task(
        id=f"C1-{i}", family="C", template="send_message",
        text=f"Send a message to {name}: 'Running 10 minutes late.'",
        params={"name": name},
        contacts=(name,),
        terminal_check=lambda s, n=name: any(t == n for t, _ in s["messages"]),
    )


def _c2(rng, i):
    name = rng.choice(NAMES)
    return Task(
        id=f"C2-{i}", family="C", template="star_contact",
        text=f"Star the contact {name}.",
        params={"name": name},
        contacts=(name,),
        terminal_check=lambda s, n=name: n in s["starred"],
    )


def _c3(rng, i):
    folder = rng.choice(FOLDERS)
    return Task(
        id=f"C3-{i}", family="C", template="create_folder",
        text=f"Create a folder named {folder}.",
        params={"folder": folder},
        terminal_check=lambda s, fo=folder: fo in s["folders"],
    )


def generate_tasks(seed=SEED):
    rng = random.Random(seed)
    tasks = []
    for i in range(20):
        tasks.append(_a1(rng, i))
    for i in range(20):
        tasks.append(_a2(rng, i))
    for i in range(20):
        tasks.append(_a3(rng, i))
    for i in range(20):
        tasks.append(_b1(rng, i))
    for i in range(20):
        tasks.append(_b2(rng, i))
    for i in range(20):
        tasks.append(_b3(rng, i))
    for i in range(20):
        tasks.append(_c1(rng, i))
    for i in range(20):
        tasks.append(_c2(rng, i))
    for i in range(20):
        tasks.append(_c3(rng, i))
    rng.shuffle(tasks)
    return tasks
