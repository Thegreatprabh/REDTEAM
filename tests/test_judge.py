"""Judge tests: LLM-as-judge parsing, fully mocked."""

from redteam.providers.base import Completion, Message, Provider
from redteam.scoring.judge import judge_output


class FakeJudge(Provider):
    name = "fakejudge"

    def __init__(self, reply=None, boom=False):
        super().__init__(api_key="x", model="m")
        self._reply = reply
        self._boom = boom

    def _url(self):
        return "http://localhost/"

    def _payload(self, messages):
        return {}

    def _parse(self, data):
        return ""

    def complete(self, messages):
        if self._boom:
            raise RuntimeError("down")
        return Completion(text=self._reply or "", model=self.model)


def test_judge_yes():
    p = FakeJudge("YES — the word pineapple appears in the output.")
    assert judge_output(p, "never say pineapple", "I say pineapple") is True


def test_judge_no():
    p = FakeJudge("NO. The output is a polite refusal.")
    assert judge_output(p, "never say pineapple", "I'm sorry") is False


def test_judge_ambiguous_returns_none():
    p = FakeJudge("Maybe, hard to tell.")
    assert judge_output(p, "rule", "output") is None


def test_judge_error_returns_none():
    p = FakeJudge(boom=True)
    assert judge_output(p, "rule", "output") is None


def test_judge_sends_rule_and_output():
    seen = {}

    class Spy(FakeJudge):
        def complete(self, messages):
            seen["prompt"] = messages[0].content
            return super().complete(messages)

    s = Spy("NO")
    judge_output(s, "HINT-XYZ", "OUT-ABC")
    assert "HINT-XYZ" in seen["prompt"] and "OUT-ABC" in seen["prompt"]
