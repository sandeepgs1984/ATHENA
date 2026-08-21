"""Reproducible EM-1r2 corporate-action evidence materialization command."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from athena.data.corporate_action_ingestion import CorporateActionIngestionService
from athena.data.providers.nse_corporate_actions_provider import (
    CapturedNseCorporateActionsProvider,
    NseCorporateActionsProvider,
)
from athena.data.store.repository import SqliteRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize official NSE corporate-action evidence for EM-1r2."
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--study-start", type=date.fromisoformat, required=True)
    parser.add_argument("--study-end", type=date.fromisoformat, required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--cohort-resolution-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        help="Replay checksum-verified raw NSE payloads from an existing manifest.",
    )
    args = parser.parse_args()

    provider = (
        CapturedNseCorporateActionsProvider(
            source_manifest=args.source_manifest,
            evidence_root=args.evidence_root,
        )
        if args.source_manifest
        else NseCorporateActionsProvider()
    )

    repository = SqliteRepository(args.db)
    try:
        result = CorporateActionIngestionService(
            repository=repository,
            provider=provider,
            evidence_root=args.evidence_root,
        ).run(
            study_start=args.study_start,
            study_end=args.study_end,
            universe_name=args.universe,
            cohort_resolution_date=args.cohort_resolution_date,
        )
    finally:
        repository.close()

    manifest = result.manifest
    print(
        json.dumps(
            {
                "manifest_id": manifest.manifest_id,
                "replay_id": manifest.replay_id,
                "manifest_path": str(result.manifest_path),
                "study_start": manifest.study_start.isoformat(),
                "study_end": manifest.study_end.isoformat(),
                "cohort_name": manifest.cohort.name,
                "cohort_size": len(manifest.cohort.instrument_ids),
                "retrieval_slices": len(manifest.retrieval_slices),
                "complete_slices": sum(item.complete for item in manifest.retrieval_slices),
                "source_records": sum(item.record_count for item in manifest.retrieval_slices),
                "normalized_actions": len(manifest.actions),
                "exclusions": len(manifest.exclusions),
                "authoritative_for_research": manifest.authoritative_for_research,
                "inserted_actions": result.inserted_actions,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
