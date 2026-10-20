# Identity annotation format

The saved `annotations.json` conforms to `annotations.schema.json` and holds
full-resolution pixel masks for every cell in every included frame. Coordinates
refer to the decoded source image: integer `(x, y)` is column `x`, row `y`, with
`(0, 0)` at the top left. Frame indices start at zero; timestamps keep the source
presentation times.

Each cell/frame observation has three mask fields, used like this in this task:

- `body`: every pixel you can attribute to this cell in this frame, soma and
  attached processes together. There is no body/branch distinction here.
- `branches`: always `[]`. The field stays because the shared schema and renderer
  require it.
- `uncertain`: candidate pixels whose ownership you cannot resolve. These are
  excluded from `body`, are optional, and must be reported as unresolved.

Within an observation the masks do not overlap. Masks of different cells are
independent, so ambiguous ownership at a crossing can stay uncertain instead of
being forced onto one cell.

Encode each mask losslessly as horizontal runs `[y, x_start, x_end]` with an
exclusive `x_end`: `[10, 20, 23]` is exactly pixels `(20, 10)`, `(21, 10)` and
`(22, 10)`. Runs need integer bounds with `0 <= y < height` and
`0 <= x_start < x_end <= width`, must not overlap within a mask, are sorted by row
and starting column, and touching runs are coalesced. An empty mask is `[]`.

The schema's field names (`neurons`, `neuron_id`) are historical. Each entry in `neurons` is one cell, and no claim is made about its cell type.

A synthetic example, not an annotation of the sample:

```json
{
  "schema_version": 1,
  "revision": 1,
  "source": {
    "path": "synthetic_clip.avi",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "width": 64,
    "height": 48
  },
  "frames": [{ "frame_index": 0, "timestamp_s": 0.0 }],
  "neurons": [{ "id": "N001", "color": "#e6194b" }],
  "observations": [
    {
      "neuron_id": "N001",
      "frame_index": 0,
      "visibility": "visible",
      "body": [
        [10, 20, 27],
        [11, 20, 23]
      ],
      "branches": [],
      "uncertain": [[10, 27, 28]],
      "review": "proposed"
    }
  ]
}
```

`visibility` is `visible`, `uncertain`, `not_visible` or `out_of_frame`; `review` is
`proposed`, `agent_reviewed` or `human_reviewed`. Keep one observation per cell
per included frame, including explicit absence states. `not_visible` and
`out_of_frame` observations have empty masks.

Render directly from the saved runs with `uv run neuron-render`; zoom without
interpolating mask labels. Edit by tracing, brushes, polygons or computed
proposals as useful, then save and inspect the resulting pixel masks.

The schema checks structure only. Separately validate run bounds, mask
disjointness, unique cell/frame observations, complete frame coverage and
frame/ID references. A schema-valid file can still contain wrong masks.
