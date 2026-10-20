# v0.4.0 final-test freeze

ArithDiag-LS is the default main configuration; ArithDiag-G remains an optional
backend replacement adapter. The common observation model stores conditional
integer equations without Big-M. LS generates Big-M only on invocation; G compiles
integer digits and indicators. The production internal budget is fraction50.

The complete algorithm is retained from the tested conditional-model/fraction50
development snapshot. This release adds explicit internal search/proof ablation
gates, configuration identity and documentation, without retuning the full
algorithm, native component moves, conflict acceptance or resource guards.
Legacy budget choices and the external RC2 dispatch label are not exposed.

The main-paper ablations are no-internal-search, no-proof-enhancement and
backend-only. Common preprocessing, initialization and basic bounds remain on.
G supports full only. See EXPERIMENT_PROTOCOL.md and ABLATIONS.md for exact scope.

Correctness validation on Linux with Python 3.14.4 includes:

- 128 independently enumerated models, 384 transformation checks and 1024 conflict
  checks, plus connection/partial-bus regressions.
- Conditional-model vs LS encoding checks on 1664 assignments and wide boundaries.
- Full, search-disabled and proof-disabled coordinators each checked on 220 finite
  circuits, 660 reduced-domain checks and 1980 internal steps against independent
  exhaustive signal semantics; returned witnesses and lower bounds are checked.
- Independent hitting-set enumeration, UNKNOWN/deadline regressions, 65-bit Big-M
  transport audits, native witness and component-move checks.
- Eight fresh-worker cases across four variants, exact certificates and no-rerun
  recovery, plus four fan-out cases requiring real LS handoff when search is off.
- Offline G encoding checks using the actual builder with a recording stub:
  256 small and 10 wide assignments. No SDK optimization or license session used.

The implementation checks are not a substitute for the general arguments listed
in CORRECTNESS_OBLIGATIONS.md. Native G optimization was not retested during this
freeze; its existing guards/encoding remain and its live regression is opt-in.

Source integrity is frozen in SOURCE_MANIFEST.json and the release Git tag.
Historical code/results remain unchanged and must not be relabeled as v0.4.0.
No formal batch was started for this release; execution awaits explicit approval.
