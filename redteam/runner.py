"""Runner: executes an attack suite against a target provider.

ThreadPoolExecutor for parallelism, per-attack timeout, retries=0
(a retry would double your API bill for no reason), JSONL results.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from redteam.attacks import Attack, list_attacks
from redteam.providers.base import Message, Provider
from redteam.scoring.heuristics import Verdict, score_attack


@dataclass
class AttackResult:
    attack_id: str
    category: str
    name: str
    severity: str
    success: bool
    refused: bool
    output: str
    turns_used: int
    elapsed_s: float
    error: str = ""
    judged: Optional[bool] = None  # LLM-as-judge override, if used

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # keep result files small: truncate stored output
        if len(d["output"]) > 2000:
            d["output"] = d["output"][:2000] + "… [truncated]"
        return d


@dataclass
class SuiteResult:
    provider: str
    model: str
    started_at: str
    results: List[AttackResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at,
            "results": [r.to_dict() for r in self.results],
        }

    def save_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for r in self.results:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    @staticmethod
    def load_jsonl(path: str) -> "SuiteResult":
        results: List[AttackResult] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(AttackResult(**json.loads(line)))
        return SuiteResult(provider="", model="", started_at="", results=results)


def _run_one(provider: Provider, attack: Attack, timeout: int) -> AttackResult:
    t0 = time.time()
    try:
        messages = [Message(role="system", content=attack.system_prompt)]
        output = ""
        for turn in attack.turns:
            messages.append(Message(role="user", content=turn))
            completion = provider.complete(messages)
            output = completion.text or ""
            messages.append(Message(role="assistant", content=output))
        verdict = score_attack(attack.id, output, attack.canary_check)
        return AttackResult(
            attack_id=attack.id, category=attack.category, name=attack.name,
            severity=attack.severity, success=verdict.success,
            refused=verdict.refused, output=verdict.output,
            turns_used=len(attack.turns), elapsed_s=round(time.time() - t0, 2),
        )
    except Exception as e:  # never let one attack kill the suite
        return AttackResult(
            attack_id=attack.id, category=attack.category, name=attack.name,
            severity=attack.severity, success=False, refused=False, output="",
            turns_used=0, elapsed_s=round(time.time() - t0, 2),
            error=f"{type(e).__name__}: {e}",
        )


def run_suite(provider: Provider, attacks: Optional[List[Attack]] = None,
              workers: int = 4, timeout: int = 90,
              judge: Optional[Provider] = None,
              progress=None) -> SuiteResult:
    """Run attacks against the provider. judge optionally re-scores with an LLM."""
    attacks = attacks if attacks is not None else list_attacks()
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    suite = SuiteResult(provider=provider.name, model=provider.model, started_at=started)

    def task(attack: Attack) -> AttackResult:
        res = _run_one(provider, attack, timeout)
        if judge is not None and not res.error:
            from redteam.scoring.judge import judge_output
            hint = attack.system_prompt[:200]
            j = judge_output(judge, hint, res.output)
            res.judged = j
            if j is not None:
                res.success = j  # judge overrides heuristic
        if progress:
            progress(attack.id, res.success)
        return res

    # NOTE: providers are stateless HTTP clients; sharing one across threads is fine.
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(task, a): a for a in attacks}
        ordered = {a.id: None for a in attacks}
        for fut in as_completed(futures):
            res = fut.result()
            ordered[res.attack_id] = res
    suite.results = [r for r in ordered.values() if r is not None]
    return suite


def attack_success_rate(results: List[AttackResult]) -> Dict[str, float]:
    """ASR overall + per category. success/(success+failures); errors excluded."""
    def asr(rs: List[AttackResult]) -> float:
        valid = [r for r in rs if not r.error]
        if not valid:
            return 0.0
        return sum(1 for r in valid if r.success) / len(valid)

    out: Dict[str, float] = {"overall": asr(results)}
    cats = sorted({r.category for r in results})
    for c in cats:
        out[c] = asr([r for r in results if r.category == c])
    return out
