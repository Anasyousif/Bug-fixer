"""
rules package
-------------
Every rule module exposes a `check(tree, source_lines, filepath) -> list[Bug]`
function. To add a new rule: create a new module here with that function,
then register it in ALL_RULES below.
"""

from . import mutable_default
from . import bare_except
from . import none_comparison
from . import raise_e
from . import mutable_class_attr
from . import unclosed_file
from . import mutate_while_iterating

ALL_RULES = [
    mutable_default,
    bare_except,
    none_comparison,
    raise_e,
    mutable_class_attr,
    unclosed_file,
    mutate_while_iterating,
]
