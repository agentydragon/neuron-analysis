# GPT-6.1 Sol: baseline and prompt v2

Snapshot: 2026-10-21 05:05 UTC (2026-10-20 PDT). Five baseline runs and four v2
slice runs have completed; the v2 full-video run is still pending. These are single
attempts, not evidence of a reliable prompt effect.

## Conditions and results

Both batches use native Codex CLI 0.162.1, `gpt-6.1-sol`, medium effort, and a
120-minute agent limit, with one attempt for the full video and each of four slices.
The full source is `data/timelapse1.avi`, 73 frames at 2 fps, SHA-256
`36d2a3aa7065af6a14f87e397895e6871e412bba7851f4a86e7f6203735d10ed`.
Clips have two margin frames on either side where available. Each matched
old/new condition uses the same input video and scoring marks.

- Baseline batch: `20261021T042016Z_gpt-6.1-sol_medium_b5b35b`, code `d1e882c`.
- V2 batch: `20261021T044420Z_gpt-6.1-sol_medium_prompt-v2_7fe1a4`, code `e2c2d64`.
- Each run is `runs/<batch>_<full-or-slice>/`. The `.eval` contains scores and
  failing pairs; `outputs/` contains the saved answer; `transcripts/` contains the
  agent hand-off and execution record. V2 also has an `inputs/` snapshot.

V2 combines prompt changes with the supplied `cell-views` helper: complete raw-frame
orientation and saved-mask review, stronger completion and persistent-identity
requirements across pose jumps, and anatomy-based target guidance in `target.md`.
See [the original change list](haiku_clip_runs.md#prompt-v2-changes). This comparison
does not isolate the contribution of any individual change.

Scores are percentages. Time is agent execution time, excluding setup and scoring.

| Case | Prompt | Same cell | Different cell | Marks touched | Mark share | All-pass | IDs | Agent time |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Full | Baseline | 71.6 | 80.1 | 94.4 | 88.6 | no | 36 | 23:38 |
| Full | V2 | pending | pending | pending | pending | pending | — | — |
| 24–32 | Baseline | 99.6 | 99.6 | 100 | 99.8 | yes | 56 | 12:03 |
| 24–32 | V2 | 97.2 | 97.2 | 100 | 98.6 | yes | 37 | 11:00 |
| 52–58 | Baseline | 69.9 | 69.0 | 90 | 83.7 | no | 28 | 8:46 |
| 52–58 | V2 | 79.6 | 73.4 | 100 | 86.2 | yes | 30 | 7:12 |
| 58–62 | Baseline | 99.7 | 99.7 | 100 | 99.9 | yes | 25 | 8:51 |
| 58–62 | V2 | 75.9 | 74.3 | 100 | 86.4 | yes | 42 | 7:23 |
| 66–72 | Baseline | 94.2 | 94.2 | 100 | 97.1 | yes | 25 | 4:58 |
| 66–72 | V2 | 100 | 100 | 100 | 100 | yes | 25 | 3:20 |

All nine completed agents exited successfully without timing out. V2 improves the
slice all-pass count from 3/4 to 4/4 and touches every marked spot, but its soft
scores regress substantially on 58–62 and slightly on 24–32. The binary all-pass
test uses best-matching identities and whether marks are touched; it does not
require complete pixel coverage. Report it alongside the soft scores and mark share.
These marks do not measure whole-cell boundary accuracy or penalize extra cells.

One run per condition cannot separate prompt effects from run variation. The
different slices are different tasks, not repeated measurements of one task.
Repeat each matched condition (initially five attempts per prompt per slice),
report distributions and runtimes, and keep full-video results separate.

## Full-video identity reset at 15 seconds

The user noticed a synchronized end of tracks in the mask-area chart. This is in
the saved baseline annotations, not caused by MP4 conversion or plotting:

- `C01`–`C11` and `C21` all end at frame 29 (14.5 video seconds), never returning.
- `P01`–`P15` all begin at frame 30 (15 seconds). Visible mask count rises from
  21 to 24; the main problem here is loss of cross-transition identity continuity.
- The agent's final hand-off explicitly leaves posterior identity links across
  frames 29–30 unresolved, calls the `P` IDs provisional, and calls its output
  partial. It stopped after 23:38 of a 120-minute limit. Remaining wall-clock
  budget does not by itself prove the image ambiguity was resolvable.
- The old prompt allowed a partial hand-off. V2 already requires revisiting pose
  transitions, checking neighborhoods and preserving identity; its full-video
  result has not yet been assessed.

Evidence is in the baseline full run's
`outputs/20261020T214601_full.annotations.json` and
`transcripts/codex_82486c19be3a4225a590f8e07640ada0/final.md`.
The score metadata confirms three broken, hand-marked same-cell pairs across
frames 24 and 32:

| Mark color | ID at frame 24 | ID at frame 32 | Mark pixels covered, before / after |
| --- | --- | --- | --- |
| `#ed1c24` | C01 | P01 | 100% / 100% |
| `#00a2e8` | C04 | P07 | 100% / 100% |
| `#22b14c` | C03 | P06 | 93.7% / 9.2% |

These establish fragmentation on the marked examples, not a complete mapping of
all old IDs onto new IDs. The low coverage for P06 also leaves a segmentation problem.

## Was there enough information to do better?

Probably yes for at least some links; a complete, unambiguous mapping is not yet
established. I inspected raw and labelled frames 29, 30 and raw frame 31 at native
resolution, plus an overview of frames 24, 26, 28–32 and 34. There is a substantial
pose change, with altered projection and focus. However, the band, several
distinctive shapes and the arrangement of neighbors remain visible; frames 31–32
provide additional views after the jump. The agent also retained C12–C20 across
the transition, although that alone does not validate those associations.

The strongest practical evidence is the matched 24–32 slice: **both baseline and
v2 independently maintain all three marked identities across this same jump**.
The slice contains source frames 22–34, including frames 29–30, with the original
pixels. That shows this model and input can support those three links in a shorter
task. It does not prove every one of the twelve dropped IDs is visually identifiable,
nor exclude lucky associations in single runs. Scoring marks were unavailable to
the annotating agents; their use here is an external diagnostic only.

The useful target is to reconcile supported links and localize genuine ambiguity,
rather than abandon the identity of the whole group. Do not force a one-to-one
mapping between 12 old and 15 provisional IDs: some cells may become visible,
some earlier cells were missed, and some masks may have split or merged.

## Follow-ups

1. Inspect v2's full-video answer for the same mass ID reset when it finishes.
   Compare track lifetimes, area curves and the marked cross-jump pairs, not just
   whether every frame has masks.
2. Make a focused cross-transition review: side-by-side native crops of several
   frames before and after a jump, a persistent identity table, and explicit
   candidate links with their supporting shape/neighborhood evidence. Work in
   both temporal directions and resolve easy anchors before ambiguous neighbors.
   Test whether this process improves continuity without forcing unsupported links.
3. Add a review diagnostic for many tracks ending and new tracks starting at one
   frame. Such a burst should trigger source review, not automatically count as an
   error: visibility really can change. Keep area/lifetime charts as review aids.
4. Repeat old/v2 matched conditions; use independently reviewed cross-jump links
   for evaluation. Expand the continuity checks beyond the current three marked
   cells, and address false positives and boundary quality separately.

## Continuity requirement clarified after these launches

The task owner's requirement is that recognizable matches must share one cell ID,
regardless of position, pose or frame distance. `tasks/identity/annotate.md` now
explicitly requires checking existing tracks before introducing new IDs,
reconciling temporary IDs across all affected masks, reviewing transitions in both
temporal directions, and checking every track's start and end before hand-off.
Boundary uncertainty does not excuse leaving a recognizable identity split.
Genuine ambiguity must be specific and remain after cross-frame review; a
provisional label alone is not a completed identity decision.

This follow-up was made after both batches were launched. Their staged prompts
and saved answers are unchanged, and these results do not evaluate the new wording.

Rendered baseline videos and area charts are local in
`runs/20261021T042016Z_gpt-6.1-sol_medium_b5b35b_rendered-clips/`.
The chart uses source-video seconds and the sum of each mask's horizontal-run
lengths. Missing entries are gaps, not zero-sized cells. The baseline full run's
native transcript export reported `OutputLimitExceededError`; its CLI events,
final hand-off, status and saved annotations remain available. Agent statements
about opening every overlay are self-reports, not an independent visual audit.
