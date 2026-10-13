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

Writing to ambient or caller-visible storage without observing its contents is `ImplicitOutput` only. Reading the contents of such storage is `ImplicitInput`. Reading its length or elements counts as reading its contents. One callable can have both effects.

The effect line of a finding is the line of the direct effect site. For a transferred effect, it is the line of the call, iteration, await, or scheduling site that transfers it. A case can allow more than one line when a construct spans lines.

## Calls and execution owners

A resolved call substitutes actual storage origins and callable identities into its callee's summary. Ambient effects transfer to the caller. A parameter mutation transfers when the actual storage is externally shared. The same mutation can remain private when the actual argument is a fresh allocation. A known calculation supplied as a callback can resolve a generic helper's parameter-relative uncertainty.

Each analyzer defines finite callable and effect identities, monotone joins, stable equality, and bounded storage paths or explicit widening. Recursive propagation must not grow diagnostic provenance strings at each step. Analysis termination does not prove termination of the analyzed program.

An injected callback or an external function is unknown unless analysis establishes its effects. Passing an effectful function explicitly does not make its invocation a calculation. Unknown effects also propagate to callers.

A factory that returns an effectful callback does not execute that callback. The callback owns the deferred effect. An immediate invocation carries the callback's effect to the caller that invokes it. A file-wide report can therefore contain an action callback while its factory is a calculation.

## Execution lifecycle

Each construct below has a stated owner and timing. An analyzer that does not model a construct must report `UnknownEffect` on the owner named here.

- **Generators and iterators.** Python `yield`, TypeScript `function*`, C# `yield return`, F# `seq { }`, and Go range-over-func iterators have a body that belongs to its defining callable. The caller that iterates the body gets the transferred effect at its iteration line.
- **Async code.** An `async` function or an F# `async { }` or `task { }` body belongs to its defining callable. The caller that awaits or runs it gets the transferred effect at the await or run line, for example `await`, `Async.RunSynchronously`, or `block_on`.
- **Lazy iteration.** A lazy body that has no callable identity of its own belongs to the callable that defines it. Examples are a Python generator expression and an F# computation expression. A lambda passed to a lazy combinator such as `map` or `Select` owns its own effects. The callable that forces the lazy value gets the transferred effect at the forcing line. F# `lazy` follows the same rule, and the forcing site is `.Force()` or `.Value`.
- **Definition-time evaluation.** Python default arguments, decorators, and class bodies run when the enclosing definition runs. TypeScript class static initializers run when their class definition runs. The enclosing callable owns these effects. TypeScript default parameters run at call time, so the function that declares them owns their effects.
- **Go `defer`.** A deferred call runs within the enclosing invocation, before that invocation returns. The enclosing function owns the deferred callee's effects at the `defer` line. A named callee also owns its own effects. A deferred function literal is part of the enclosing function.
- **Scheduling.** A Go `go f(x)` statement attributes `f`'s effects to the scheduling function at the `go` line. A library scheduler, such as a timer, a thread pool, or `Task.Run`, is an ordinary call. It transfers effects when the library's semantics are documented. Otherwise it is `UnknownEffect`.

## Macro boundary

A Rust macro invocation is an `UnknownEffect` boundary unless the macro is a documented standard-library macro. `println!`, `print!`, `eprintln!`, and `eprint!` are output. `vec!` is a fresh allocation. A local `macro_rules!` definition with a standard-library name is a different macro, and invoking it is `UnknownEffect`. A separate case would have to define expanded behavior before an analyzer may expand local macros.

## Storage ownership

An argument can refer to caller-owned storage. A local alias retains that origin. A later rebinding does not erase a mutation that happened before the rebinding.

A fresh allocation has private outer storage. Mutation of that outer storage can be part of a calculation. A shallow copy can retain references to caller-owned elements. Mutation of those elements is externally visible and remains an action.

A branch that sometimes makes a copy does not establish private storage on every path. Ownership joins possible origins at the mutation site. A mutable reference permits a write but does not prove that a write occurs.

Readonly bindings and uppercase names do not freeze mutable contents. A read of storage that another operation can change retains its timing dependence. No observed write establishes immutability only under a documented closed-world assumption and an established nonescaping origin. Unknown alias creation and escaped allocations retain uncertainty. A private captured container with no writes or escaping data alias need not acquire timing dependence.

Branches and loops join origins at each operation site. Return summaries preserve argument aliases and fresh allocation provenance. Outer allocation privacy does not erase shared reachable origins.

## Value and binding assumptions

Positive examples restrict numeric operands to exact native numeric values. Container examples use ordinary built-in scalar containers or plain records. They exclude custom iteration, conversion, getters, operator overloads, reflection, and monkey-patching. Standard-library bindings retain their documented semantics. Captured values have no unanalysed mutation or escaping alias.

These restrictions are preconditions of the examples. Type annotations alone do not establish them at runtime. Native documentation must state its corresponding restrictions and analysis boundary. An empty diagnostic set establishes no universal arbitrary-runtime purity claim.

## Shared acceptance cases

`tests/explicitness_cases.json` records one case per language and identifier. Each case has these fields:

- A source fixture.
- Value and binding assumptions.
- The expected CLI exit status: 0 for a calculation-only file and 2 for a file with any effect.
- `outcomes`, which maps each effectful callable to its effect kinds and their allowed effect lines.
- `quiet_owners`, which lists every other callable in the fixture.

`twin_of` links an action twin to the calculation case it mirrors. `variant_of` links an equivalent-syntax variant to its base case. `semantic` explains the expectation. Expectations come from Normand's definitions and this contract. They never come from native output.

The world of owners is closed. A native record fails its case when:

- its owner matches no declared callable, or matches more than one;
- its owner is a quiet owner;
- its effect kind is not declared for its owner;
- its line is not a declared effect line;
- its path does not resolve to the fixture.

Every declared owner and kind must appear in the native report. Duplicate findings, processing errors, missing owner metadata, and malformed records fail the case. A malformed report never ends the run. Merely mentioning a caller in a message cannot prove propagation.

A calculation passes only when its action twin passed in the same run. The twin has the same shape with one recognized effect. A detector that reports nothing therefore fails every calculation pair. A calculation verdict remains a claim of complete analysis under the fail-closed rule above.

`tests/explicitness_conformance.py` runs the native CLI as `CLI FIXTURE json explicitness --strict`. Under `--strict`, a source suppression does not hide a finding. Each language whose CLI supports suppression has a `suppression_marker` case, and that case still expects the suppressed finding. Go has no suppression mechanism.

Each fixture gets a random file name and a random directory for each run. Only the language suffix stays fixed. Native paths are compared with the full fixture path. A containerized CLI declares a prefix mapping with `--path-map CONTAINER=HOST`. C# uses `/src` and Rust uses `/workspace`.

The runner exits 0 when every selected case passes, 1 when any case fails, and 2 for a usage or corpus error. It writes its output file after each case, and the file records whether the run completed.

The corpus is public, so a detector can be written against its source text. Renaming fixtures stops lookup by name only. True holdouts cannot live in this repository. The parent session's independent reviewers act as the holdout: they run fresh adversarial probe censuses against each candidate. The corpus is an acceptance gate, not proof about all programs.

## Primary definitions

- [What is an action?](https://ericnormand.me/podcast/what-is-an-action)
- [What is a calculation?](https://ericnormand.me/podcast/what-is-a-calculation)
- [What is immutability?](https://ericnormand.me/podcast/what-is-immutability)
- [Do you need immutability for functional programming?](https://ericnormand.me/podcast/do-you-need-immutability-for-functional-programming)
- [Is FP just programming with pure functions?](https://ericnormand.me/podcast/is-fp-just-programming-with-pure-functions)
