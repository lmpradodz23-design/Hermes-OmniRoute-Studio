"""Detecção de estagnação no loop de goals — atividade não é progresso.

── Por que este arquivo existe ──────────────────────────────────────────────

O loop de goals já pausava por falha de INFRAESTRUTURA: judge inalcançável,
judge ilegível, orçamento de turnos esgotado, gate que estourou os retries.
Faltava o caso em que nada quebra e mesmo assim nada anda — o agente gasta
turno após turno, o workspace não muda um byte, e a mesma falha volta idêntica.

Esse é o modo de falha caro: parece trabalho, consome orçamento inteiro, e
termina exatamente onde começou. Detectá-lo exige MEDIR progresso, e não
perguntar ao executor se ele progrediu.

Progresso aqui tem definição operacional: o workspace mudou, OU a falha mudou
(falha diferente é informação nova), OU não houve falha. Nenhuma das três ⇒
turno queimado.
"""

import json
import time
from unittest.mock import patch

import pytest

from hermes_cli.goals import (
    DEFAULT_STALL_ESCALATION_TURNS,
    DEFAULT_STALL_STRATEGY_CHANGE_TURNS,
    STALL_DIRECTIVE_ESCALATE,
    STALL_DIRECTIVE_NONE,
    STALL_DIRECTIVE_STRATEGY_CHANGE,
    GoalManager,
    GoalState,
    classify_progress,
)

FAIL = "gate:pytest -q:1"


def _advance(state, *, fingerprint, failure, now=1000.0):
    return classify_progress(
        state, fingerprint=fingerprint, failure_signature=failure, now=now
    )


# ── A função pura ───────────────────────────────────────────────────────────


def test_first_failure_is_progress_not_stagnation():
    """A primeira falha é informação nova. Acusar estagnação nela seria acusar
    o agente de estar parado no exato momento em que ele descobriu o problema."""
    state = GoalState(goal="x")

    assert _advance(state, fingerprint="fp1", failure=FAIL) == STALL_DIRECTIVE_NONE
    assert state.no_progress_turns == 0
    assert state.same_failure_count == 1


def test_workspace_change_counts_as_progress_even_with_the_same_failure():
    """O teste continua vermelho, mas o código mudou: isso é uma tentativa
    real, não repetição. Contar como estagnação puniria quem está trabalhando."""
    state = GoalState(goal="x")
    _advance(state, fingerprint="fp1", failure=FAIL)

    assert _advance(state, fingerprint="fp2", failure=FAIL) == STALL_DIRECTIVE_NONE
    assert state.no_progress_turns == 0


def test_new_failure_counts_as_progress_even_with_an_unchanged_workspace():
    """Falha diferente = o diagnóstico andou, mesmo sem nada escrito no disco."""
    state = GoalState(goal="x")
    _advance(state, fingerprint="fp1", failure=FAIL)

    assert (
        _advance(state, fingerprint="fp1", failure="gate:pytest -q:2")
        == STALL_DIRECTIVE_NONE
    )
    assert state.same_failure_count == 1


def test_three_equivalent_attempts_demand_a_strategy_change():
    state = GoalState(goal="x")

    directives = [
        _advance(state, fingerprint="fp1", failure=FAIL)
        for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS)
    ]

    assert directives[-1] == STALL_DIRECTIVE_STRATEGY_CHANGE
    assert directives[:-1] == [STALL_DIRECTIVE_NONE] * (
        DEFAULT_STALL_STRATEGY_CHANGE_TURNS - 1
    )
    assert state.same_failure_count == DEFAULT_STALL_STRATEGY_CHANGE_TURNS


def test_sustained_no_progress_escalates_to_a_diagnostic_agent():
    state = GoalState(goal="x")
    directive = STALL_DIRECTIVE_NONE

    for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1):
        directive = _advance(state, fingerprint="fp1", failure=FAIL)

    assert directive == STALL_DIRECTIVE_ESCALATE
    assert state.no_progress_turns >= DEFAULT_STALL_ESCALATION_TURNS


def test_escalation_outranks_strategy_change():
    """Quem já passou por cinco turnos parados não precisa de mais uma
    tentativa — precisa de outro par de olhos. A diretiva mais forte vence."""
    state = GoalState(goal="x")

    for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1):
        directive = _advance(state, fingerprint="fp1", failure=FAIL)

    assert directive == STALL_DIRECTIVE_ESCALATE


def test_real_progress_resets_the_counters():
    """Estagnação é um estado, não uma dívida acumulada."""
    state = GoalState(goal="x")
    for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS):
        _advance(state, fingerprint="fp1", failure=FAIL)
    assert state.stall_directive == STALL_DIRECTIVE_STRATEGY_CHANGE

    _advance(state, fingerprint="fp2", failure=FAIL)

    assert state.no_progress_turns == 0
    assert state.same_failure_count == 1
    assert state.stall_directive == STALL_DIRECTIVE_NONE


def test_heartbeat_is_not_progress():
    """A distinção inteira do arquivo cabe neste teste: o loop rodou (heartbeat
    subiu) e não andou (last_progress_at ficou onde estava)."""
    state = GoalState(goal="x")
    _advance(state, fingerprint="fp1", failure=FAIL, now=1000.0)
    progress_marker = state.last_progress_at

    _advance(state, fingerprint="fp1", failure=FAIL, now=2000.0)

    assert state.heartbeat_at == 2000.0, "o heartbeat tem que registrar o turno"
    assert state.last_progress_at == progress_marker, (
        "um turno sem progresso mexeu em last_progress_at — a métrica que "
        "distingue atividade de progresso acabou de ser destruída"
    )


def test_no_failure_at_all_is_progress():
    state = GoalState(goal="x")
    _advance(state, fingerprint="fp1", failure=FAIL)

    assert _advance(state, fingerprint="fp1", failure="") == STALL_DIRECTIVE_NONE
    assert state.same_failure_count == 0


def test_outside_git_absence_of_measurement_never_accuses_stagnation():
    """`workspace_fingerprint()` devolve "" fora de um repositório. Sem sinal
    medido, o critério fica MAIS conservador — nunca menos."""
    state = GoalState(goal="x")

    first = _advance(state, fingerprint="", failure=FAIL)
    second = _advance(state, fingerprint="", failure="outra falha")

    assert first == STALL_DIRECTIVE_NONE
    assert second == STALL_DIRECTIVE_NONE
    assert state.no_progress_turns == 0


# ── Persistência ────────────────────────────────────────────────────────────


def test_stall_counters_survive_a_json_roundtrip():
    """O checkpoint é o que sobrevive à interrupção. Contador que não persiste
    zera na retomada e a estagnação recomeça do zero, invisível."""
    state = GoalState(goal="x")
    for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS):
        _advance(state, fingerprint="fp1", failure=FAIL, now=1234.0)

    loaded = GoalState.from_json(state.to_json())

    assert loaded.no_progress_turns == state.no_progress_turns
    assert loaded.same_failure_count == state.same_failure_count
    assert loaded.last_failure_signature == FAIL
    assert loaded.last_workspace_fingerprint == "fp1"
    assert loaded.stall_directive == STALL_DIRECTIVE_STRATEGY_CHANGE
    assert loaded.heartbeat_at == 1234.0


def test_pre_stall_state_rows_load_clean():
    """Compatibilidade: linhas de `state_meta` gravadas antes destes campos."""
    old = {"goal": "legacy", "status": "active", "turns_used": 3}

    state = GoalState.from_json(json.dumps(old))

    assert state.no_progress_turns == 0
    assert state.same_failure_count == 0
    assert state.stall_directive == STALL_DIRECTIVE_NONE
    assert state.last_progress_at == 0.0


# ── O loop real ─────────────────────────────────────────────────────────────


def _mgr(session_id, *, max_turns=50):
    mgr = GoalManager(session_id=session_id, default_max_turns=max_turns)
    mgr.set("consertar a suíte")
    return mgr


def test_judge_loop_injects_a_strategy_change_into_the_continuation_prompt():
    """Não basta detectar: o turno seguinte tem que CHEGAR diferente ao agente."""
    mgr = _mgr("stall-judge-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "ainda falta o mesmo teste", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS - 1):
            decision = mgr.evaluate_after_turn("mais do mesmo")
            assert STALL_DIRECTIVE_STRATEGY_CHANGE not in decision["continuation_prompt"]

        decision = mgr.evaluate_after_turn("mais do mesmo")

    assert decision["should_continue"] is True, "trocar de estratégia não é parar"
    assert decision["stall_directive"] == STALL_DIRECTIVE_STRATEGY_CHANGE
    assert "ESTAGNAÇÃO DETECTADA" in decision["continuation_prompt"]
    assert "NÃO repita a mesma tentativa" in decision["continuation_prompt"]
    # E a proibição de verde artificial viaja junto — é no momento da
    # frustração que remover o teste vira tentador.
    assert "remover teste" in decision["continuation_prompt"]


def test_judge_loop_pauses_for_escalation_instead_of_burning_the_budget():
    mgr = _mgr("stall-escalate-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "ainda falta o mesmo teste", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1):
            decision = mgr.evaluate_after_turn("mais do mesmo")

    assert decision["status"] == "paused"
    assert decision["should_continue"] is False
    assert decision["verdict"] == "stalled"
    assert STALL_DIRECTIVE_ESCALATE in decision["message"]
    assert STALL_DIRECTIVE_ESCALATE in mgr.state.paused_reason
    # Pausou MUITO antes do orçamento de 50 turnos — que era o ponto.
    assert mgr.state.turns_used <= DEFAULT_STALL_ESCALATION_TURNS + 2


def test_an_agent_that_keeps_changing_the_code_is_never_declared_stalled():
    """O falso positivo que importa: quem está trabalhando não pode ser
    interrompido só porque o teste ainda não passou."""
    mgr = _mgr("stall-working-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "quase lá", False, None, False),
    ):
        for i in range(DEFAULT_STALL_ESCALATION_TURNS + 3):
            with patch(
                "hermes_cli.goals.workspace_fingerprint", return_value=f"fp-{i}"
            ):
                decision = mgr.evaluate_after_turn("commit novo")

    assert decision["should_continue"] is True
    assert decision["stall_directive"] == STALL_DIRECTIVE_NONE
    assert mgr.state.no_progress_turns == 0


def test_the_per_gate_retry_guard_still_fires_first_when_it_applies():
    """Divisão de trabalho, não duplicação.

    Um gate vermelho com `max_retries` baixo já era coberto: o contador POR
    GATE pausa em 3 tentativas. A detecção de estagnação não deve atropelar
    isso — quem chega antes, decide.
    """
    mgr = _mgr("stall-gate-retry-sid")
    mgr.add_gate("pytest -q", max_retries=2)

    with patch("hermes_cli.goals.run_gate", return_value=(False, 1, "1 failed")), patch(
        "hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"
    ), patch("hermes_cli.goals.judge_goal") as judge:
        decisions = [
            mgr.evaluate_after_turn("tentei de novo")
            for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1)
        ]

    paused = next(d for d in decisions if d["status"] == "paused")

    assert "retries" in paused["message"]
    assert STALL_DIRECTIVE_ESCALATE not in paused["message"]
    judge.assert_not_called()


def test_a_gate_with_generous_retries_still_escalates_on_stagnation():
    """O buraco que o contador por gate deixa aberto.

    `max_retries` alto (ou vários gates se revezando) faz o loop rodar dezenas
    de turnos sobre uma suíte que não sai do lugar. O contador por gate está
    dentro do seu limite o tempo todo; quem enxerga que NADA andou é a medição
    de nível de missão.
    """
    mgr = _mgr("stall-gate-sid")
    mgr.add_gate("pytest -q", max_retries=99)

    with patch("hermes_cli.goals.run_gate", return_value=(False, 1, "1 failed")), patch(
        "hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"
    ), patch("hermes_cli.goals.judge_goal") as judge:
        decisions = [
            mgr.evaluate_after_turn("tentei de novo")
            for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1)
        ]

    paused = next(d for d in decisions if d["status"] == "paused")

    assert paused["verdict"] == "stalled"
    assert STALL_DIRECTIVE_ESCALATE in paused["message"]
    assert mgr.state.gates[0].attempts < 99, "o contador por gate nunca teria pausado"
    judge.assert_not_called()


def test_reaching_the_goal_clears_the_stall_state():
    """Um /goal resume depois não pode herdar estagnação de outra vida."""
    mgr = _mgr("stall-done-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "mesma coisa", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS):
            mgr.evaluate_after_turn("parado")
    assert mgr.state.same_failure_count == DEFAULT_STALL_STRATEGY_CHANGE_TURNS

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("done", "pronto", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        decision = mgr.evaluate_after_turn("terminei")

    assert decision["status"] == "done"
    assert mgr.state.no_progress_turns == 0
    assert mgr.state.same_failure_count == 0
    assert mgr.state.stall_directive == STALL_DIRECTIVE_NONE


# ── Checkpoint e retomada ───────────────────────────────────────────────────
#
# O checkpoint só vale se sobreviver à morte do processo. Estes testes trocam
# de GoalManager no meio — é o mais perto de "o executor morreu e outro subiu"
# que dá para chegar sem matar um processo de verdade: o estado tem que vir
# inteiro do `state_meta`, não da memória do objeto anterior.


def test_stall_state_survives_the_executor_dying():
    mgr = _mgr("stall-checkpoint-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "mesma falha", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_STRATEGY_CHANGE_TURNS):
            mgr.evaluate_after_turn("parado")

    # Outro processo, mesma sessão: nada do objeto anterior é reaproveitado.
    revived = GoalManager(session_id="stall-checkpoint-sid")

    assert revived.state.same_failure_count == DEFAULT_STALL_STRATEGY_CHANGE_TURNS
    assert revived.state.stall_directive == STALL_DIRECTIVE_STRATEGY_CHANGE
    assert revived.state.last_workspace_fingerprint == "fp-parado"
    assert revived.state.turns_used == DEFAULT_STALL_STRATEGY_CHANGE_TURNS, (
        "os turnos gastos voltaram a zero — o executor recomeçaria do zero, "
        "que é exatamente o que o checkpoint existe para impedir"
    )


def test_the_revived_executor_continues_counting_instead_of_restarting():
    """Retomar não é recomeçar: quem volta herda a contagem e escala na hora
    certa, não cinco turnos depois."""
    mgr = _mgr("stall-revive-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "mesma falha", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_ESCALATION_TURNS - 1):
            mgr.evaluate_after_turn("parado")

        revived = GoalManager(session_id="stall-revive-sid")
        decision = revived.evaluate_after_turn("parado")
        decision = revived.evaluate_after_turn("parado")

    assert decision["status"] == "paused"
    assert STALL_DIRECTIVE_ESCALATE in decision["message"]


def test_resume_after_escalation_grants_a_fresh_window():
    """Sem isto, /goal resume devolveria o loop já estagnado: um turno vermelho
    e ele re-pausa. O botão existiria e não funcionaria."""
    mgr = _mgr("stall-resume-sid")

    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "mesma falha", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 1):
            mgr.evaluate_after_turn("parado")
        assert mgr.state.status == "paused"

        mgr.resume()
        assert mgr.state.no_progress_turns == 0
        assert mgr.state.stall_directive == STALL_DIRECTIVE_NONE

        decision = mgr.evaluate_after_turn("parado")

    assert decision["should_continue"] is True, "resume não devolveu o loop ao trabalho"

    # Mas não é amnésia: a mesma falha idêntica volta a contar do 1 e escala
    # de novo dentro da janela nova.
    with patch(
        "hermes_cli.goals.judge_goal",
        return_value=("continue", "mesma falha", False, None, False),
    ), patch("hermes_cli.goals.workspace_fingerprint", return_value="fp-parado"):
        decisions = [
            mgr.evaluate_after_turn("parado")
            for _ in range(DEFAULT_STALL_ESCALATION_TURNS)
        ]

    paused = next(d for d in decisions if d["status"] == "paused")

    assert STALL_DIRECTIVE_ESCALATE in paused["message"]


# ── O furo que a auditoria independente encontrou ───────────────────────────
#
# Todos os testes acima patcham `workspace_fingerprint` para uma constante. Isso
# provou a LÓGICA e escondeu o BUG: em produção o fingerprint era medido DEPOIS
# de rodar os gates, então os artefatos que o próprio gate escrevia (relatório de
# cobertura, `dist/`, qualquer arquivo não ignorado) contavam como progresso do
# agente. `workspace_moved` dava True todo turno, os contadores nunca subiam, e
# o caso motivador — gate vermelho com `max_retries` alto — queimava os 50 turnos
# de orçamento inteiros.
#
# O mock removia exatamente a variável que quebrava. Estes testes usam um
# repositório git DE VERDADE, sem mock nenhum de fingerprint.

import subprocess
import textwrap


def _git_repo(tmp_path):
    """Um repositório git real, com um commit, para medir fingerprint de fato.

    Em um SUBDIRETÓRIO, e não na raiz de `tmp_path`, porque o
    `_hermetic_environment` do conftest aponta `HERMES_HOME` para
    ``tmp_path/hermes_test`` — dentro do repositório, o banco de estado do
    Hermes apareceria como arquivo não rastreado e mudaria o fingerprint a cada
    turno, exatamente o ruído que estes testes existem para detectar.
    """
    tmp_path = tmp_path / "repo"
    tmp_path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    return tmp_path


def test_a_gate_that_writes_artifacts_does_not_fake_progress(tmp_path, monkeypatch):
    """O bug: o gate escreve, o fingerprint muda, e a estagnação some.

    Sem correção, este teste roda os 12 turnos sem nunca pausar.
    """
    repo = _git_repo(tmp_path)
    monkeypatch.chdir(repo)

    runs = {"n": 0}

    def failing_gate_that_writes(gate, cwd=None):
        # Exatamente o que uma suíte real faz: falha E deixa um relatório.
        runs["n"] += 1
        (repo / f"report-{runs['n']}.xml").write_text("<testsuite/>", encoding="utf-8")

        return (False, 1, "1 failed")

    mgr = GoalManager(session_id="stall-artifacts-sid", default_max_turns=50)
    mgr.set("consertar a suíte")
    mgr.add_gate("pytest -q", max_retries=99)

    with patch("hermes_cli.goals.run_gate", side_effect=failing_gate_that_writes), patch(
        "hermes_cli.goals.judge_goal"
    ):
        decisions = [mgr.evaluate_after_turn("tentei de novo") for _ in range(12)]

    paused = [d for d in decisions if d["status"] == "paused"]

    assert paused, (
        "o gate escreveu um arquivo por execução e a estagnação nunca disparou — "
        "o fingerprint está sendo medido depois do gate de novo"
    )
    assert STALL_DIRECTIVE_ESCALATE in paused[0]["message"]
    assert runs["n"] <= DEFAULT_STALL_ESCALATION_TURNS + 2, (
        "queimou mais turnos do que devia antes de escalar"
    )


def test_real_source_changes_are_still_read_as_progress(tmp_path, monkeypatch):
    """O contrapeso: quem edita código de verdade não pode ser acusado de parar."""
    repo = _git_repo(tmp_path)
    monkeypatch.chdir(repo)

    edits = {"n": 0}

    def failing_gate(gate, cwd=None):
        return (False, 1, "1 failed")

    mgr = GoalManager(session_id="stall-realwork-sid", default_max_turns=50)
    mgr.set("consertar a suíte")
    mgr.add_gate("pytest -q", max_retries=99)

    with patch("hermes_cli.goals.run_gate", side_effect=failing_gate), patch("hermes_cli.goals.judge_goal"):
        for _ in range(DEFAULT_STALL_ESCALATION_TURNS + 3):
            edits["n"] += 1
            # O agente mexendo no FONTE entre turnos, que é trabalho de verdade.
            (repo / "src.py").write_text(f"# tentativa {edits['n']}\n", encoding="utf-8")
            decision = mgr.evaluate_after_turn("editei o código")

    assert decision["status"] == "active", "quem está trabalhando foi acusado de estagnar"
    assert mgr.state.no_progress_turns == 0


def test_the_judge_signature_survives_a_reworded_reason(tmp_path, monkeypatch):
    """`reason` é texto livre do modelo. Uma vírgula diferente zerava tudo."""
    repo = _git_repo(tmp_path)
    monkeypatch.chdir(repo)

    frases = [
        "ainda falta o mesmo teste",
        "ainda falta o mesmo teste.",
        "Ainda falta o mesmo teste",
        "o mesmo teste ainda falta",
        "falta ainda aquele teste",
        "o teste continua falhando",
        "segue faltando o teste",
    ]
    respostas = iter([("continue", f, False, None, False) for f in frases])

    mgr = GoalManager(session_id="stall-judge-text-sid", default_max_turns=50)
    mgr.set("consertar a suíte")

    with patch("hermes_cli.goals.judge_goal", side_effect=lambda *a, **k: next(respostas)):
        decisions = [mgr.evaluate_after_turn("nada mudou") for _ in range(len(frases))]

    paused = [d for d in decisions if d["status"] == "paused"]

    assert paused, (
        "o judge reescreveu a mesma ressalva sete vezes sobre um workspace "
        "intocado e o loop nunca percebeu — a assinatura voltou a ser o texto"
    )
