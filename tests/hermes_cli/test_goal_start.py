"""`start_goal` — o portão único de revisão de spec.

Este arquivo existe porque a decisão "este objetivo pode começar a rodar
sozinho agora?" estava duplicada em `gateway/slash_commands.py` e em
`hermes_cli/cli_commands_mixin.py`. As duas cópias concordavam por
coincidência, não por construção, e a UI do desktop está prestes a ser o
terceiro consumidor (o toggle "Spec" de `audit/HERMES_DESIGN_SYSTEM.md` §3.3).

O que estes testes travam:

  1. um contrato rascunhado NUNCA começa a rodar sem revisão humana;
  2. se a pausa não persistir, o objetivo é APAGADO — nunca deixado ativo;
  3. um objetivo livre, sem contrato, continua começando na hora, como sempre.
"""

import pytest

from hermes_cli.goals import (
    GoalContract,
    GoalPauseError,
    SPEC_REVIEW_PAUSE_REASON,
    start_goal,
)


class FakeState:
    def __init__(self, goal, contract=None, status="active"):
        self.goal = goal
        self.contract = contract
        self.status = status
        self.max_turns = 20
        self.paused_reason = None

    def has_contract(self):
        return self.contract is not None and not self.contract.is_empty()


class FakeManager:
    """Um GoalManager só com o que `start_goal` toca.

    `pause_behaviour` é o ponto do teste: os modos abaixo são exatamente as
    três formas de a pausa falhar em produção — devolver `None`, devolver um
    estado que não está pausado, e levantar.
    """

    def __init__(self, *, pause_behaviour="ok", set_raises=None):
        self.pause_behaviour = pause_behaviour
        self.set_raises = set_raises
        self.state = None
        self.cleared = False
        self.pause_reasons = []

    def set(self, goal, *, contract=None, max_turns=None):
        if self.set_raises:
            raise ValueError(self.set_raises)
        self.state = FakeState(goal, contract)
        return self.state

    def pause(self, reason="user-paused"):
        self.pause_reasons.append(reason)
        if self.pause_behaviour == "raises":
            raise RuntimeError("disk full")
        if self.pause_behaviour == "returns_none":
            return None
        if self.pause_behaviour == "stays_active":
            return self.state  # status continua "active"
        self.state.status = "paused"
        self.state.paused_reason = reason
        return self.state

    def clear(self):
        self.cleared = True
        self.state = None


def contract():
    return GoalContract(
        outcome="a suíte passa",
        verification="pytest -q",
        constraints="não tocar em migrations",
        boundaries="apenas tests/",
        stop_when="exit 0",
    )


# ── o portão fecha ──────────────────────────────────────────────────────────


def test_drafted_contract_is_paused_and_does_not_kick_off():
    mgr = FakeManager()

    outcome = start_goal(mgr, "arrumar a suíte", contract=contract(), require_spec_review=True, drafted=True)

    assert outcome.paused_for_review is True
    assert outcome.should_kick_off is False, "um plano rascunhado nunca começa sozinho"
    assert mgr.pause_reasons == [SPEC_REVIEW_PAUSE_REASON]
    assert mgr.cleared is False
    assert outcome.contract_block and "pytest -q" in outcome.contract_block


def test_review_gate_off_starts_immediately_even_with_contract():
    # `/goal outcome: … verify: …` digitado à mão é o próprio usuário escrevendo
    # o contrato. Não há nada para revisar — ele acabou de escrever.
    mgr = FakeManager()

    outcome = start_goal(mgr, "arrumar a suíte", contract=contract(), require_spec_review=False)

    assert outcome.paused_for_review is False
    assert outcome.should_kick_off is True
    assert mgr.pause_reasons == []


def test_free_form_goal_starts_immediately():
    mgr = FakeManager()

    outcome = start_goal(mgr, "explorar o repositório", require_spec_review=True)

    assert outcome.paused_for_review is False
    assert outcome.should_kick_off is True, "sem contrato não há spec para revisar"
    assert mgr.pause_reasons == []


# ── a falha de pausa apaga o objetivo ───────────────────────────────────────


@pytest.mark.parametrize("behaviour", ["raises", "returns_none", "stays_active"])
def test_pause_failure_clears_the_goal(behaviour):
    """Se a pausa não persiste, o objetivo fica ATIVO — e um objetivo ativo é
    exatamente o que dispara trabalho autônomo. Seguir em frente seria executar
    sem revisão no caminho que existe para exigir revisão."""
    mgr = FakeManager(pause_behaviour=behaviour)

    outcome = start_goal(mgr, "arrumar a suíte", contract=contract(), require_spec_review=True, drafted=True)

    assert outcome.cleared_after_pause_failure is True
    assert outcome.paused_for_review is False
    assert outcome.should_kick_off is False, "nunca rodar depois de uma pausa que falhou"
    assert mgr.cleared is True, "o objetivo tem que ser apagado, não deixado ativo"
    assert outcome.pause_error


def test_clear_failing_after_pause_failure_still_refuses_to_run():
    """O pior caso: a pausa falha E o clear falha. Ainda assim não roda."""

    class ClearAlsoFails(FakeManager):
        def clear(self):
            raise RuntimeError("db locked")

    mgr = ClearAlsoFails(pause_behaviour="raises")

    outcome = start_goal(mgr, "arrumar a suíte", contract=contract(), require_spec_review=True, drafted=True)

    assert outcome.cleared_after_pause_failure is True
    assert outcome.should_kick_off is False


# ── validação e rascunho indisponível ───────────────────────────────────────


def test_invalid_goal_reports_error_and_starts_nothing():
    mgr = FakeManager(set_raises="goal text is empty")

    outcome = start_goal(mgr, "", require_spec_review=True)

    assert outcome.error == "goal text is empty"
    assert outcome.state is None
    assert outcome.should_kick_off is False


def test_draft_unavailable_is_reported_and_still_runs():
    # O modelo auxiliar não produziu contrato. Cai para objetivo livre — que é
    # o comportamento de antes — mas quem chama precisa poder dizer isso.
    mgr = FakeManager()

    outcome = start_goal(mgr, "arrumar a suíte", contract=None, require_spec_review=True, drafted=True)

    assert outcome.draft_unavailable is True
    assert outcome.should_kick_off is True
    assert outcome.contract_block is None


def test_empty_contract_is_not_a_contract():
    mgr = FakeManager()

    outcome = start_goal(mgr, "arrumar a suíte", contract=GoalContract(), require_spec_review=True, drafted=True)

    assert outcome.paused_for_review is False
    assert outcome.should_kick_off is True


def test_pause_error_type_is_the_documented_one():
    assert issubclass(GoalPauseError, RuntimeError)
