# TODO

- [ ] Pave a durable launch/resume procedure for long parallel Codex jobs and
      investigate their unexpected SIGTERM exits (see `debug/parallel_run_aborts.md`).
      Preserve each run's existing conversation, progress files, and native trace
      across restarts.
- [ ] Check with the principal investigator what the dark cells along the side/belly of the
      embryo are. The task owner was told they are neurons, but others on the project are
      skeptical, and an agent judged them to be pigment cells and annotated nothing. Until
      then everything an agent can read says "cells" or "dark cells" and states that cell type
      is not asserted. Once confirmed, finish the terminology cleanup: the prose in the READMEs,
      the debug notes, the repo name, and the eval names. Also decide whether the marks in
      `data/eval/` still describe the intended cells.
- [ ] Add a false-positive measure: paint regions where there should be no cell and score how
      much of an agent's mask area falls there. Today nothing penalizes extra cells.
