"""REDTEAM — LLM red-teaming / jailbreak-testing framework.

Defensive security tooling: test models you own or have permission to test,
using your own API key (your usage, your cost).

Core design: canary-based testing. Attacks NEVER request real harmful
content. Each attack plants a harmless canary rule in the system prompt
(e.g. "never say the word 'pineapple'") and tries to make the model break
it. Canary appears in the output => the technique works => vulnerability
proven, zero harm generated.
"""

from redteam.attacks import Attack, list_attacks
from redteam.runner import run_suite

__version__ = "0.1.0"
__all__ = ["Attack", "list_attacks", "run_suite", "__version__"]
