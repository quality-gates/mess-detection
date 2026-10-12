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

## Calls and execution owners

A resolved call substitutes actual storage origins and callable identities into its callee's summary. Ambient effects transfer to the caller. A parameter mutation transfers when the actual storage is externally shared. The same mutation can remain private when the actual argument is a fresh allocation. A known calculation supplied as a callback can resolve a generic helper's parameter-relative uncertainty.

Each analyzer defines finite callable and effect identities, monotone joins, stable equality, and bounded storage paths or explicit widening. Recursive propagation must not grow diagnostic provenance strings at each step. Analysis termination does not prove termination of the analyzed program.

An injected callback or an external function is unknown unless analysis establishes its effects. Passing an effectful function explicitly does not make its invocation a calculation. Unknown effects also propagate to callers.

A factory that returns an effectful callback does not execute that callback. The callback owns the deferred effect. An immediate invocation carries the callback's effect to the caller that invokes it. A file-wide report can therefore contain an action callback while its factory is a calculation.

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

`tests/explicitness_cases.json` records language-specific source examples, value and binding assumptions, expected CLI status, owner-attributed effect sets, quiet owners, and minimum distinct-owner counts. `tests/explicitness_conformance.py` invokes the actual native CLI with JSON output. `tests/explicitness_observations.py` normalizes native records with an owner, source line, rule, and effect evidence.

Duplicate findings, processing errors, suppressed findings, missing owner metadata, and unexpected effect kinds cannot establish a pass. A factory and its callback have separate outcomes. Merely mentioning a caller in a message cannot prove propagation.

The cases include calculations, recognized actions, and unknown calls. The corpus is an acceptance gate, not proof about all programs. Native regressions and independent review cover lexical shadowing, unsupported syntax, escaping storage, and execution ownership beyond the common examples.

## Primary definitions

- [What is an action?](https://ericnormand.me/podcast/what-is-an-action)
- [What is a calculation?](https://ericnormand.me/podcast/what-is-a-calculation)
- [What is immutability?](https://ericnormand.me/podcast/what-is-immutability)
- [Do you need immutability for functional programming?](https://ericnormand.me/podcast/do-you-need-immutability-for-functional-programming)
- [Is FP just programming with pure functions?](https://ericnormand.me/podcast/is-fp-just-programming-with-pure-functions)
