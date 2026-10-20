# Cell identity annotation prompt

You are the annotator for the supplied microscopy clip. Find every distinguishable
cell in the requested region, mark its visible pixels in every frame, and keep
one persistent identity per cell across the whole sequence. Deliver the
annotations and a colored annotated video. Choose how to do the work yourself; the
result must satisfy the same requirements regardless of the tools you use.

Use the source clip, reference image and output directory named in the launch
prompt. `target.md` and the reference image define the region whose cells you are to annotate.
Follow that region as the specimen moves and rotates; the outline guides target
selection and is not an already aligned segmentation mask. Continue through the
whole clip without waiting for intermediate approval.

This task is about identity. Do not separate body from branches: for each cell,
mark everything you can see of that one cell (its body and any processes attached
to it) as a single mask. Follow `annotations.schema.json` for how to save it: its descriptions define the coordinates,
the mask encoding and the meaning of each field, and it includes an example.

Work in one conversation; context compaction and CLI continuation are allowed.
Keep the ID/color table, annotation revision, unresolved decisions and review
progress on disk so you can continue reliably. Keep identity decisions in this
conversation; do not delegate frames to other agents. Keep scratch scripts and
generated artifacts in the output directory. Use only the supplied inputs and your
own work, without consulting other runs, reference annotations, evaluation
answers or any files outside this workspace.

You may create tools that help you annotate, inspect and correct the data, using
the Python environment here (`uv sync --locked`). Use `uv run neuron-render` to
display saved masks; run `uv run neuron-render --help` for options.

1. Inspect the source sequence yourself, including the entire requested region in
   every frame. Use an overview to orient yourself and close, pixel-preserving
   views to tell neighboring cells apart. Establish which cells belong to the
   requested region from `target.md` and the reference image. You may begin with a clear frame or
   a few cells, but that does not reduce the scope of the task.
2. Annotate every distinguishable cell throughout the sequence. Follow each
   identity between neighboring frames and through changes in pose, focus and
   appearance. Add cells that become visible later. Check for identity switches,
   duplicate IDs for one cell, and different cells sharing an ID. Revisit
   earlier frames when later evidence changes a decision. Verify disappearance
   against the source; difficulty matching an identity does not establish that a
   cell is absent. The same cell seen in distant frames, or from a very
   different view, must keep its ID.
3. For every frame, open the saved annotations rendered over its source pixels.
   Compare raw and annotated views over the whole region, with close crops wherever
   needed, readable IDs and stable distinct colors. Check both directions: every
   recognizable cell should be marked, and every marked pixel and identity should
   be supported by the source. Look for missed cells, background pixels, and
   masks that cover or merge neighboring cells. Opening a view without assessing
   it does not complete review.
4. Correct the saved masks and identities wherever review reveals an error or
   omission, then render and open the affected views again. Recheck identity
   changes across all affected frames. Continue until you have addressed the
   discrepancies you can resolve from the source. Checking a few examples does not
   validate the remaining cells or frames. Contact sheets alone cannot establish
   which pixels belong to which cell.
5. Preserve uncertainty at the place it occurs. Distinguishable cells must have
   separate identities even when parts of them cannot be assigned. Never use one
   cell ID as a container for several unresolved cells. Record uncertain
   identity alternatives explicitly, without claiming an established association.
   Do not present guesses as observed pixels. Use `uncertain`, `not_visible` and
   `out_of_frame` according to the evidence and `annotations.schema.json`.
6. Before hand-off, account for every source frame and every cell in the region.
   Having an observation row for every frame or a valid JSON file does not satisfy
   these requirements. If a resource limit or a specific ambiguity prevents
   completion, save the work as partial and identify the exact affected frames,
   regions, IDs and unresolved decisions; do not call an incomplete result complete.

Validate the JSON against `annotations.schema.json`, and separately check the image-dependent
invariants it describes (run bounds, non-overlapping masks, one observation per cell per frame,
complete frame coverage).
Your only deliverable is `output/annotations.json`; it is the only file collected, so
do not rely on any other output. Each cell must keep a distinct color and its ID
across frames. Preserve source frame order and dimensions. Any later annotation
change invalidates your review of the affected views.

The final response states annotation and review coverage (frames, IDs and regions you
inspected), the unresolved identity or pixel alternatives and where they are, any
incomplete work, and whether compaction occurred (or unknown if undetermined). Keep
your visual checks distinct from human review.
