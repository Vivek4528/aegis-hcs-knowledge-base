"""
Version scope utilities — parse and evaluate sw_rev scope expressions.
"""
import re
from functools import total_ordering


@total_ordering
class Version:
    def __init__(self, s: str):
        parts = str(s).strip().split(".")
        self.parts = tuple(int(x) for x in parts if x.isdigit())

    def __eq__(self, other):
        a, b = self._pad(self.parts, other.parts)
        return a == b

    def __lt__(self, other):
        a, b = self._pad(self.parts, other.parts)
        return a < b

    @staticmethod
    def _pad(a, b):
        n = max(len(a), len(b))
        return (a + (0,) * (n - len(a))), (b + (0,) * (n - len(b)))

    def __repr__(self):
        return ".".join(str(p) for p in self.parts)


_SCOPE_RE = re.compile(
    r"sw_rev\s*(>=|<=|>|<|==)\s*(\d+(?:\.\d+)*)"
)


def version_satisfies_scope(version_str: str, scope: str) -> bool:
    """
    Evaluate whether a software version string satisfies a scope expression.

    Examples:
      version_satisfies_scope("3.2",   "sw_rev >= 3.2")  → True
      version_satisfies_scope("3.1",   "sw_rev >= 3.2")  → False
      version_satisfies_scope("3.2.1", "sw_rev >= 3.2")  → True
      version_satisfies_scope("3.0",   "sw_rev < 3.2")   → True
      version_satisfies_scope("3.2",   "sw_rev < 3.2")   → False
    """
    if not scope:
        return True
    m = _SCOPE_RE.search(scope)
    if not m:
        return True  # unrecognised scope — treat as universal
    op, ref_str = m.group(1), m.group(2)
    v = Version(version_str)
    r = Version(ref_str)
    ops = {">=": v >= r, "<=": v <= r, ">": v > r, "<": v < r, "==": v == r}
    return ops.get(op, True)


def scope_label(scope: str) -> str:
    """Return a human-readable label for a version scope."""
    if not scope:
        return "all revisions"
    return scope.replace("sw_rev", "firmware")
