# Spec-Driven Delivery

Use this gate for new products, cross-cutting features, migrations, public API changes, authentication or authorization work, and any task whose acceptance criteria are not obvious from one sentence. Skip it for a narrow correction with a demonstrated cause and a small, reversible diff.

## Spec artifact

Write one versioned Markdown artifact under `.hermes/specs/<task-slug>.md` when the repository allows local project metadata. Otherwise keep the contract in Goal state. Include:

1. user outcome and measurable acceptance criteria;
2. current-system evidence and affected boundaries;
3. functional and non-functional requirements;
4. non-goals and preserved behavior;
5. architecture, data contracts, trust boundaries, and failure modes;
6. ordered implementation slices with file ownership;
7. unit, integration, E2E, security, accessibility, and performance gates;
8. migration, rollback, release, and observability plan;
9. open decisions that materially change the result.

Use Mermaid only when a flow, topology, state machine, data relationship, or multi-agent dependency becomes clearer than prose. A diagram is explanatory evidence, not permission to invent a component.

## Goal lifecycle

- `/goal draft <outcome>` produces the Goal Contract and pauses with reason `awaiting-spec-review`.
- Inspect and revise the contract or spec before any material implementation.
- `/goal resume` begins the autonomous build.
- The goal can stop only when its verification conditions and deterministic gates pass, or when it reports a real blocker.
- A turn limit is a safety backstop, not evidence of completion.

Do not auto-publish, auto-deploy, auto-commit, or push as a side effect of approving the spec. Those are separate release actions.
