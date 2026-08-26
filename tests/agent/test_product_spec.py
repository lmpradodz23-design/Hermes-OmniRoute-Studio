"""Tests for the structured ProductSpec (agent/product_spec.py)."""

from __future__ import annotations

import pytest

from agent.product_spec import Feature, ProductSpec


def _spec(**kw) -> ProductSpec:
    base = dict(
        name="Clinic SaaS",
        platforms=("web",),
        acceptance_criteria=("a user can book an appointment end to end",),
        features=(
            Feature("auth", "Authentication", "critical"),
            Feature("booking", "Booking", "high", depends_on=("auth",)),
        ),
    )
    base.update(kw)
    return ProductSpec(**base)


def test_valid_spec():
    assert _spec().validate() == []
    assert _spec().is_valid


def test_missing_required_fields():
    assert "name is required" in ProductSpec(name="  ").validate()
    assert any("acceptance" in i for i in ProductSpec(name="x", platforms=("web",)).validate())
    assert any("platform" in i for i in ProductSpec(name="x", acceptance_criteria=("c",)).validate())


def test_duplicate_feature_ids():
    spec = _spec(features=(Feature("a", "A"), Feature("a", "A2")))
    assert any("duplicate feature ids" in i for i in spec.validate())


def test_unknown_dependency():
    spec = _spec(features=(Feature("a", "A", depends_on=("ghost",)),))
    assert any("unknown feature 'ghost'" in i for i in spec.validate())


def test_invalid_priority():
    spec = _spec(features=(Feature("a", "A", priority="urgent"),))
    assert any("invalid priority" in i for i in spec.validate())


def test_roundtrip_to_dict_from_mapping():
    spec = _spec(
        roles=("admin", "patient"),
        integrations=("stripe",),
        assumptions=("DECISAO ASSUMIDA: Postgres — best-practice default",),
    )
    again = ProductSpec.from_mapping(spec.to_dict())
    assert again == spec


def test_to_mission_dag_shape():
    spec = _spec()
    dag = spec.to_mission_dag()
    assert "auth" in dag and "booking" in dag
    assert "__qa__" in dag and "__release__" in dag
    # QA waits on every feature; release waits on QA.
    assert set(dag.node("__qa__").parents) == {"auth", "booking"}
    assert dag.node("__release__").parents == ("__qa__",)
    # release is the terminal of the critical path
    assert dag.critical_path().nodes[-1] == "__release__"
    # only auth is dispatchable initially (booking depends on auth)
    assert dag.ready_nodes() == ("auth",)


def test_to_mission_dag_rejects_invalid_spec():
    with pytest.raises(ValueError):
        ProductSpec(name="").to_mission_dag()
