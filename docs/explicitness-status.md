# Explicitness implementation status

## Historical checkpoint

This document records the earlier direct-flow checkpoint. Its source hashes, native-suite results, and 33 of 55 case result are historical. The corpus and implementations have since changed. They are not current acceptance evidence. The delivery work is recorded in `docs/explicitness-delivery-plan.md`.

At this checkpoint, the reliability goal was not met. Six native suites passed, but every analyzer failed semantic gates. No repository could treat a clean explicitness report as calculation proof.

The branches are `fix/normand-explicitness`. The changes are uncommitted. No PR, merge, or deployment was made. The documentation hub owns the corpus and runner. It is not an analyzer.

## Verified changes

| Analyzer | Native suite | Shared cases | Changes |
| --- | --- | --- | --- |
| Python | 377 run, 1 skipped | 7/11 | Direct aliases, execution-order rebinding, private outer copies, uppercase mutable data, and fixed captures. Captured content reads remain inputs. |
| TypeScript | 386 passed | 5/9 | Direct aliases and fresh outer replacements. A conditional copy does not establish private storage. |
| Go | All packages passed | 6/10 | Direct aliases, private outer copies, and separate anonymous callable reporting. |
| F# | 227 passed | 7/11 | Array reads with observed writes, direct aliases, and separate lambda reporting. A fixed array with no observed writes stays quiet. |
| C# | 730 passed in Docker | 4/7 | Returned collection mutations, aliases, private outer copies, and readonly collections with observed writes. |
| Rust | 788 passed in capped Docker | 4/7 | Mutable-reference capability no longer fabricates a write. Actual borrowed writes and aliases are tracked. Trait implementations retain their effects. |

Go's first full run failed because a test expected a `/var` temporary path while the report used its canonical `/private/var` path. The unchanged commit reproduced that failure. All packages passed with a canonical `TMPDIR`. No path-handling code was changed.

Rust's Clippy command completed with warnings. Its formatting check failed on existing formatting. No repository-wide formatting change was made. The temporary Rust container and its development image were removed. Build output used container tmpfs mounts, not the checkout.

## Open correctness gates

1. Known effects do not propagate to callers in plain explicitness. The Python, TypeScript, Go, and F# `spread` cases fail. C# and Rust also need propagation coverage.
2. All six tools miss injected callback effects and opaque external calls. They need an explicit unknown result and effect-summary propagation. Passing a callback as an argument does not establish that it is pure.
3. All six tools miss mutations of shared elements inside fresh shallow copies. Ownership needs to distinguish outer storage from reachable storage. Making a new container is not proof that its elements are private.
4. Receiver policy and unresolved language features still prevent a complete classifier contract. These need separate semantic summaries rather than stronger style rules.

The first six implementation units address direct-flow defects. They are not the completed classifier feature. Do not promote them as FP certification.

## Principles applied

- Foundational Thinking selected native ownership and execution-scope facts before report changes.
- Laziness Protocol kept the native analyzers instead of adding an external parser and runtime.
- Model the Domain organized the acceptance cases and storage-ownership observations as structured records.
- Build the Lever produced the reusable cross-language CLI runner.
- Fix Root Causes replaced whole-function rebinding guesses with mutation-site ownership.
- Sequence Work into Verifiable Units required each native unit to pass its CLI checks and tests before the next unit.
- Test Behavior, Not Implementation required literal findings from public CLI calls.
- Prove It Works kept the failed family gate visible instead of treating green native suites as completion.
- Never Block on the Human allowed reversible branch and fixture work to proceed without another approval request.

## Evidence and replay

The durable observations are `tests/explicitness-results.json`. They include actual CLI output, failed expectations, base commits, native-suite results, and hashes of the changed source files. The acceptance inputs are `tests/explicitness_cases.json`. The decision trail is `docs/explicitness-decisions.tsv`.

Run the corpus against a built native CLI:

```console
python3 tests/explicitness_conformance.py --language go --command '/absolute/path/to/messgo' --output /tmp/go-explicitness.json
```

The current runner sends a fixture path, `json`, and `explicitness`. Use `--cases` for a comma-separated selection. The default runs the entire language corpus. A nonzero runner exit means that a semantic gate failed.

Python must call the entry point, not merely import `messpy.cli`:

```console
python3 tests/explicitness_conformance.py --language python --command "env PYTHONPATH=/absolute/path/to/messpy/src python3 -c 'from messpy.cli import main; main()'"
```

Use Docker adapters for C# and Rust. Their repository instructions still apply. The working-session logs and adapter scripts are under `/tmp/mess-normand-goal`. Rust replay requires a new capped development container because the verification container was removed.
