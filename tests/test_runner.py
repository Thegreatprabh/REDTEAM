"""Runner tests: fake provider, no network. JSONL roundtrip + ASR math."""

import json
import os

from redteam.attacks import Attack, contains_word, list_attacks
from redteam.providers.base import Completion, Message, Provider
from redteam.runner import AttackResult, SuiteResult, attack_success_rate, run_suite


class ScriptedProvider(Provider):
    """Returns canned outputs per attack id (matched via system prompt canary word)."""

    name = "scripted"

    def __init__(self, leaks: set):
        super().__init__(api_key="fake", model="fake-model")
        self.leaks = leaks  # attack ids that should "succeed"

    def _url(self):
        return "http://localhost/"

    def _payload(self, messages):
        return {}

    def _parse(self, data):
        return ""

    def complete(self, messages):
        # identify the attack by its unique first user turn
        user_turns = [m.content for m in messages if m.role == "user"]
        first = user_turns[0] if user_turns else ""
        for a in list_attacks():
            if a.turns[0] == first:
                if a.id in self.leaks:
                    return Completion(text=_leak_for(a), model=self.model)
                return Completion(text="I'm sorry, I can't do that.", model=self.model)
        return Completion(text="ok", model=self.model)


def _leak_for(attack: Attack) -> str:
    # produce text that trips the attack's own canary check
    candidates = ["pineapple", "bluebird", "ZXQWV-7741", "mango", "cactus",
                  "lantern", "m4ng0", "ognam", "z n a t b".replace(" ", "")]
    for c in candidates:
        if attack.canary_check(f"here: {c}"):
            return f"here: {c}"
    # fallback: brute single words from the system prompt's quoted words
    import re
    for w in re.findall(r"'([a-z0-9\-]+)'", attack.system_prompt):
        if attack.canary_check(w):
            return w
    raise AssertionError(f"no leak text for {attack.id}")


def test_run_suite_counts_and_asr():
    attacks = list_attacks("injection")  # 10
    leaks = {"inj-001", "inj-003", "inj-010"}
    provider = ScriptedProvider(leaks)
    suite = run_suite(provider, attacks, workers=2)
    assert len(suite.results) == 10
    succeeded = {r.attack_id for r in suite.results if r.success}
    assert succeeded == leaks
    asr = attack_success_rate(suite.results)
    assert abs(asr["overall"] - 0.3) < 1e-9
    assert abs(asr["injection"] - 0.3) < 1e-9


def test_run_suite_provider_error_isolated():
    class Boom(Provider):
        name = "boom"

        def __init__(self):
            super().__init__(api_key="x", model="m")

        def _url(self):
            return "http://localhost/"

        def _payload(self, messages):
            return {}

        def _parse(self, data):
            return ""

        def complete(self, messages):
            raise RuntimeError("kaput")

    suite = run_suite(Boom(), list_attacks("logic")[:2], workers=1)
    assert all(r.error and not r.success for r in suite.results)


def test_jsonl_roundtrip(tmp_path):
    attacks = list_attacks("encoding")[:3]
    suite = run_suite(ScriptedProvider({"enc-001"}), attacks, workers=1)
    p = str(tmp_path / "r.jsonl")
    suite.save_jsonl(p)
    lines = open(p, encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 3
    assert all(json.loads(line)["attack_id"] for line in lines)
    loaded = SuiteResult.load_jsonl(p)
    assert len(loaded.results) == 3
    assert sum(1 for r in loaded.results if r.success) == 1


def test_asr_excludes_errors():
    rs = [
        AttackResult("a", "c", "n", "high", True, False, "x", 1, 0.1),
        AttackResult("b", "c", "n", "high", False, True, "y", 1, 0.1),
        AttackResult("c", "c", "n", "high", False, False, "", 1, 0.1, error="boom"),
    ]
    asr = attack_success_rate(rs)
    assert abs(asr["overall"] - 0.5) < 1e-9  # 1/2 valid


def test_asr_empty():
    assert attack_success_rate([])["overall"] == 0.0
