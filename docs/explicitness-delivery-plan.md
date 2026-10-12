# Explicitness delivery plan

## Workflow

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [ ] Phase C: Run the loop.
- [ ] Complete native effect summaries and reachable-storage ownership in six isolated repository lanes.
- [ ] Verify the full shared corpus and native regressions for each lane.
- [ ] Add expanded adversarial cases and an executable CI conformance gate.
- [ ] Obtain fresh independent reviews of exact candidate commits.
- [ ] Phase D: Keep the audit trail.
- [ ] Phase E: Verify and hand back.
- [ ] Open one PR per repository and wait for green CI at each current head.
- [ ] Merge reviewed PRs individually and verify the resulting default-branch commits.

## Predicate

The result is complete only when all six analyzers classify the agreed supported cases correctly, report unresolved effects rather than imply purity, and pass their native suites. Each of the seven repositories must have a merged PR with green CI at its final reviewed head. The documentation repository owns the semantic contract and executable corpus. A native suite alone and a quiet report are not proof of functional purity.

The classification is actions, calculations established within the documented analyzed subset, and unknown effects. Arbitrary runtime behavior cannot be certified by a syntax-only analyzer. Dynamic dispatch, external dependencies, unmodeled effects, and unresolved callbacks must retain uncertainty. Necessary actions are legitimate. The rules do not define boolean parameters, static methods, or branches as violations of functional programming.

## Data shape and design

Each native analyzer owns a callable summary with parameter-relative reads and writes, ambient effects, unresolved operations, returned storage and callable provenance, and completeness information. Call transfer substitutes actual argument storage and callable identities. It does not copy diagnostic sets. Deferred bodies belong to separate execution owners. The report adapter preserves direct-flow diagnostics and adds `UnknownEffect`.

The solver uses finite callable and effect identities, monotone joins, stable equality, and bounded paths or explicit widening. Recursive provenance cannot grow indefinitely. Private argument substitution can remove a parameter mutation at a caller boundary. It cannot erase ambient or unrelated unresolved effects.

Storage facts distinguish the outer allocation from its reachable contents. A fresh shallow copy has private outer storage but can retain caller-owned elements. Aliases and rebinding change storage facts at the operation site. Branches join possible origins rather than erase them.

The chosen design extends native semantic summaries. The alternative is one normalized cross-language intermediate representation and common solver. An embedded common solver can preserve standalone executables. It still requires a sound translation of each language's storage and execution facts. The native design avoids that new translation contract and shared packaging machinery. The shared corpus supplies a common contract without owning parser internals.

The independent design review returned `ISSUES`. It recommended the native shape only after strengthening calculation assumptions, effect substitution, reachable ownership, execution ownership, finite joins, and attributed acceptance. This design verdict is not candidate-commit or merge approval.

## Execution and review

The prior run used the sequential fallback because no dedicated subagent tool was registered. Local Codex and Claude CLIs are now observed on PATH. Availability and credentials must be tested before these processes count as workers or independent reviewers. Local processes need one repository lane each. Shared corpus edits and forge operations remain parent-owned. Workers must not commit, push, merge, change CI expectations, or modify another lane.

The CI gate must execute the native CLI. No fixture-specific classification, blanket unknown result, disabled regression, weakened corpus, or green-only documentation change satisfies the predicate. Preserve red observations and correct invalid expectations in separate changes.

Throughput checkpoint. Six analyzer lanes and one documentation lane. Build and mutation-site correctness precede effect propagation. Review begins only on stable candidate commits. PRs land only after both correctness evidence and current-head CI are verified.

## Shipping limits

Normal branch pushes, PR creation, and requested merges are authorized. Force pushes to shared branches, deployment, and data deletion still require a pause. Do not bypass branch protection or fabricate independent review. A failed independent-review process is a blocker, not an approval.

The append-only decision trail remains `docs/explicitness-decisions.tsv`.
