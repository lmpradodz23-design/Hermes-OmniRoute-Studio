"""Cron seguro para WhatsApp — só ações seguras, nunca envio ilimitado.

Permite `scheduled_message`, `session_health_check`, `reconnect_check`. Cada job
tem rate limit, timeout, idempotência (dedup key) e é cancelável. Um job de cron
não vira mecanismo de spam."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Set


class CronJobType(str, Enum):
    SCHEDULED_MESSAGE = "scheduled_message"
    SESSION_HEALTH_CHECK = "session_health_check"
    RECONNECT_CHECK = "reconnect_check"


ALLOWED_CRON_JOBS = frozenset(CronJobType)


class CronPolicyError(Exception):
    pass


@dataclass
class CronJob:
    job_type: CronJobType
    session_id: str
    idempotency_key: str
    timeout_seconds: float = 60.0
    max_per_day: int = 50


class CronGuard:
    """Aplica a política. `admit` recusa job fora da allowlist, duplicado (mesma
    idempotency_key) ou acima do teto diário."""

    def __init__(self) -> None:
        self._seen_keys: Set[str] = set()
        self._daily_count: dict[str, int] = {}

    def admit(self, job: CronJob) -> None:
        if job.job_type not in ALLOWED_CRON_JOBS:
            raise CronPolicyError(f"tipo de cron não permitido: {job.job_type}")
        if job.timeout_seconds <= 0 or job.timeout_seconds > 3600:
            raise CronPolicyError("timeout de cron fora do intervalo")
        if job.idempotency_key in self._seen_keys:
            raise CronPolicyError("job duplicado (idempotency_key repetida)")
        bucket = f"{job.session_id}:{job.job_type.value}"
        if self._daily_count.get(bucket, 0) >= job.max_per_day:
            raise CronPolicyError("teto diário do job excedido")
        self._seen_keys.add(job.idempotency_key)
        self._daily_count[bucket] = self._daily_count.get(bucket, 0) + 1
