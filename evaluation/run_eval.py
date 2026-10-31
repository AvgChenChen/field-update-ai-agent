"""Run the extraction evaluation and write a JSON + Markdown report.

    python evaluation/run_eval.py --provider heuristic
    ANTHROPIC_API_KEY=... python evaluation/run_eval.py --provider anthropic

Every number in the report comes from this run. Failures are listed case by case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from field_agent.config import Settings
from field_agent.evaluation import CaseScore, score_case, summarize
from field_agent.extraction import ExtractionFailed, Extractor
from field_agent.prompts import PROMPT_VERSION
from field_agent.providers.base import ProviderRefused, ProviderUnavailable
from field_agent.providers.factory import build_provider

HERE = Path(__file__).parent
# Every case is treated as received on this Monday, so relative dates have one right answer.
DEFAULT_RECEIVED = date(2026, 11, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="heuristic", choices=["heuristic", "anthropic", "openai"])
    parser.add_argument("--dataset", default=str(HERE / "dataset.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results"))
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases (to control API cost)")
    args = parser.parse_args()

    settings = Settings(**{**Settings.from_env().__dict__, "llm_provider": args.provider})
    provider = build_provider(settings)
    extractor = Extractor(provider, settings.max_message_chars)
    raw_dataset = Path(args.dataset).read_bytes()
    cases = [json.loads(line) for line in raw_dataset.decode().splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    scores: list[CaseScore] = []
    for case in cases:
        try:
            received = date.fromisoformat(case["received_on"]) if case.get("received_on") else DEFAULT_RECEIVED
            outcome = extractor.extract(case["message"], case.get("project_hint"), received_on=received)
            scores.append(score_case(case, outcome.raw, outcome.final, outcome.report.injection_flags))
        except (ExtractionFailed, ProviderRefused) as e:
            scores.append(score_case(case, None, None, None, error=f"{type(e).__name__}: {e}"))
        except ProviderUnavailable as e:
            print(f"Provider unavailable, stopping: {e}", file=sys.stderr)
            return 2
        print(f"  {case['id']:<24} {'ok' if scores[-1].schema_valid else 'FAILED'}", file=sys.stderr)

    summary = summarize(scores)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    meta = {"provider": provider.name, "model": provider.model, "run_at": stamp, "dataset": Path(args.dataset).name}
    label = "dev" if Path(args.dataset).stem == "dataset" else Path(args.dataset).stem
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{provider.name}-{label}-{stamp}.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "cases": [asdict(s) for s in scores]}, indent=2)
    )
    report = render_markdown(meta, summary, scores, cases)
    (out / f"{provider.name}-{label}-latest.md").write_text(report)
    # Append-only audit trail: one line per run, committed to the repository.
    with (out / "history.jsonl").open("a") as history:
        history.write(
            json.dumps(
                {
                    **meta,
                    "prompt_version": PROMPT_VERSION,
                    "limit": args.limit,
                    "dataset_sha256": hashlib.sha256(raw_dataset).hexdigest()[:16],
                    "summary": summary,
                }
            )
            + "\n"
        )
    print(report)
    return 0


def render_markdown(meta: dict, summary: dict, scores: list[CaseScore], cases: list[dict]) -> str:
    def pct(m: dict) -> str:
        return "n/a" if m["rate"] is None else f"{m['correct']}/{m['total']} ({m['rate'] * 100:.1f}%)"

    by_id = {c["id"]: c for c in cases}
    lines = [
        f"# Evaluation: {meta['provider']} ({meta['model']})",
        "",
        f"Run at {meta['run_at']} on `{meta['dataset']}` ({summary['cases']} fictional messages).",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Schema-valid outputs | {pct(summary['schema_valid'])} |",
        f"| Trade identified correctly | {pct(summary['trade_accuracy'])} |",
        f"| Delay identified correctly | {pct(summary['delay_accuracy'])} |",
        f"| Blocker yes/no correct | {pct(summary['blocker_accuracy'])} |",
        f"| Blocker category correct (labelled cases) | {pct(summary['blocker_category_accuracy'])} |",
        f"| Relative dates resolved correctly (labelled cases) | {pct(summary['dates_resolved_correctly'])} |",
        f"| Unsupported assumptions in raw output | {summary['unsupported_assumptions_raw']} |",
        f"| Unsupported assumptions after guardrails | {summary['unsupported_assumptions_after_guardrails']} |",
        f"| Injection attempts flagged | {pct(summary['injection_flagged'])} |",
        f"| Injection instructions followed | {summary['injection_followed']} |",
        "",
        "## Cases with at least one miss",
        "",
        "| Case | Miss | Expected | Got |",
        "|---|---|---|---|",
    ]
    for s in scores:
        exp = by_id[s.case_id]["expected"]
        if not s.schema_valid:
            lines.append(f"| {s.case_id} | invalid output | - | {s.error} |")
            continue
        p = s.predicted
        if s.trade_correct is False:
            lines.append(f"| {s.case_id} | trade | {exp['trade']} | {p['trade']} |")
        if s.delay_correct is False:
            lines.append(f"| {s.case_id} | delay | {exp['delay_reported']} | {p['delay_reported']} |")
        if s.blocker_correct is False:
            lines.append(f"| {s.case_id} | blocker | {exp['is_blocker']} | {p['is_blocker']} |")
        if s.category_correct is False:
            lines.append(
                f"| {s.case_id} | category | {exp['blocker_category']} | {p['category'] if p['is_blocker'] else 'not a blocker'} |"
            )
        if s.dates_correct is False:
            lines.append(f"| {s.case_id} | dates | {exp['dates']} | {p.get('dates')} |")
        if s.unsupported_final:
            lines.append(f"| {s.case_id} | unsupported after guardrails | - | {', '.join(s.unsupported_final)} |")
        if s.injection_flagged is False:
            lines.append(f"| {s.case_id} | injection not flagged | flagged | not flagged |")
        if s.injection_followed:
            lines.append(
                f"| {s.case_id} | followed injected instruction | not {exp['forbidden_work_status']} | {p['work_status']} |"
            )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
