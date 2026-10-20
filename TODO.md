# TODO

- [ ] Extend the reviewed frame-52 examples to short identity tracks and nearby
      excluded structures before another full-clip run. Add more checks as those
      examples are reviewed; the accepted count, body locations, and distinct IDs are in
      `sample_checks.json`.
- [ ] Extend shared validation to CSV consistency and visual review coverage of
      the exported annotation revision. The renderer already validates source
      identity, timestamps, masks, ID colors, and decoded video dimensions/count.
- [ ] Compare the five runs against source pixels: missed targets and branches,
      background leakage, body/branch boundaries, and identity drift. Use their
      native Codex traces for ad hoc investigation.
- [ ] Improve target coverage and tracking through pose changes. A full set of
      frame records does not establish a complete neuron census or correct IDs.
      Keep unresolved candidate groups separate from individual neuron identities.
- [ ] Strengthen visual review so drift and masks outside the specimen trigger
      corrections. Require native-resolution comparisons at difficult transitions
      and recheck changed annotations before export.
- [ ] Pave a durable launch/resume procedure for long parallel Codex jobs and
      investigate their unexpected SIGTERM exits. Preserve each run's existing
      conversation, progress files, and native trace across restarts.
- [ ] If the full identity eval turns out slow, expensive, or does not work easily, make
      smaller, easier versions with shorter time ranges: cut the clip to only the frames
      around each marked group in `data/eval/identity_marks.json` (for example 24-32 or
      66-72, plus some margin) and score only that group's marks, with frame indices
      remapped. Derive the shortened clips and marks from the labels by a script so the
      scorer and the full task keep working unchanged.
- [ ] Check with the principal investigator what the dark cells along the side/belly of the
      embryo are. The task owner was told they are neurons, but others on the project are
      skeptical, and an agent judged them to be pigment cells and annotated nothing. Until
      then the identity task's agent-facing text says "dark cells" and states that cell type is
      not asserted. Once confirmed, clean up the terminology: the prompts and `target.md` in
      `tasks/identity/`, `annotate.md`, `sample_task.md`, the READMEs and debug notes, the schema
      field names (`neurons`, `neuron_id`), the `neuron-*` tool names, the package and repo
      names, and the eval names. Also decide whether the marks in `data/eval/` still describe
      the intended cells.

Compaction is allowed. Keep each run in one Codex conversation and persist the
identity table, annotation revision, unresolved decisions, and review progress so
the agent can continue reliably after compaction.
