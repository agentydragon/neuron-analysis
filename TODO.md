# TODO

- [ ] Investigate whole groups of identities restarting across pose jumps, starting
      with baseline full-video frames 29–30 (15 s): review supported links, compare
      v2's full run, and test focused cross-transition reconciliation and track-lifetime
      diagnostics. See `debug/gpt_6_1_sol_runs.md`; preserve the original saved answers.
- [ ] Repeat matched GPT-6.1 Sol medium baseline/v2 runs (initially five per prompt
      per slice), reporting score distributions and runtime. Single attempts and
      different slices do not establish a prompt effect; assess full-video tracking separately.
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
- [ ] Compare prompt v2 on Haiku (high) with the prior prompt on Sonnet (medium-high) on all four clips,
      repeating the weaker clips. Keep the input video and marks fixed across conditions.
- [ ] Compare against the ground-truth annotation file once it exists.
- [ ] Later: a judge agent that reviews an annotator's rendered overlays and sends it back to fix problems.
