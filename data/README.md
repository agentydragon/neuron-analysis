# Original sample

`timelapse1.avi` is the full-resolution original of the recording and the video the eval uses: 73 frames,
1376 × 1024, 36.5 seconds at 2 fps, Motion JPEG. It has the same frames as `IMG_6128.AVI` below, which is a
downscaled copy (1280 × 944): registering the two gives a pure scale of 1.075 in x and 1.085 in y with
under a pixel of residual and no crop. `data/eval/identity_marks.json` was painted on `IMG_6128.AVI` and
resampled onto this video (see `data/eval/README.md`). `IMG_6128.AVI` is kept so earlier runs stay reproducible.

`IMG_6128.AVI` is the original Xenopus laevis embryo recording: 73 decoded
frames, 1280 × 944, 36.4 seconds, H.264 in an MP4 container despite its AVI suffix.
`photo_2026-10-19_14-30-28.jpg` is the 1280 × 915 target reference; its red outline
guides anatomical target selection, not fixed-coordinate segmentation.

All three files are stored unchanged through Git LFS. `manifest.json` records their
sizes and SHA-256 hashes. Retrieve their contents with `git lfs pull` after cloning.
The files were copied from `~/drive/neuron-tracking/data/`; the Drive originals
are retained. No external candidate videos or generated trial outputs are included.
