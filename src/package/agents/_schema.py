"""Plan-reference grammar shared by the planner prompt and the executor (a protocol, not a setting)."""

import re


_REF = re.compile(r"^\$(\d+)((?:\.[\w*]+)*)$")  # "$1", "$1.candidates", "$2.ranked.*.item_id"

# Args whose literal (non-reference) string values must be copied from the user request, never invented.
ID_ARG_KEYS = ("user_id", "items", "item_ids")
