# Functional explicitness contract

## Meaning

Eric Normand defines an action by dependence on when or how often the operation runs. A calculation transforms explicit inputs into outputs without that dependence. Actions are necessary parts of software. These rules identify effects, not bad programmers or forbidden operations.

The analyzers classify source within a documented subset. They do not execute the program or certify arbitrary runtime behavior. Each native tool describes its supported calls, storage analysis, dispatch resolution, and unknown boundaries.

## Effect summaries

Each callable owns parameter-relative reads and writes, ambient effects, unresolved operations, returned storage and callable provenance, and completeness information. A summary is not a copied set of diagnostic messages.

| Evidence | Classification |
| --- | --- |
| A recognized ambient read or externally visible mutation | Action |
| An unresolved effect, without a recognized action | Unknown |
| Both a recognized action and an unresolved effect | Action with retained uncertainty |
| No effect after complete analysis of a supported callable | Calculation within that supported subset |

`ImplicitInput` and `ImplicitOutput` report recognized effect evidence. `UnknownEffect` reports unresolved operations. Strict receiver rules describe additional policy. Receiver exemptions must not be interpreted as evidence that ignored state is pure.

A clean report after rule filtering, suppression, a parse error, or an unsupported analysis path is not a calculation verdict. The full explicitness ruleset and its documented assumptions define the classification. Arithmetic and known standard-library calculations remain useful positive classifications. Blanket unknown reporting does not satisfy the contract.

Analysis fails closed. A construct outside a native analyzer's documented subset must produce `UnknownEffect` on the callable that owns it. An analyzer must never skip such a construct and leave its owner without findings. A missing finding therefore claims complete analysis of that owner within the subset.

Storage reached through a parameter is explicit input. Reading it, including its length or its elements, is not an effect. `ImplicitInput` is reading ambient state, or reading captured or module-level storage that another operation can change. Writing storage that a caller can observe is `ImplicitOutput`, whether the caller reaches it through an argument or through shared storage. Writing without observing the contents is `ImplicitOutput` only. One callable can have both effects. The binding assumption is that no concurrent writer mutates argument storage during a call.

Each finding has one effect line. For a direct effect, it is the line of the effect site. For a transferred effect, it is the line of the call, iteration, await, run, force, `defer`, `go`, or scheduling site that transfers it. When an owner has several sites of one effect kind, the designated line is the first such site in source order. The fixtures put one statement on each line, so the site is unambiguous.

A branch guarded by a literal `false`, or the language's equivalent literal constant, does not run, and its effects are not reported. Pruning applies only to literal constants. An evaluated constant expression is not pruned.

## Calls and execution owners

A resolved call substitutes actual storage origins and callable identities into its callee's summary. Ambient effects transfer to the caller. A parameter mutation transfers when the actual storage is externally shared. The same mutation can remain private when the actual argument is a fresh allocation. A known calculation supplied as a callback resolves a generic helper's parameter-relative uncertainty. A known effectful function supplied as a callback transfers its effect to the caller at the call line.

Each analyzer defines finite callable and effect identities, monotone joins, stable equality, and bounded storage paths or explicit widening. Recursive propagation must not grow diagnostic provenance strings at each step. Analysis termination does not prove termination of the analyzed program.

An injected callback or an external function is unknown unless analysis establishes its effects. Passing an effectful function explicitly does not make its invocation a calculation. Unknown effects also propagate to callers.

A factory that returns an effectful callback does not execute that callback. The callback owns the deferred effect. An immediate invocation carries the callback's effect to the caller that invokes it. A file-wide report can therefore contain an action callback while its factory is a calculation.

## Owners

A named callable is its own owner. Methods, nested functions and same-named callables in different scopes are qualified by their enclosing scopes, for example `A.Run` and `B.Run`.

An anonymous body is its own owner and has one of these names:

| Owner | Body |
| --- | --- |
| `<lambda>` | A lambda, closure, arrow function, function literal, or delegate |
| `<genexpr>` | A Python generator expression |
| `<seq>` | An F# `seq { }` expression |
| `<async>` | An F# `async { }` expression, or a Rust `async { }` block |
| `<task>` | Reserved for an F# `task { }` expression outside any callable; inside a callable a hot task belongs to that callable |
| `<lazy>` | An F# `lazy (...)` expression, or the factory of a C# `Lazy<T>` |
| `<module>` | Load-time code of the fixture file |

`<module>` owns top-level statements and static or type initializers that run when the file loads. These are the Python module body, F# top-level `do` and effectful `let` bindings, Go package `var` initializers and `init`, and C# static field initializers and static constructors. Rust has no load-time code. A fixture-local import is effect-free unless the imported module has a `<module>` effect.

A native report may spell an owner with extra qualifiers. The runner normalizes a reported owner before it compares it:

- `::` becomes `.`, and Go's `(*T).M` becomes `T.M`.
- `<locals>` is dropped anywhere, and a leading `crate`, `self`, `super` or fixture file stem is dropped.
- A positional suffix inside angle brackets, such as `<lambda@4>`, is dropped.
- Go and C# reports with separate `class` and `method` fields combine them before matching.

An exact match with a declared owner wins. Otherwise the declared name must be a tail of the reported name, and every extra leading qualifier must be listed in the case's `scopes` or be a segment of a declared owner. A record whose owner matches no declared owner, or matches two equally specific ones, fails.

## Execution lifecycle

Each construct below has a stated owner and timing. The required precision table says which ones the acceptance gate requires a language to model. An unsupported construct still produces `UnknownEffect` on its execution owner; that answer fails a case that requires precision.

- **Named generators, iterators and cold async functions.** Python functions with `yield` or `async def`, TypeScript `function*`, C# `yield return` methods, Go range-over-func iterators, and Rust `async fn` own their bodies and report their body effects. A caller that only creates the generator, iterator or coroutine is quiet. The caller that iterates, awaits, runs or polls it gets the transferred effect at that line.
- **Anonymous deferred bodies.** A Python generator expression, an F# `seq { }`, `async { }` or `lazy (...)` expression, a C# `Lazy<T>` factory, a Rust `async { }` block, and a closure own their own bodies. A definer that only builds the value is quiet. The caller that forces it gets the transferred effect at the forcing line, for example iteration, `Async.RunSynchronously`, `.Force()`, `.Value`, `.await` or `block_on`. A lambda passed to a lazy combinator such as `map` or `Select` owns its own effects.
- **Hot async.** TypeScript async functions and C# async methods start running at the call; an F# `task { }` starts when the task expression is evaluated. Every effect in a hot body, before and after its first await, transfers to the caller at the call line, because the continuation runs whether or not the caller awaits. A named async callable or async lambda owns its body. Constructing an async lambda does not invoke it. A hot F# task body inside a callable belongs to that callable, and that callable's callers get the transfer at their call line.
- **Cold async.** Python coroutines, F# `async { }` and Rust futures do nothing until awaited, run or polled. Their effects transfer at the await, run or poll line.
- **Definition-time evaluation.** Python default arguments, decorators and class bodies run when the enclosing definition runs. TypeScript class static initializers run when their class definition runs. The enclosing callable, or `<module>` at top level, owns these effects. TypeScript default parameters run at call time, so the function that declares them owns their effects.
- **Go `defer`.** A deferred call runs within the enclosing invocation, before that invocation returns. The enclosing function owns the deferred callee's transferred effects at the `defer` line. A named callee owns its body; a function literal owns its body as `<lambda>`. Capture origins are substituted when transferring the literal's effects: a write to a result local to the enclosing invocation can remain private there, while the lambda's capture-relative summary records its read and write.
- **Scheduling.** A Go `go f(x)` statement attributes `f`'s effects to the scheduling function at the `go` line. A scheduled function literal also owns its body as `<lambda>`. A library scheduler, such as a timer, a thread pool, or `Task.Run`, is an ordinary call. It transfers effects when the library's semantics are documented. Otherwise it is `UnknownEffect`.

## Required precision

All languages require precise ordinary scalar arithmetic and literal control flow, parameter reads, shared and private storage writes, aliases and shallow copies, capture origins, return provenance, known same-file calls and callbacks, recursive propagation, and load-time ownership where applicable. These requirements apply under the value and binding assumptions below. The table lists the additional lifecycle constructs and trusted library bindings exercised by the corpus. `UnknownEffect` does not satisfy these precise cases. For constructs outside this required subset, `UnknownEffect` on the execution owner is accepted.

| Language | Required lifecycle and binding behavior | Trusted standard operations |
| --- | --- | --- |
| Python | Named generators, generator expressions, iteration and `sum`; cold `async def`, coroutine creation and `await`; deferred and immediately invoked lambdas; defaults, decorators and class-body evaluation | Built-in `input`, `print`, `len`, `list`, `sum`; ordinary list reads, indexing, copying and `append` |
| TypeScript | `function*`, generator creation and iteration; hot async functions and arrows, invocation and `await`; deferred arrows; default parameters and class static evaluation | `console.log`, `Date.now`, `Promise.resolve`; ordinary array reads, indexing, spread, `slice` and `push` |
| Go | Go 1.23 range-over-func construction and iteration; function literals, `defer` and `go`; value and pointer receiver methods; package initializers and `init` | Built-in `len`, `max`, `append`, `copy`, `println`; `fmt.Println`, `os.Getenv`, `slices.Clone`, `slices.Sort` |
| F# | Anonymous `seq`, cold `async`, hot `task` and `lazy` bodies; iteration, `Async.RunSynchronously` and `Force`; lambdas and top-level evaluation; mutable module and record storage | `printfn`, `System.Console.Read`, `System.Console.ReadLine`; `Array.copy`, `Array.set`, `Seq.map`, `Seq.sum`, `Seq.toList`; ordinary array indexing and list construction |
| C# | Iterator construction and `foreach`; hot async methods, invocation and `await`; delegates and local functions; `Lazy<T>` construction and `Value`; static initialization; direct getter and setter body summaries | `Console.Read`, `Console.WriteLine`; ordinary arrays and `Clone`; `List<T>` construction, reads, `Add`, `Insert`, `Remove`; LINQ `Select` with deferred callback transfer |
| Rust | Closures and iterator combinators; cold `async fn`, future creation and `.await`; `&mut self` methods; local trusted macro identity | `std::env::var_os`; the trusted macros below; ordinary `Vec`/slice reads, indexing, `new`, `from`, `clone`, `to_vec`, `push`, `extend_from_slice`, `iter`, `map`, `collect`; `RefCell` creation and borrows; atomic `load` and `fetch_add` |

These constructs answer `UnknownEffect` on their owner unless a native documents a precise model of them:

- Go method values, interface dispatch and channels.
- Rust `Drop`, `Deref`, operator overloads, `dyn` dispatch and generic `Fn` parameters. For `Drop`, the unknown effect belongs to the function that binds the value, at the binding line.
- C# property dispatch, operators and events. A declared accessor's own body has an ordinary summary; opaque dispatch is a separate boundary.
- F# active patterns.

Each language has at least one case that asserts `UnknownEffect` for such a construct. Go value-receiver and pointer-receiver methods and Rust `&mut self` methods have precise cases.

## Macro boundary

A Rust macro invocation is an `UnknownEffect` boundary unless it is in this closed trusted set:

| Macro | Effect |
| --- | --- |
| `println!`, `print!`, `eprintln!`, `eprint!` | Output |
| `format!` | A calculation that builds a fresh `String` |
| `vec!` | A fresh allocation |

The arguments of a trusted macro are analysed as ordinary expressions, so an effect inside them belongs to the enclosing owner. Every other macro, including other standard-library macros and an external crate's macro, is `UnknownEffect`. A local `macro_rules!` definition with a standard-library name is a different macro, and invoking it is `UnknownEffect`. A separate case would have to define expanded behavior before an analyzer may expand local macros.

## Storage ownership

An argument can refer to caller-owned storage. A local alias retains that origin. A later rebinding does not erase a mutation that happened before the rebinding.

A fresh allocation has private outer storage. Mutation of that outer storage can be part of a calculation. A shallow copy can retain references to caller-owned elements. Mutation of those elements is externally visible and remains an action.

A branch that sometimes makes a copy does not establish private storage on every path. Ownership joins possible origins at the mutation site. A mutable reference permits a write but does not prove that a write occurs.

Readonly bindings and uppercase names do not freeze mutable contents. A read of storage that another operation can change retains its timing dependence. No observed write establishes immutability only under a documented closed-world assumption and an established nonescaping origin. Unknown alias creation and escaped allocations retain uncertainty. A closure that only reads a captured private container does not make that container escape. A private captured container with no writes and no escaping data alias does not acquire timing dependence.

Branches and loops join origins at each operation site. Return summaries preserve argument aliases and fresh allocation provenance. Outer allocation privacy does not erase shared reachable origins.

## Value and binding assumptions

Positive examples restrict numeric operands to exact native numeric values. Container examples use ordinary built-in scalar containers or plain records. They exclude custom iteration, conversion, getters, operator overloads, reflection, and monkey-patching. Standard-library bindings retain their documented semantics. Captured values have no unanalysed mutation or escaping alias. No concurrent writer mutates argument storage during a call. Go fixtures assume Go 1.23 or later, which has range-over-func iterators.

These restrictions are preconditions of the examples. Type annotations alone do not establish them at runtime. Native documentation must state its corresponding restrictions and analysis boundary. An empty diagnostic set establishes no universal arbitrary-runtime purity claim.

## Shared acceptance cases

`tests/explicitness_cases.json` records one case per language and identifier. Each case has these fields:

- `source`, the fixture text.
- `semantic`, which explains the expectation.
- `binding_assumptions` and `value_assumptions`.
- `exit`, the expected CLI exit status: 0 for a calculation-only file and 2 for a file with any effect.
- `outcomes`, which maps each effectful owner to its effect kinds and one designated effect line for each kind.
- `quiet_owners`, which lists every other owner in the fixture.

Optional fields:

- `scopes` lists the class, module, package, impl type or namespace names that a native may print as qualifiers.
- `twin_of` links an action twin to the calculation case it mirrors.
- `variant_of` links an equivalent-syntax variant to its base case.
- `contrasts` maps the name of a wrong model of the semantics to the outcomes that model would report. `eager` is an analyzer that runs a deferred body at its creation. `known_argument_clean` is one that treats every known callback argument as clean. Runner tests check that these models fail.

Expectations come from Normand's definitions and this contract. They never come from native output.

Fixtures put one statement on each line. Bodies of effectful owners start on the line after their declaration, so no outcome sits on its owner's declaration line. A Python lambda one-liner is the only exception, and its case says so. Go fixtures are gofmt-clean, and the hub gate checks this.

The world of owners is closed. A native record fails its case when:

- its owner matches no declared owner, or matches more than one;
- its owner is a quiet owner;
- its effect kind is not declared for its owner;
- its line is not the designated effect line;
- its path does not resolve to the fixture.

Every declared owner and kind must appear in the native report at its designated line. Duplicate findings, processing errors, missing owner metadata, and malformed records fail the case. A malformed report never ends the run. Merely mentioning a caller in a message cannot prove propagation.

A calculation passes only when its action twin passed in the same run. The twin has the same shape and adds exactly one effect: either one effectful library call and no other new library call, or a write or read of the storage under test. C# twins use `Console.Read()` and Rust twins use `std::env::var_os`. Every twin has at least one outcome on a line without a direct I/O token, so a detector that only scans for I/O names fails it. A detector that reports nothing fails every calculation pair. A calculation verdict remains a claim of complete analysis under the fail-closed rule above.

`tests/explicitness_conformance.py` runs the native CLI as `CLI FIXTURE json explicitness --strict`. Under `--strict`, a source suppression does not hide a finding. Each language whose CLI supports suppression has a `suppression_marker` case, and that case still expects the suppressed finding. Go has no suppression mechanism.

Each fixture gets a random file name and a random directory for each run. Only the language suffix stays fixed. Native paths are compared with the full fixture path. A containerized CLI declares a prefix mapping with `--path-map CONTAINER=HOST`. C# uses `/src` and Rust uses `/workspace`.

The runner exits 0 when every selected case passes, 1 when any case fails, and 2 for a usage or corpus error. It writes its output file, marked incomplete, before the first case, and rewrites it after each case. The final file records that the run completed. Native output that is not UTF-8, a NUL or undecodable path, or a report that cannot be judged fails that case only. The output file is ASCII JSON.

## Conformance workflow

A native repository calls `.github/workflows/explicitness.yml` with its language and a `contract_ref`, which must be a full commit SHA. The workflow obtains its own defining commit, repository and file from GitHub's [job context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context), passed as `toJSON(job)`. It validates the reusable workflow identity and fails when that context is missing. The workflow builds the native CLI first, then checks out the contract at `contract_ref` without credentials. Immediately before running the runner, it requires `git merge-base --is-ancestor WORKFLOW_SHA CONTRACT_REF` and verifies that the checkout is exactly `contract_ref` with no tracked or untracked changes. The workflow therefore accepts its own commit and descendants, and rejects older commits or unrelated branches. Hub tests execute the actual workflow checks against a temporary Git history.

The corpus is public, so a detector can be written against its source text. A fake that looks each fixture up by its exact source and replays the declared outcomes passes every case, and the runner tests record that it does. Renaming fixtures stops lookup by name only. True holdouts cannot live in this repository. The parent session's independent reviewers act as the holdout: they run fresh adversarial probe censuses against each candidate. The corpus is an acceptance gate, not proof about all programs.

## Primary definitions

- [What is an action?](https://ericnormand.me/podcast/what-is-an-action)
- [What is a calculation?](https://ericnormand.me/podcast/what-is-a-calculation)
- [What is immutability?](https://ericnormand.me/podcast/what-is-immutability)
- [Do you need immutability for functional programming?](https://ericnormand.me/podcast/do-you-need-immutability-for-functional-programming)
- [Is FP just programming with pure functions?](https://ericnormand.me/podcast/is-fp-just-programming-with-pure-functions)
