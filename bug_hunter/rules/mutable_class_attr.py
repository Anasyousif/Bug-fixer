"""
rules/mutable_class_attr.py
-----------------------------
Bug: defining a mutable attribute directly on a class body instead of
inside __init__.

    class ShoppingCart:
        items = []      # <-- shared by EVERY instance of ShoppingCart!

        def add(self, item):
            self.items.append(item)

Class-body assignments create a SINGLE object bound to the class itself.
Every instance that doesn't shadow it in __init__ shares that exact same
list/dict/set. Two unrelated ShoppingCart() instances would silently
share items. This is the class-level cousin of the mutable-default-arg bug.

IMPORTANT — false positive lesson learned:
A mutable class attribute is only an actual bug if it's ever MUTATED.
A class-level list used purely as a read-only constant (e.g. a list of
attribute names for serialization, iterated via `getattr(self, a)`) is
completely fine — the shared-object risk never materializes because
nothing ever calls .append/.pop/etc. on it. Testing this rule against
the real `requests` library surfaced exactly this: `Response.__attrs__`
and `Session.__attrs__` are class-level lists that are only ever read
(`for attr in self.__attrs__`), never mutated — flagging those as bugs
would be noise, not signal. So this rule now checks whether the
attribute is ever mutated anywhere in the class body before flagging it.

This rule flags true positives but does NOT auto-fix them, because the
correct fix depends on the class's __init__ structure (whether one
already exists, whether super().__init__() needs to be called first,
etc.) — that needs a human decision.
"""

import ast
from models import Bug

RULE_ID = "mutable-class-attribute"
MUTABLE_CONSTRUCTORS = (ast.List, ast.Dict, ast.Set)
MUTATING_METHODS = {"append", "extend", "insert", "remove", "pop", "clear",
                     "update", "add", "discard", "sort", "reverse", "popitem",
                     "setdefault"}


def _is_mutated_in_class(class_node, attr_name):
    """Looks for self.<attr_name>.<mutating_method>(...) or
    <attr_name>.<mutating_method>(...) (direct class-level access)
    anywhere within the class body."""
    for node in ast.walk(class_node):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in MUTATING_METHODS:
            continue

        target = node.func.value
        # self.attr_name.append(...)
        if (isinstance(target, ast.Attribute) and target.attr == attr_name
                and isinstance(target.value, ast.Name) and target.value.id == "self"):
            return True
        # ClassName.attr_name.append(...) or bare attr_name.append(...)
        if isinstance(target, ast.Name) and target.id == attr_name:
            return True

        # also catch item assignment via subscript mutation, e.g.
        # self.attr_name[key] = value  (handled separately below)
    for node in ast.walk(class_node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript):
                    base = t.value
                    if (isinstance(base, ast.Attribute) and base.attr == attr_name
                            and isinstance(base.value, ast.Name) and base.value.id == "self"):
                        return True
                    if isinstance(base, ast.Name) and base.id == attr_name:
                        return True
    return False


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            target_name = None
            value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                    and isinstance(stmt.targets[0], ast.Name):
                target_name = stmt.targets[0].id
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target_name = stmt.target.id
                value = stmt.value

            if value is None or not isinstance(value, MUTABLE_CONSTRUCTORS):
                continue

            if not _is_mutated_in_class(node, target_name):
                continue  # read-only class-level constant — not a bug

            snippet = source_lines[stmt.lineno - 1].strip()
            bugs.append(Bug(
                file=filepath,
                line=stmt.lineno,
                col=stmt.col_offset,
                rule_id=RULE_ID,
                title="Mutable class attribute",
                message=(
                    f"'{target_name}' in class '{node.name}' is a mutable "
                    f"class-level attribute that IS mutated elsewhere in the "
                    f"class (e.g. via .append/.update/etc.). It will be "
                    f"SHARED across every instance of {node.name}, so "
                    f"mutating it on one instance silently affects all others."
                ),
                severity="high",
                auto_fixable=False,
                suggested_fix_note=(
                    f"Move '{target_name} = ...' into __init__ as "
                    f"'self.{target_name} = ...' so each instance gets its own copy."
                ),
                code_snippet=snippet,
            ))
    return bugs
