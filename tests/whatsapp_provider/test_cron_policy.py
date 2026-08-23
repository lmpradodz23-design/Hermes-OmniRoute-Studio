"""Testes do CronGuard — cron seguro para WhatsApp.

Prova que só tipos allowlisted entram, que idempotência barra duplicata, que o
teto diário barra spam e que timeout fora do intervalo é recusado. Um job de
cron nunca vira mecanismo de envio ilimitado.
"""

import pytest

from whatsapp_provider.cron_policy import (
    ALLOWED_CRON_JOBS,
    CronGuard,
    CronJob,
    CronJobType,
    CronPolicyError,
)


def _job(**overrides) -> CronJob:
    base = dict(
        job_type=CronJobType.SCHEDULED_MESSAGE,
        session_id="s1",
        idempotency_key="k1",
    )
    base.update(overrides)
    return CronJob(**base)


def test_allowed_job_types_are_the_three_safe_ones():
    assert ALLOWED_CRON_JOBS == frozenset(CronJobType)
    assert {
        CronJobType.SCHEDULED_MESSAGE,
        CronJobType.SESSION_HEALTH_CHECK,
        CronJobType.RECONNECT_CHECK,
    } == set(CronJobType)


@pytest.mark.parametrize("job_type", list(CronJobType))
def test_each_allowlisted_type_is_admitted(job_type):
    guard = CronGuard()
    guard.admit(_job(job_type=job_type, idempotency_key=f"k-{job_type.value}"))


def test_duplicate_idempotency_key_is_rejected():
    guard = CronGuard()
    guard.admit(_job(idempotency_key="dup"))
    with pytest.raises(CronPolicyError, match="duplicado"):
        guard.admit(_job(idempotency_key="dup"))


def test_daily_cap_is_enforced_per_session_and_type():
    guard = CronGuard()
    for i in range(3):
        guard.admit(_job(idempotency_key=f"k{i}", max_per_day=3))
    with pytest.raises(CronPolicyError, match="teto diário"):
        guard.admit(_job(idempotency_key="k3", max_per_day=3))


def test_daily_cap_is_isolated_across_types():
    """Esgotar o teto de um tipo não bloqueia outro tipo na mesma sessão."""
    guard = CronGuard()
    guard.admit(_job(job_type=CronJobType.SCHEDULED_MESSAGE, idempotency_key="a", max_per_day=1))
    # tipo diferente, mesma sessão → bucket separado, admitido
    guard.admit(_job(job_type=CronJobType.RECONNECT_CHECK, idempotency_key="b", max_per_day=1))


def test_daily_cap_is_isolated_across_sessions():
    guard = CronGuard()
    guard.admit(_job(session_id="s1", idempotency_key="a", max_per_day=1))
    guard.admit(_job(session_id="s2", idempotency_key="b", max_per_day=1))


@pytest.mark.parametrize("timeout", [0.0, -1.0, 3600.1, 100000.0])
def test_timeout_out_of_range_is_rejected(timeout):
    guard = CronGuard()
    with pytest.raises(CronPolicyError, match="timeout"):
        guard.admit(_job(timeout_seconds=timeout))


@pytest.mark.parametrize("timeout", [0.5, 60.0, 3600.0])
def test_timeout_within_range_is_accepted(timeout):
    guard = CronGuard()
    guard.admit(_job(idempotency_key=f"t{timeout}", timeout_seconds=timeout))


def test_rejected_job_does_not_consume_daily_budget():
    """Um job recusado por timeout não deve contar para o teto diário nem
    marcar a idempotency_key como usada."""
    guard = CronGuard()
    with pytest.raises(CronPolicyError):
        guard.admit(_job(idempotency_key="reuse", timeout_seconds=0.0))
    # a mesma chave deve poder ser usada num job válido depois
    guard.admit(_job(idempotency_key="reuse", timeout_seconds=60.0))
