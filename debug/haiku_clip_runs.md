# First Haiku clip runs: what happened and what to change

Haiku, high effort, one run per clip, on the short clips cut around each marked group. Rollouts are in
`runs/20261021T0006Z_identity_clips/` (66-72, 58-62, 52-58). These ran on the old 1280x944 video and the marks
before they were rescaled to `data/timelapse1.avi`. All of them are single runs, so treat the numbers as
anecdotes. The findings come from the agents' own hand-off notes, the saved answers and one geometry check on
52-58; the transcripts were not read in full.

| Clip | same_cell | different_cell | marks_covered | all_pass | Cells annotated |
| --- | --- | --- | --- | --- | --- |
| 66-72 | 0.99 | 0.99 | 1.00 | yes | 33 |
| 58-62 | 0.63 | 0.46 | 0.80 | no | 18 |
| 52-58 | 0.00 | 0.00 | 0.00 | no | 13 |

A fourth clip, 24-32, was lost twice: a container restart killed it, and a rerun was scored against marks at the
wrong scale (a stale cached clip from the old video; fixed, the cache is now keyed by the video hash and the
clip size is checked). That invalid result was not kept. The rerun on the new video is in `runs/20261021T0045Z_identity_clips_24-32/`: 3 of 6 marks hit, `all_pass` no, 127 cells annotated, 17 minutes of agent time.

## What we saw

- **66-72 passing says little.** The agent marked every dark blob (33 per frame) and tracked them. That covers
  all the marks, and nothing penalizes extra cells, so the best strategy for this score is to annotate
  everything dark. The extra-cell measure in `TODO.md` matters before prompts are tuned against these scores.
- **52-58 looked in the wrong place.** The agent located the red outline in `target.jpg` by template matching
  on the eye and then restricted itself to that fixed pixel region (about y 615-690 in the clip). The marks run
  from about y 640 to 906 and x 186 to 693, so the lower-left part of the band was never annotated. The launch
  prompt says the outline "marks the region", which invites reading it as a fixed area.
- **58-62 and 52-58 hit abrupt pose changes.** The embryo rotates about 90 degrees in the last frame of 58-62,
  and 52-58 jumps between frames 4 and 5 and between 8 and 9. The agents could not link identities across a jump
  and left those frames empty (58-62 frame 8, 52-58 frames 9-10) or gave the cells before and after the jump
  unrelated ids. An empty frame scores zero; a best guess might not.
- **They stopped early and said so.** Each run used about 6 to 8 minutes of a 120 minute budget and called the
  result partial. The prior `annotate.md` step 6 allowed exactly this ("save the work as partial and identify the exact
  affected frames"), and all three used it.
- **Review was thin.** All three said their visual checks covered a few frames, although step 3 requires every
  frame.

## Prompt v2 changes

Applied in `tasks/identity/annotate.md` and `target.md`, with tested `cell-views` commands
for raw frames, saved-mask overlays and contact sheets. The following list records the original decisions:

1. **Remove the license to stop early.** Delete the partial hand-off text in `annotate.md` step 6 and the
   final-response request to report incomplete work. State that full annotation of every frame is required.
2. **Warn that poses can jump.** The specimen can twitch, rotate or jump between frames; identity must be kept
   across such jumps by matching the arrangement of neighboring cells, and a frame is never left empty.
3. **Require looking at every input frame first**, as a contact sheet of the raw frames, so the agent sees the
   jumps before it starts. Provide the command ready-made.
4. **Require validation by looking**: render an overlay for every frame and open each one, with a ready-made
   contact-sheet command for the annotated frames too. Contact sheets orient, close crops still decide pixels
   (keep the existing sentence on that).
5. **Describe the region by anatomy, not coordinates.** Keep the side/belly-band and illustrative-outline
   guidance in `target.md`. The generic prompt and launch message refer to that file without specifying
   anatomy or coordinates.

## Next experiments

- v2 prompt on Haiku (high) and the current prompt on Sonnet (medium-high), one run per clip, so that model and
  prompt effects can be told apart; repeat the two weaker clips about three times per condition.
- Re-run on `data/timelapse1.avi` for every condition so all runs share one video and one set of marks.
- A judge agent that views the overlays and iterates with the annotator is a later step, after the simpler
  prompt fixes and once the ground-truth annotation file exists.

## Running these

A scheduled wake-up resets the container and kills background processes (two batches were lost this way). Run
long jobs with the harness's background command and wait for its completion notice instead of timers.
