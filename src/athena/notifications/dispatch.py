"""Briefing dispatcher: assemble then notify (M10.3)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.models import DecisionThresholdsCfg, NotificationsConfig
from athena.data.store.repository import SqliteRepository
from athena.errors import BriefingError
from athena.notifications.builder import DailyBriefingBuilder, DecisionSummarySource
from athena.notifications.models import BriefingDispatchResult, BriefingStatus, DeliveryReceipt
from athena.notifications.notifiers import EmailNotifier, FileNotifier, Notifier, WebhookNotifier


class BriefingDispatcher:
    """Build a daily briefing and deliver it through configured notifiers."""

    def __init__(
        self,
        repo: SqliteRepository,
        config: NotificationsConfig,
        *,
        tzinfo: ZoneInfo,
        decision_source: DecisionSummarySource | None = None,
        decision_thresholds: DecisionThresholdsCfg | None = None,
        notifiers: Sequence[Notifier] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        if not config.enabled:
            raise BriefingError("notifications are disabled in config/notifications.json")
        self._builder = DailyBriefingBuilder(
            repo, config, tzinfo=tzinfo, decision_source=decision_source,
            decision_thresholds=decision_thresholds,
        )
        self._config = config
        self._repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
        self._notifiers = list(notifiers) if notifiers is not None else self._default_notifiers()

    def dispatch(self, *, as_of: datetime, dry_run: bool = False) -> BriefingDispatchResult:
        briefing = self._builder.build(as_of=as_of)
        if briefing.status is BriefingStatus.FAILED:
            raise BriefingError(
                f"briefing {briefing.briefing_id} status FAILED: "
                f"{', '.join(briefing.degradation_reasons) or 'unknown'}"
            )

        notifiers = self._notifiers
        if dry_run:
            file_cfg = self._config.channels.file
            out = self._resolve_output(file_cfg.output_dir)
            notifiers = [FileNotifier(out)]

        if not notifiers:
            raise BriefingError("no notification channels enabled")

        receipts: list[DeliveryReceipt] = []
        for notifier in notifiers:
            receipts.append(notifier.notify(briefing))
        return BriefingDispatchResult(briefing=briefing, receipts=tuple(receipts))

    def _default_notifiers(self) -> list[Notifier]:
        channels = self._config.channels
        out: list[Notifier] = []
        if channels.file.enabled:
            out.append(FileNotifier(self._resolve_output(channels.file.output_dir)))
        if channels.webhook.enabled:
            out.append(WebhookNotifier(timeout_seconds=channels.webhook.timeout_seconds))
        if channels.email.enabled:
            out.append(EmailNotifier())
        return out

    def _resolve_output(self, output_dir: str) -> Path:
        path = Path(output_dir)
        return path if path.is_absolute() else self._repo_root / path
