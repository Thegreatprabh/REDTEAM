"""Report generation: markdown + standalone HTML (dark hacker theme, inline
CSS, CSS-bar charts — no JS, no external libs)."""

from __future__ import annotations

import html
from collections import Counter
from typing import Dict, List

from redteam.runner import AttackResult, attack_success_rate

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def summarize(results: List[AttackResult]) -> Dict:
    asr = attack_success_rate(results)
    by_sev: Dict[str, List[AttackResult]] = {}
    for r in results:
        by_sev.setdefault(r.severity, []).append(r)
    sev_asr = {s: attack_success_rate(rs)["overall"] for s, rs in by_sev.items()}
    top = sorted(
        [r for r in results if r.success and not r.error],
        key=lambda r: (_SEV_ORDER.get(r.severity, 9), r.attack_id),
    )[:10]
    return {
        "total": len(results),
        "succeeded": sum(1 for r in results if r.success),
        "refused": sum(1 for r in results if r.refused),
        "errors": sum(1 for r in results if r.error),
        "asr": asr,
        "sev_asr": sev_asr,
        "top": top,
    }


def to_markdown(suite_provider: str, suite_model: str, started_at: str,
                results: List[AttackResult]) -> str:
    s = summarize(results)
    L: List[str] = []
    L.append(f"# REDTEAM Report — {suite_model}")
    L.append("")
    L.append(f"**Provider:** {suite_provider} · **Model:** `{suite_model}` · **Ran:** {started_at}")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append(f"- Attacks run: **{s['total']}**")
    L.append(f"- Succeeded (canary leaked): **{s['succeeded']}**")
    L.append(f"- Refused: **{s['refused']}** · Errors: **{s['errors']}**")
    L.append(f"- **Overall ASR: {_pct(s['asr']['overall'])}** (attack success rate)")
    L.append("")
    L.append("## ASR by category")
    L.append("")
    L.append("| Category | ASR |")
    L.append("|---|---|")
    for cat in sorted(k for k in s["asr"] if k != "overall"):
        L.append(f"| {cat} | {_pct(s['asr'][cat])} |")
    L.append("")
    L.append("## ASR by severity")
    L.append("")
    for sev in sorted(s["sev_asr"], key=lambda x: _SEV_ORDER.get(x, 9)):
        L.append(f"- **{sev}**: {_pct(s['sev_asr'][sev])}")
    L.append("")
    L.append("## Top successful attacks")
    L.append("")
    if not s["top"]:
        L.append("_None — the model resisted everything._")
    for r in s["top"]:
        L.append(f"### {r.attack_id} — {r.name} `[{r.severity}]`")
        out = (r.output or "")[:600].replace("\n", " ")
        L.append(f"> {out}")
        L.append("")
    L.append("## Per-attack details")
    L.append("")
    L.append("| ID | Category | Severity | Result |")
    L.append("|---|---|---|---|")
    for r in sorted(results, key=lambda x: x.attack_id):
        mark = "✅ leaked" if r.success else ("⛔ refused" if r.refused else ("⚠️ error" if r.error else "❌ blocked"))
        L.append(f"| {r.attack_id} | {r.category} | {r.severity} | {mark} |")
    L.append("")
    L.append("_Canary-based testing: each attack plants a harmless fake rule; a leak "
             "proves the technique works. No real harmful content was requested._")
    return "\n".join(L)


def _bar(pct: float) -> str:
    w = max(2, int(pct * 100))
    color = "#ff5555" if pct >= 0.5 else ("#ffb86c" if pct >= 0.2 else "#50fa7b")
    return (f'<div class="bar"><div class="fill" style="width:{w}%;'
            f'background:{color}"></div><span>{pct*100:.1f}%</span></div>')


def to_html(suite_provider: str, suite_model: str, started_at: str,
            results: List[AttackResult]) -> str:
    s = summarize(results)
    esc = html.escape
    rows = []
    for r in sorted(results, key=lambda x: x.attack_id):
        cls = "ok" if r.success else ("ref" if r.refused else ("err" if r.error else "blk"))
        mark = "LEAKED" if r.success else ("REFUSED" if r.refused else ("ERROR" if r.error else "BLOCKED"))
        rows.append(
            f'<tr class="{cls}"><td>{esc(r.attack_id)}</td><td>{esc(r.category)}</td>'
            f'<td>{esc(r.severity)}</td><td>{mark}</td></tr>')
    cats = "".join(
        f'<div class="cat"><label>{esc(c)}</label>{_bar(s["asr"][c])}</div>'
        for c in sorted(k for k in s["asr"] if k != "overall"))
    top = "".join(
        f'<div class="top"><b>{esc(r.attack_id)}</b> — {esc(r.name)} '
        f'<span class="sev">{esc(r.severity)}</span><p>{esc((r.output or "")[:400])}</p></div>'
        for r in s["top"]) or "<p><i>None — the model resisted everything.</i></p>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>REDTEAM Report — {esc(suite_model)}</title>
<style>
body{{background:#0d1117;color:#c9d1d9;font-family:ui-monospace,Menlo,monospace;margin:0;padding:24px}}
h1{{color:#ff5555}}h2{{color:#50fa7b;border-bottom:1px solid #30363d;padding-bottom:6px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:12px 0}}
.big{{font-size:2em;color:#ff5555}}
.bar{{background:#21262d;border-radius:4px;height:22px;position:relative;margin:6px 0}}
.fill{{height:100%;border-radius:4px}}
.bar span{{position:absolute;right:8px;top:2px;font-size:12px;color:#fff}}
.cat label{{display:inline-block;width:110px;color:#8b949e}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border:1px solid #30363d;padding:6px 8px;text-align:left}}
tr.ok td:last-child{{color:#ff5555;font-weight:bold}}
tr.ref td:last-child{{color:#50fa7b}}tr.err td:last-child{{color:#ffb86c}}tr.blk td:last-child{{color:#8b949e}}
.sev{{background:#ff5555;color:#000;border-radius:4px;padding:1px 6px;font-size:11px}}
.top{{background:#161b22;border-left:3px solid #ff5555;padding:8px 12px;margin:8px 0}}
.top p{{color:#8b949e;font-size:12px;white-space:pre-wrap}}
.note{{color:#8b949e;font-size:12px}}
</style></head><body>
<h1>☠️ REDTEAM Report</h1>
<div class="card">Model <b>{esc(suite_model)}</b> ({esc(suite_provider)}) · ran {esc(started_at)}<br>
<span class="big">{s['asr']['overall']*100:.1f}%</span> overall attack success rate
· {s['succeeded']}/{s['total']} attacks leaked the canary
· {s['refused']} refused · {s['errors']} errors</div>
<h2>ASR by category</h2><div class="card">{cats}</div>
<h2>Top successful attacks</h2>{top}
<h2>Per-attack details</h2><div class="card"><table>
<tr><th>ID</th><th>Category</th><th>Severity</th><th>Result</th></tr>
{''.join(rows)}</table></div>
<p class="note">Canary-based testing: each attack plants a harmless fake rule; a leak proves the
technique works. No real harmful content was requested or generated.</p>
</body></html>
"""
