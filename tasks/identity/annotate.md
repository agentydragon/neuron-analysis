# Neuron identity annotation prompt

You are the annotator for the supplied microscopy clip. Find every distinguishable
neuron in the requested region, mark its visible pixels in every frame, and keep
one persistent identity per neuron across the whole sequence. Deliver the
annotations and a colored annotated video. Choose how to do the work yourself; the
result must satisfy the same requirements regardless of the tools you use.

Use the source clip, reference image and output directory named in the launch
prompt. `target.md` and the reference image define the region whose neurons you are to annotate.
Follow that region as the specimen moves and rotates; the outline guides target
selection and is not an already aligned segmentation mask. Continue through the
whole clip without waiting for intermediate approval.

This task is about identity. Do not separate body from branches: for each neuron,
mark everything you can see of that one cell (its body and any processes attached
to it) as a single mask. Read `format.md` for how to save it and
`annotations.schema.json` for the machine format.

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
   views to tell neighboring cells apart. Establish which neurons belong to the
   requested region from `target.md` and the reference image. You may begin with a clear frame or
   a few neurons, but that does not reduce the scope of the task.
2. Annotate every distinguishable neuron throughout the sequence. Follow each
   identity between neighboring frames and through changes in pose, focus and
   appearance. Add neurons that become visible later. Check for identity switches,
   duplicate IDs for one neuron, and different neurons sharing an ID. Revisit
   earlier frames when later evidence changes a decision. Verify disappearance
   against the source; difficulty matching an identity does not establish that a
   neuron is absent. The same neuron seen in distant frames, or from a very
   different view, must keep its ID.
3. For every frame, open the saved annotations rendered over its source pixels.
   Compare raw and annotated views over the whole region, with close crops wherever
   needed, readable IDs and stable distinct colors. Check both directions: every
   recognizable neuron should be marked, and every marked pixel and identity should
   be supported by the source. Look for missed neurons, background pixels, and
   masks that cover or merge neighboring cells. Opening a view without assessing
   it does not complete review.
4. Correct the saved masks and identities wherever review reveals an error or
   omission, then render and open the affected views again. Recheck identity
   changes across all affected frames. Continue until you have addressed the
   discrepancies you can resolve from the source. Checking a few examples does not
   validate the remaining neurons or frames. Contact sheets alone cannot establish
   which pixels belong to which cell.
5. Preserve uncertainty at the place it occurs. Distinguishable cells must have
   separate identities even when parts of them cannot be assigned. Never use one
   neuron ID as a container for several unresolved neurons. Record uncertain
   identity alternatives explicitly, without claiming an established association.
   Do not present guesses as observed pixels. Use `uncertain`, `not_visible` and
   `out_of_frame` according to the evidence and `format.md`.
6. Before hand-off, account for every source frame and every neuron in the region.
   Having an observation row for every frame or a valid JSON file does not satisfy
   these requirements. If a resource limit or a specific ambiguity prevents
   completion, save the work as partial and identify the exact affected frames,
   regions, IDs and unresolved decisions; do not call an incomplete result complete.

Validate the JSON structure and the image-dependent mask invariants in `format.md`.
Your only deliverable is `output/annotations.json`; it is the only file collected, so
do not rely on any other output. Each neuron must keep a distinct color and its ID
across frames. Preserve source frame order and dimensions. Any later annotation
change invalidates your review of the affected views.

The final response states annotation and review coverage (frames, IDs and regions you
inspected), the unresolved identity or pixel alternatives and where they are, any
incomplete work, and whether compaction occurred (or unknown if undetermined). Keep
your visual checks distinct from human review.
