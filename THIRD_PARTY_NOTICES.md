# Third-party notices

## LS-IQCQP

Source: https://github.com/INFORMSJoC/2025.1178
Pinned commit: d41da7f2cb1dbd03f3cf18c8508bb82080383a51
Authors: Xiang He, Peng Lin, Tao Jiang, Shaowei Cai.
Original license: MIT, preserved verbatim in `vendor/LS-IQCQP.LICENSE`.

`native/ls-iqcqp/` and `baseline/native/` contain substantial source derived from
this project. ArithDiag adds instrumentation, initialization handling and
component-aware moves to the adapted kernel. The original license remains
applicable to upstream-derived code. The upstream authors are not claimed as
authors of ArithDiag.

Paper DOI: https://doi.org/10.1287/ijoc.2025.1178
Software DOI: https://doi.org/10.1287/ijoc.2025.1178.cd

## External build dependencies

GSL and Boost are dependencies, not bundled source or binary packages.
GSL is distributed under the GNU GPL; Boost under the Boost Software License.
Respect the dependency licenses if distributing executables linked to them.
This source release includes no linked executables.

## Benchmark and test fixtures

The benchmark is distributed separately at
https://github.com/oldmouz-szm/MBD-Benchmark/tree/v1.0.0
and has its own license and third-party notices. No generated ArithsGen component
source is copied into ArithDiag. The tiny arithmetic interface fixtures in
`tests/fixtures/library/` are handwritten for these tests.
