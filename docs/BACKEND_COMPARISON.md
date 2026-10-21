# Backend replacement validation

ArithDiag-LS is the main method. ArithDiag-G is the optional replacement adapter.
Both invoke the same conditional arithmetic model, preprocessing, initialization,
internal search/proof, interleaved50 ledger and original-model checker.

LS compiles Big-M constraints only at backend handoff, audits the native input,
and retains adapted arithmetic proposals and restarts. G compiles integer radix
segments and indicators directly, receives verified starts, and retains numerical
safety guards. Neither consumes externally supplied optimum values.

Different representations are deliberate backend implementations. Compare complete
configurations, including encoding time and measured memory. Do not attribute their
entire difference solely to the underlying solver. Separate results by whether a
backend was invoked, whether it improved U, and where the final proof originated.

Baseline search implementations and their experiment controller remain outside
this repository. There is no RC2, SATbD, SAFARI or SMT backend dispatch in ArithDiag.
