"""REDTEAM CLI.

Safety: test ONLY models you own or have permission to test.
Your key = your usage = your cost.
"""

from __future__ import annotations

import argparse
import os
import sys

from redteam import __version__
from redteam import config as cfg
from redteam.attacks import list_attacks
from redteam.providers.anthropic import DEFAULT_MODEL as ANTH_MODEL, AnthropicProvider
from redteam.providers.base import Provider
from redteam.providers.gemini import DEFAULT_MODEL as GEM_MODEL, GeminiProvider
from redteam.providers.openai import DEFAULT_MODEL as OPENAI_MODEL, OpenAIProvider
from redteam.runner import SuiteResult, attack_success_rate, run_suite

SAFETY_NOTE = (
    "Test only models you own or have permission to test. "
    "Your key = your usage = your cost."
)

_PROVIDERS = {
    "openai": (OpenAIProvider, OPENAI_MODEL),
    "anthropic": (AnthropicProvider, ANTH_MODEL),
    "gemini": (GeminiProvider, GEM_MODEL),
}


def build_provider(name: str, key: str, model: str | None) -> Provider:
    cls, default_model = _PROVIDERS[name]
    return cls(api_key=key, model=model or default_model)


def cmd_list(args) -> int:
    attacks = list_attacks(args.suite if args.suite != "all" else None)
    print(f"{'ID':<10}{'CATEGORY':<12}{'SEV':<9}NAME")
    print("-" * 60)
    for a in attacks:
        print(f"{a.id:<10}{a.category:<12}{a.severity:<9}{a.name}")
    print(f"\n{len(attacks)} attacks. {SAFETY_NOTE}")
    return 0


def _resolve_key(args, provider_name: str | None) -> tuple[str, str]:
    """Returns (provider_name, key). Auto-detects provider from key when needed."""
    key = cfg.get_key(provider_name or "", explicit=args.key)
    if key and not provider_name:
        provider_name = cfg.detect_provider(key)
        key = cfg.get_key(provider_name, explicit=args.key)
    if not key:
        need = provider_name or "openai|anthropic|gemini"
        print(f"error: no API key for '{need}'. Use --key, env var, or "
              f"`redteam config --save-key PROVIDER`.", file=sys.stderr)
        raise SystemExit(2)
    assert provider_name
    return provider_name, key


def cmd_run(args) -> int:
    from redteam import report as report_mod

    provider_name, key = _resolve_key(args, args.provider)
    provider = build_provider(provider_name, key, args.model)
    attacks = list_attacks(args.suite if args.suite != "all" else None)
    if not attacks:
        print(f"error: unknown suite '{args.suite}'", file=sys.stderr)
        return 2

    judge = None
    if args.judge:
        judge = build_provider(provider_name, key, args.model)

    print(f"REDTEAM v{__version__} — {len(attacks)} attacks vs "
          f"{provider_name}/{provider.model} …")
    print(SAFETY_NOTE)

    def progress(attack_id: str, success: bool):
        mark = "💥" if success else "·"
        print(f"  {mark} {attack_id}", flush=True)

    suite = run_suite(provider, attacks, workers=args.workers,
                      timeout=args.timeout, judge=judge,
                      progress=progress if args.verbose else None)

    out = args.out or f"redteam-{provider.model.replace('/', '_')}.jsonl"
    suite.save_jsonl(out)
    print(f"\nresults → {out}")

    asr = attack_success_rate(suite.results)
    print(f"overall ASR: {asr['overall']*100:.1f}% "
          f"({sum(1 for r in suite.results if r.success)}/{len(suite.results)} leaked)")
    for cat in sorted(k for k in asr if k != "overall"):
        print(f"  {cat:<12} {asr[cat]*100:5.1f}%")

    if args.report:
        md = report_mod.to_markdown(provider_name, provider.model,
                                    suite.started_at, suite.results)
        html = report_mod.to_html(provider_name, provider.model,
                                  suite.started_at, suite.results)
        base = os.path.splitext(out)[0]
        open(base + ".md", "w", encoding="utf-8").write(md)
        open(base + ".html", "w", encoding="utf-8").write(html)
        print(f"report → {base}.md + {base}.html")
    return 0


def cmd_report(args) -> int:
    from redteam import report as report_mod
    suite = SuiteResult.load_jsonl(args.results)
    base = os.path.splitext(args.results)[0]
    if args.format in ("md", "both"):
        md = report_mod.to_markdown(suite.provider, suite.model,
                                    suite.started_at, suite.results)
        open(base + ".md", "w", encoding="utf-8").write(md)
        print(f"→ {base}.md")
    if args.format in ("html", "both"):
        html = report_mod.to_html(suite.provider, suite.model,
                                  suite.started_at, suite.results)
        open(base + ".html", "w", encoding="utf-8").write(html)
        print(f"→ {base}.html")
    return 0


def cmd_config(args) -> int:
    if args.save_key:
        cfg.save_key_interactive(args.save_key)
        print(f"key saved for {args.save_key} (0600). Value was never displayed.")
        return 0
    data = cfg.load_config()
    keys = data.get("keys", {})
    if isinstance(keys, dict) and keys:
        print("configured providers:", ", ".join(sorted(keys)))
    else:
        print("no keys configured. Use `redteam config --save-key PROVIDER`.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="redteam",
        description="LLM red-teaming framework (canary-based, defensive). " + SAFETY_NOTE)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list attacks")
    pl.add_argument("--suite", default="all",
                    help="all|injection|jailbreak|extraction|encoding|multiturn|logic")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("run", help="run a suite against a model")
    pr.add_argument("--provider", choices=["openai", "anthropic", "gemini"],
                    help="omit to auto-detect from key prefix")
    pr.add_argument("--model", help="override default model")
    pr.add_argument("--key", help="API key (or use env / config)")
    pr.add_argument("--suite", default="all",
                    help="all|injection|jailbreak|extraction|encoding|multiturn|logic")
    pr.add_argument("--workers", type=int, default=4)
    pr.add_argument("--timeout", type=int, default=90)
    pr.add_argument("--judge", action="store_true",
                    help="re-score with LLM-as-judge (doubles cost)")
    pr.add_argument("--out", help="results JSONL path")
    pr.add_argument("--report", action="store_true",
                    help="also write .md + .html reports")
    pr.add_argument("--verbose", action="store_true")
    pr.set_defaults(func=cmd_run)

    prp = sub.add_parser("report", help="render reports from a results JSONL")
    prp.add_argument("results", help="results .jsonl file")
    prp.add_argument("--format", choices=["md", "html", "both"], default="both")
    prp.set_defaults(func=cmd_report)

    pc = sub.add_parser("config", help="manage API keys")
    pc.add_argument("--save-key", metavar="PROVIDER",
                    choices=["openai", "anthropic", "gemini"])
    pc.set_defaults(func=cmd_config)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
