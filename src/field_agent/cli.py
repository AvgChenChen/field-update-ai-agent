"""Command line: python -m field_agent.cli "message text" [--project NAME]"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .config import Settings
from .extraction import ExtractionFailed, Extractor
from .providers.factory import build_provider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract structured data from a construction site update.")
    parser.add_argument("message")
    parser.add_argument("--project", default=None, help="Known project for the sender")
    parser.add_argument("--received", default=None, help="Date the message was received (YYYY-MM-DD)")
    parser.add_argument("--provider", default=None, help="anthropic, openai or heuristic (overrides LLM_PROVIDER)")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.provider:
        settings = Settings(**{**settings.__dict__, "llm_provider": args.provider})
    extractor = Extractor(build_provider(settings), settings.max_message_chars)
    try:
        received = date.fromisoformat(args.received) if args.received else None
        outcome = extractor.extract(args.message, args.project, received_on=received)
    except ExtractionFailed as e:
        print(json.dumps({"error": "extraction_failed", "detail": str(e)}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "provider": outcome.provider,
                "model": outcome.model,
                "extraction": outcome.final.model_dump(mode="json"),
                "guardrails": outcome.report.model_dump(mode="json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
