# Timelapse target region

These constraints apply to this sample, not to the general workflow. They also apply to
clips cut from `timelapse1.avi`.

Annotate the **dark cells in the anatomical band along the embryo's side/belly**.
`target.jpg` illustrates this band with a red outline. It is not a fixed pixel
area, crop, or segmentation mask to transfer from the reference image.

Find the band from the visible anatomy in each frame and follow it as the embryo
moves and rotates. Use the cell neighborhoods and the shape of the specimen to
recognize the same band across changes in view. Registering the outline once,
including by matching the eye, does not define the target in later frames.

This task does not assert what kind of cell these are. Do not decide what type of cell they
are, and do not leave a cell out for that reason: treat each distinct dark cell in the band
as one target and give it its own identity.

Dark marks elsewhere on the embryo are outside this task's scope, even when they look like
easier isolated examples. Exclude the large eye, bubbles, and background texture. Record
unresolved ownership explicitly; an unresolved collection of candidates is not one cell.
