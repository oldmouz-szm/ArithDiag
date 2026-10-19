# Third-party notices

ArithDiag's own source is licensed under the root MIT license.

`ArithDiag-LS/native/` contains an adapted LS-IQCQP kernel derived from
[INFORMSJoC/2025.1178](https://github.com/INFORMSJoC/2025.1178), fixed upstream
commit `d41da7f2cb1dbd03f3cf18c8508bb82080383a51`. The original copyright and MIT
permission are preserved in `ArithDiag-LS/native/LICENSE`. ArithDiag modifications
include circuit component proposals, exact integer candidate transport and input
auditing, and budgeted integration. This is a modified kernel, not an unmodified
upstream binary. GSL and Boost are external build dependencies; their libraries
and source are not redistributed here.

Gurobi and gurobipy are proprietary external dependencies. This repository does
not distribute Gurobi binaries, credentials or licenses, and the root MIT license
does not grant rights to those products. Users must obtain a suitable license.

Datasets and generated circuit libraries are separate materials with their own
licenses and third-party notices. This repository contains no benchmark data or
generated component library and makes no license grant for them. Test interfaces
are small author-written fixtures generated transiently by test code; they are
not copies of the benchmark's generated gate library.
