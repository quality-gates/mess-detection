# Normand explicitness implementation plan

## Workflow

1. Read the Principles section of the poteto-mode skill.
2. Phase A: Frame.
3. Phase B: Design the workflow.
4. Phase C: Run the loop.
5. Phase D: Keep the audit trail.
6. Phase E: Verify and hand back.

## Goal and gates

The six analyzers must agree with Normand's action and calculation distinction on a shared semantic corpus. An effectful operation is an action even when its return value is used. A fixed capture and mutation of a private fresh copy are calculations. A callback whose effects are not established is unknown.

The documentation hub does not become an analyzer. It owns the contract and the cross-language runner.

The goal is not met until each tool passes the shared corpus through its public analysis entry, its existing tests pass, and unresolved effects cannot masquerade as proven calculations. A blocked build is not a pass. A test that marks every example unknown is not sufficient.

Scope is six native implementations and one documentation repository. The baseline audit reproduced ownership, capture, copy, shared-content, and deferred-execution errors. C# and Rust builds are blocked by Docker image downloads at the start of this run. Runtime dependencies and report compatibility are constraints.

## Design alternatives

Candidate A keeps effect classification native. Each analyzer owns execution scope, storage ownership, and effect summaries. Shared tests establish the language-independent contract. The CLI keeps its existing direct-flow diagnostics and gains explicit unresolved-effect information as needed.

Candidate B adds one external cross-language classifier and invokes it from every tool. The engine could centralize classification, but this adds runtime dependencies to standalone tools and creates a second parser and rule engine. It would expose source transport and process failure concerns to native callers.

The base is candidate A. Candidate B is rejected because it violates the standalone-tool contract and duplicates parser ownership. Its useful contribution is one shared corpus rather than six independently invented definitions of purity. The design hides ownership and execution-scope analysis inside each existing flow module. It does not add a generic dependency-injection framework.

No subagent or cross-model tool is available in this harness. The candidates were evaluated sequentially by the parent. This is not independent design review.

## Ordered units

1. Add a cross-language semantic corpus and runner. Capture the unchanged implementations' failures.
2. Fix Python's parameter ownership, fixed captures, and mutable-content reads. Verify the public CLI and existing explicitness and onion suites.
3. Fix TypeScript's parameter ownership and fresh replacement handling. Verify the public CLI and explicitness suite.
4. Fix Go's deferred execution and private-copy handling. Verify the public CLI and explicitness tests.
5. Fix F#'s shared-array reads and deferred execution. Verify the public CLI and explicitness tests.
6. Fix C#'s used-result mutation and readonly mutable-content reads. Verify only in the required Docker environment.
7. Fix Rust's mutation-capability classification and trait effect exclusions. Verify only in its capped development container.
8. Evaluate unresolved-effect handling and propagation against the contract. Implement the remaining boundary or record the goal as incomplete.
9. Run the family gate and review each native diff. Report every unverified case and compatibility change.

throughput checkpoint: six native analyzer units, verified sequentially; shared fixtures and public-CLI checks come first.

## Review and delivery

Each unit ends in a reproducible before-and-after check. Repository branches are `fix/normand-explicitness`. No deployment or merge is included. Native tests must observe findings from production code. The decision trail is `docs/explicitness-decisions.tsv`.
