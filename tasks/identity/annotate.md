# Cell identity annotation prompt

You are the annotator for the supplied microscopy clip. Find every distinguishable
cell in the requested region, mark its visible pixels in every frame, and keep
one persistent identity per cell across the whole sequence. Deliver the
annotations. Choose how to do the work yourself; the
result must satisfy the same requirements regardless of the tools you use.

Use the source clip, reference image and output directory named in the launch
prompt. `target.md` and the reference image define the region whose cells you are to annotate.
Continue through the whole clip without waiting for intermediate approval. Full
annotation and visual review of every source frame are required.

This task is about identity: for each cell, mark everything you can see of that one
cell (its body and any processes attached to it) as a single mask. Follow `annotations.schema.json` for how to save it: it defines the coordinates, the
mask encoding and the format of each entry, and it includes an example.

Work in one conversation; context compaction and CLI continuation are allowed.
Keep the cell id table, the saved annotations, unresolved decisions and review
progress on disk so you can continue reliably. Keep identity decisions in this
conversation; do not delegate frames to other agents. Keep scratch scripts and
generated artifacts in the output directory. Use only the supplied inputs and your
own work, without consulting other runs, reference annotations, evaluation
answers or any files outside this workspace.

You may create tools that help you annotate, inspect and correct the data, using
the Python environment here (`uv sync --locked`). Use `uv run cell-render` to
display saved masks and `uv run cell-views` for full-resolution PNGs and contact
sheets. `source.txt` contains the source video's filename for the commands below.

1. Before annotating, generate contact sheets of **every raw input frame**:

   ```bash
   uv run cell-views --source "$(cat source.txt)" --output output/raw
   ```

   Open every image in `output/raw/sheets/` and inspect the entire requested
   region in every frame. The sheet labels give zero-based frame indices and
   timestamps. The specimen may twitch, rotate or jump abruptly between frames;
   identify these transitions before starting. Use close, pixel-preserving
   views to tell neighboring cells apart. Establish which cells belong to the
   requested region from `target.md` and the reference image. You may begin with a clear frame or
   a few cells, but that does not reduce the scope of the task.
2. Annotate every distinguishable cell throughout the sequence. Follow each
   identity between neighboring frames and through changes in pose, focus and
   appearance. Add cells that become visible later. Check for identity switches,
   duplicate IDs for one cell, and different cells sharing an ID. Revisit
   earlier frames when later evidence changes a decision. Verify disappearance
   against the source; difficulty matching an identity does not establish that a
   cell is absent. If a cell at one position in one frame is recognizable as the
   same cell at another position in another frame, both masks must use the same
   ID, including across distant frames and very different views.
   Across an abrupt pose change, compare the arrangement of neighboring cells,
   their shapes and their processes to maintain identities. Inspect native crops
   from several frames on both sides and follow candidates forward and backward.
   Before creating a new ID, check whether you have already identified that cell
   in another frame.
   Use the existing ID wherever the source supports the match. If review reveals
   that one cell has multiple IDs, correct all affected masks to use one ID.
   Do not restart a group of identities or leave a frame unannotated because a
   pose jump or identity match is difficult.
3. Generate overlays from the **saved** annotations for every frame:

   ```bash
   REVIEW="output/review-$(date +%s%N)"
   uv run cell-views --source "$(cat source.txt)" \
     --annotations output/annotations.json --output "$REVIEW"
   ```

   Open every contact sheet in the printed `sheets/` paths, then open **every
   full-resolution overlay** in that review directory's `frames/`. The raw
   full-resolution frames are in `output/raw/frames/`. For every frame,
   compare raw and annotated views over the whole region, with close crops wherever
   needed, and readable IDs; the renderer colors each cell consistently. Check both directions: every
   recognizable cell should be marked, and every marked pixel and identity should
   be supported by the source. Look for missed cells, background pixels, and
   masks that cover or merge neighboring cells. Opening a view without assessing
   it does not complete review.
4. Correct the saved masks and identities wherever review reveals an error or
   omission, then render and open the affected views again. Recheck identity
   changes across all affected frames. Continue until you have addressed the
   discrepancies you can resolve from the source. Checking a few examples does not
   validate the remaining cells or frames. Contact sheets alone cannot establish
   which pixels belong to which cell. Rerun the overlay command after edits; it
   creates a fresh review directory so older overlays cannot be mistaken for the
   current saved annotations. `frames.json` records frame coverage and source and
   annotation hashes; it does not establish that visual review occurred.
5. Preserve uncertainty at the place it occurs. Distinguishable cells must have
   separate identities even when parts of them cannot be assigned. Never use one
   cell ID as a container for several unresolved cells. Record uncertain
   identity alternatives explicitly, without claiming an established association.
   Uncertainty about boundary pixels does not justify separate IDs for a
   recognizable cell. Leave an identity link unresolved only when a specific
   visual ambiguity remains after cross-frame review.
   Do not present guesses as observed pixels. A cell that is not visible in a frame, or
   is out of frame, has no entry for that frame; say in your final response where you
   are unsure.
6. Before hand-off, account for every source frame and every cell in the region.
   Review the first and last frame annotated for each cell ID, especially when
   many IDs end and new IDs appear together. Check the source to distinguish visibility changes from
   broken links, and reconcile every recognizable match under one persistent ID.
   Complete the annotations and visual review throughout the entire sequence.
   A valid JSON file or a successful rendering command does not satisfy these requirements.

Validate the JSON against `annotations.schema.json`, and separately check the image-dependent
invariants it describes (run bounds, non-overlapping runs, frame indices inside the video, at most one
entry per cell per frame).
Your only deliverable is `output/annotations.json`; it is the only file collected, so
do not rely on any other output. Each cell must keep its ID across frames. Frame indices
are in the video's decode order, starting at zero. Any later annotation change invalidates
your review of the affected views.

The final response states annotation and review coverage (frames, IDs and regions you
inspected), the unresolved identity or pixel alternatives and where they are,
and whether compaction occurred (or unknown if undetermined). Keep
your visual checks distinct from human review.
