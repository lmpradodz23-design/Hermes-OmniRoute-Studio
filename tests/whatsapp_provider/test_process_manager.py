"""Ownership do processo e política de restart — sem restart infinito, e crash ≠ logout."""

import pytest

from whatsapp_provider.process_manager import (
    ProcessManager,
    RestartPolicy,
    RuntimeStatus,
)


def test_only_kills_what_hermes_started():
    pm = ProcessManager()
    assert pm.can_kill() is False  # nada iniciado
    pm.on_started(pid=1234, now=1.0)
    assert pm.can_kill() is True
    pm.on_exited(0, now=2.0)
    assert pm.can_kill() is False  # já saiu


def test_crash_triggers_restart_with_backoff():
    pm = ProcessManager(RestartPolicy(base_delay=1, max_delay=60, max_restarts=5))
    pm.on_started(pid=1, now=0)
    pm.on_exited(1, now=10)  # crash
    assert pm.record.status == RuntimeStatus.CRASHED
    d1 = pm.plan_restart(now=10)
    assert d1 == 1.0  # 2^0
    # simula sucessivos crashes → backoff cresce
    delays = [d1]
    for i in range(3):
        pm.on_started(pid=2, now=20 + i)
        pm.on_exited(1, now=21 + i)
        delays.append(pm.plan_restart(now=21 + i))
    assert delays == [1.0, 2.0, 4.0, 8.0]  # exponencial


def test_restart_gives_up_after_max():
    pm = ProcessManager(RestartPolicy(base_delay=1, max_restarts=2, window_seconds=1000))
    for i in range(2):
        pm.on_started(pid=1, now=i)
        pm.on_exited(1, now=i + 0.5)
        assert pm.plan_restart(now=i + 0.5) is not None
    # terceira: estourou o teto
    pm.on_started(pid=1, now=5)
    pm.on_exited(1, now=6)
    assert pm.plan_restart(now=6) is None
    assert pm.record.status == RuntimeStatus.GIVEN_UP


def test_logout_is_not_a_crash_and_never_restarts():
    # Reiniciar após logout só geraria QR em loop.
    pm = ProcessManager()
    pm.on_started(pid=1, now=0)
    pm.on_exited(0, logged_out=True, now=5)
    assert pm.record.status == RuntimeStatus.LOGGED_OUT
    assert pm.plan_restart(now=5) is None


def test_clean_exit_does_not_restart():
    pm = ProcessManager()
    pm.on_started(pid=1, now=0)
    pm.on_exited(0, now=5)  # saída limpa (stop pedido)
    assert pm.record.status == RuntimeStatus.STOPPED
    assert pm.plan_restart(now=5) is None


def test_restart_window_resets_after_time():
    pol = RestartPolicy(base_delay=1, max_restarts=2, window_seconds=100)
    pm = ProcessManager(pol)
    pm.on_started(pid=1, now=0); pm.on_exited(1, now=1); pm.plan_restart(now=1)
    pm.on_started(pid=1, now=2); pm.on_exited(1, now=3); pm.plan_restart(now=3)
    # dentro da janela: esgotou
    pm.on_started(pid=1, now=4); pm.on_exited(1, now=5)
    assert pm.plan_restart(now=5) is None
    # muito depois: janela limpou, pode de novo
    pm.on_started(pid=1, now=500); pm.on_exited(1, now=501)
    assert pm.plan_restart(now=501) is not None
