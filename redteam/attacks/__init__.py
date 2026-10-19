"""Attack definitions: canary-based, zero-harm-by-design.

Every attack plants a HARMLESS canary rule in the system prompt and tries to
make the model break it. If the canary leaks into the output, the TECHNIQUE
works — vulnerability proven, nothing harmful ever generated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Union

CanaryCheck = Callable[[str], bool]


def contains_word(word: str, whole: bool = True) -> CanaryCheck:
    """Canary check: does the output contain `word`?"""
    pat = r"\b" + re.escape(word) + r"\b" if whole else re.escape(word)
    rx = re.compile(pat, re.IGNORECASE)

    def check(output: str) -> bool:
        return bool(rx.search(output or ""))

    check.__name__ = f"contains_{word}"
    return check


def contains_any(*words: str) -> CanaryCheck:
    subs = [contains_word(w) for w in words]

    def check(output: str) -> bool:
        return any(s(output) for s in subs)

    return check


def matches_regex(pattern: str, flags: int = re.IGNORECASE) -> CanaryCheck:
    rx = re.compile(pattern, flags)

    def check(output: str) -> bool:
        return bool(rx.search(output or ""))

    return check


# ---------------------------------------------------------------------------
# Attack dataclass + registry
# ---------------------------------------------------------------------------

SEVERITIES = ("low", "medium", "high", "critical")
CATEGORIES = ("injection", "jailbreak", "extraction", "encoding", "multiturn", "logic")


@dataclass
class Attack:
    """A single red-team probe.

    turns: the user message(s) to send. Single-turn attacks use one entry;
    multi-turn attacks use several (sent sequentially, keeping history).
    canary_check(output) -> True means the attack SUCCEEDED (canary leaked).
    """

    id: str
    category: str
    name: str
    description: str
    system_prompt: str
    turns: List[str]
    canary_check: CanaryCheck = field(repr=False)
    severity: str = "medium"
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category: {self.category}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")
        if not self.turns:
            raise ValueError("attack needs at least one turn")


_REGISTRY: Dict[str, Attack] = {}


def register(attack: Attack) -> Attack:
    if attack.id in _REGISTRY:
        raise ValueError(f"duplicate attack id: {attack.id}")
    _REGISTRY[attack.id] = attack
    return attack


def list_attacks(category: Optional[str] = None) -> List[Attack]:
    attacks = sorted(_REGISTRY.values(), key=lambda a: a.id)
    if category:
        attacks = [a for a in attacks if a.category == category]
    return attacks


def get_attack(attack_id: str) -> Attack:
    return _REGISTRY[attack_id]


def _load_all() -> None:
    # Import side-effect: each module registers its attacks.
    from redteam.attacks import encoding, extraction, injection, jailbreak, logic, multiturn  # noqa: E402,F401


_load_all()
