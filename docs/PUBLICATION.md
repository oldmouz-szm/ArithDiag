# Public source selection

The source release is prepared independently from the historical development
workspace. The original workspace and its experiment results remain local.

## Included

- Diagnostic model builder, exact validation and transformation code.
- Adapted LS-IQCQP source and the instrumented baseline source used by ablations.
- A configurable serial runner with whole-instance deadlines and memory guards.
- Self-contained small exhaustive tests, partial-bus fixtures and native checks.
- External-dataset audit command, portable build files and a CI smoke workflow.
- Method/result/build documentation, license notices and pinned provenance.
- Source checksums and a concise validation record.

## Excluded

- Virtual environments, private Python distributions and installed libraries.
- Boost package archives and unpacked headers, compiled binaries and object files.
- Generated LP models, caches, temporary files, progress files and worker logs.
- Historical certificates, local reference optima and development result tables.
- Personal machine paths, local environment snapshots and credential material.
- SATbD/BE-RC2 projects and other separately maintained solver implementations.
- Benchmark circuits and observations, which live in MBD-Benchmark.
- Unimplemented baseline methods and unverified final-paper claims.

The CLI no longer requires another project's interpreter, source files or
certificate database. The same public source can be built in an ordinary Linux
environment or WSL. Data paths are supplied explicitly. Release archives are
generated from the committed Git tree, so ignored local files cannot enter them.
