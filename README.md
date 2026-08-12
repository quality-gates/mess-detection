# Mess detection

Org hub for [quality-gates](https://github.com/quality-gates) mess detectors.

Mess detection scans source for maintainability problems before they calcify:
oversized functions and types, tangled dependencies, dead private code, muddy
naming, and other mess that reviews keep rediscovering.

You need mess detection to avoid **AI code slop** calcifying in the tree.
Models emit plausible structure at high volume. Review cannot re-litigate every
name, dependency edge, and method length on every PR. A local CLI can.

## Why you need it

You need mess detection to avoid AI code slop before it calcifies. Generators
optimise for “looks done” and green unit tests, not for code a human can still
change safely six months later.

AI-assisted changes often leave:

- functions and types that grew past a readable size in one session
- dependency webs no one designed on purpose
- private helpers that died after the next rewrite
- names that read fine in the prompt and wrong in the domain
- copy-pasted branches where one abstraction should live

Mess detectors read source as text or syntax. They do not import, build, or run
your project. Findings fail CI with a stable exit code so mess cannot merge
quietly. Start with the recommended low-noise ruleset for the language; add
`opinionated` when the team wants the stricter band.

## Pain points it hits

| Pain | What mess detection does |
| :--- | :--- |
| AI dumps large green diffs | Rules flag size, complexity, and coupling before merge |
| Review fatigue on style and structure | Automated findings carry stable rule names and locations |
| “We’ll clean it up later” | Gate exit `2` on findings keeps debt from landing |
| Linters pass, design still rots | Maintainability rules sit above format and type checks |
| Polyglot monorepo | One CLI shape per language; same report formats for CI |
| Thresholds differ by team | XML rulesets and `--disable` / excludes encode policy in-repo |
| Noise on generated or test trees | `--ignore-tests`, path excludes, and tuned rulesets |

## Language map

Quality-gates ships language-native CLIs. Start with the row for your stack.

| Language | Tool | Role | Repo |
| :--- | :--- | :--- | :--- |
| Python | **messpy** | Local CLI; text/syntax scan; `python` + `opinionated` rulesets; SARIF/GitHub/GitLab reports | [quality-gates/messpy](https://github.com/quality-gates/messpy) |
| Rust | **messrust** | Local CLI; parses Rust without building; `rust` + `opinionated` rulesets | [quality-gates/messrust](https://github.com/quality-gates/messrust) |
| Go | **messgo** | Local CLI on `go/ast`; idiomatic `go` ruleset; phpmd-shaped rulesets and reports | [quality-gates/messgo](https://github.com/quality-gates/messgo) |
| JavaScript / TypeScript | **messcript** | Local CLI; no project install required to scan; `typescript` / `javascript` rulesets | [quality-gates/messcript](https://github.com/quality-gates/messcript) |
| C# | **messharp** | Roslyn syntax-only scan; `csharp` + `opinionated`; Docker/`scripts/dotnet.sh` workflow | [quality-gates/messharp](https://github.com/quality-gates/messharp) |
| F# | **messfsharp** | FCS-backed scan of `.fs` / `.fsi` / `.fsx`; `fsharp` + `opinionated`; .NET tool | [quality-gates/messfsharp](https://github.com/quality-gates/messfsharp) |

Shared command shape across the family:

```text
<tool> <paths> <format> <ruleset[,ruleset...]> [options]
```

Formats commonly include `text`, `json`, `sarif`, `github`, and `gitlab`. Exit
`0` is clean, `2` means findings, `1` means tool or input failure (see each
repo for exact codes and flags).

## Start here

**Python**

```console
python -m pip install messpy
messpy src text python --ignore-tests
```

**Rust**

```console
cargo install messrust
messrust src text rust --ignore-tests
```

**Go**

```console
go install github.com/quality-gates/messgo/cmd/messgo@latest
messgo ./... text go --ignore-tests
```

**JavaScript / TypeScript** (clone until a registry package is published)

```console
git clone https://github.com/quality-gates/messcript.git
cd messcript
npm ci && npm run build
node dist/cli.js src text typescript --ignore-tests
```

**C#** (repo tooling via Docker wrappers)

```console
git clone https://github.com/quality-gates/messharp.git
cd messharp
scripts/dotnet.sh build -c Release
scripts/dotnet.sh run --project src/MessSharp -- ./src text csharp --ignore-tests
```

**F#**

```console
dotnet tool install --global messfsharp
messfsharp src text fsharp --ignore-tests
```

Add `,opinionated` to the ruleset list when you want the stricter band. Point
at a team XML ruleset when thresholds must live in the repo. Drop the tool into
CI with `github` or `gitlab` format so findings show up on the change.

## Related quality gates

Mess detection asks whether source stays maintainable. **Mutation testing**
asks whether tests would catch a real fault — including AI test slop that
passes coverage and still misses behaviour:

| Concern | Hub | Tools |
| :--- | :--- | :--- |
| Test strength | [mutation-testing](https://github.com/quality-gates/mutation-testing) | [mutago](https://github.com/quality-gates/mutago), [mutarust](https://github.com/quality-gates/mutarust), [mutaskell](https://github.com/quality-gates/mutaskell) |

Use both: mess detectors on every change; mutation scores on a cadence or on
touched packages when runtime allows.

## Maintainers

This repository is documentation only: the org map and pitch for mess
detection. Product code and releases live in the language tool repos above.

Hub contract tests:

```console
python3 tests/hub_contract_test.py
```
