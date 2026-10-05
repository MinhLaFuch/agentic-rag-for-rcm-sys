import re


_REF = re.compile(r"^\$(\d+)((?:\.[\w*]+)*)$")  # "$1", "$1.candidates", "$2.ranked.*.item_id"