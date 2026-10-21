"""Plot data retains source time and missing observations rather than inventing zeros."""

import importlib.util
from pathlib import Path

from cell_tracking.masks import CellMask, CellMasks, VideoInfo


def test_area_series_uses_exclusive_run_ends_and_preserves_gaps():
    path = Path(__file__).resolve().parents[1] / 'scripts/plot-cell-areas.py'
    spec = importlib.util.spec_from_file_location('plot_cell_areas', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    masks = CellMasks(masks=[
        CellMask(cell='A', frame=0, mask=[(1, 2, 5), (2, 2, 4)]),
        CellMask(cell='A', frame=2, mask=[(1, 3, 4)]),
        CellMask(cell='B', frame=1, mask=[(3, 1, 3)]),
    ])
    info = VideoInfo(width=8, height=6, timestamps_s=[0.0, 0.4, 1.1])
    assert module.area_series(masks, info) == {'A': [5, None, 1], 'B': [None, 2, None]}
