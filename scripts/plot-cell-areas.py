# /// script
# requires-python = ">=3.12"
# dependencies = ["av==17.0.1", "matplotlib==3.11.2", "plotly>=6", "pydantic==2.13.5"]
# ///
"""Plot saved cell-mask area against source-video time, using the renderer's ID colors.

Run with uv and the adjacent script lockfile; see README.md for an example.
"""

import argparse
import csv
import json
import os
from pathlib import Path
import sys

# uv's script environment supplies dependencies; import the models from this checkout.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cell_tracking.hashing import hash_file
from cell_tracking.masks import CellMasks, VideoInfo


def area_series(masks: CellMasks, info: VideoInfo) -> dict[str, list[int | None]]:
    """Count annotated pixels; an absent mask is a gap, never a zero measurement."""
    masks.check_bounds(info.width, info.height, len(info.timestamps_s))
    series = {cell: [None] * len(info.timestamps_s) for cell in masks.colors()}
    for entry in masks.masks:
        series[entry.cell][entry.frame] = sum(end - start for _, start, end in entry.mask)
    return series


def plot(source: Path, annotations: Path, prefix: Path, title: str) -> dict[str, Path]:
    masks = CellMasks.model_validate_json(annotations.read_bytes())
    info = VideoInfo.probe(source)
    series = area_series(masks, info)
    colors = masks.colors()
    times = info.timestamps_s
    outputs = {extension: Path(str(prefix) + '.' + extension)
               for extension in ('png', 'svg', 'html', 'csv', 'provenance.json')}
    for output in outputs.values():
        if output.exists():
            raise FileExistsError(f"Output already exists; choose a fresh prefix: {output}")
        if output.resolve() in (source.resolve(), annotations.resolve()):
            raise ValueError("Output would overwrite an input")
    prefix.parent.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter
    import plotly.graph_objects as go

    with outputs['csv'].open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['cell', 'frame', 'video_time_s', 'area_pixels', 'color'])
        for cell, values in series.items():
            for index, area in enumerate(values):
                writer.writerow([cell, index, times[index], '' if area is None else area, colors[cell]])

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.hashsalt': 'cell-areas'})
    fig, ax = plt.subplots(figsize=(16, 9), facecolor='white')
    for cell, values in series.items():
        ax.plot(times, [float('nan') if area is None else area for area in values],
                color=colors[cell], label=cell, linewidth=1.6, marker='.', markersize=2.8)
    ax.set_title(title, loc='left', fontsize=20, fontweight='bold', pad=20)
    ax.set_xlabel('Video time (s)', labelpad=12)
    ax.set_ylabel('Mask area (pixels)', labelpad=12)
    if times[-1] > times[0]:
        ax.set_xlim(times[0], times[-1])
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='y', color='#e3e6ea', linewidth=0.8)
    ax.set_axisbelow(True)
    if series:
        ax.legend(title='Cell identity', loc='upper left', bbox_to_anchor=(1.02, 1.01),
                  ncol=2, frameon=False, handlelength=2.2, columnspacing=1.3,
                  fontsize=10, title_fontsize=12)
    fig.subplots_adjust(left=0.08, right=0.80, bottom=0.13, top=0.89)
    fig.text(0.08, 0.035, 'Area = annotated mask pixels. Gaps = no saved mask. Colors match the renderer.',
             fontsize=11, color='#555555')
    fig.savefig(outputs['png'], dpi=180, facecolor='white')
    fig.savefig(outputs['svg'], facecolor='white', metadata={'Date': None})
    plt.close(fig)

    interactive = go.Figure()
    for cell, values in series.items():
        interactive.add_trace(go.Scatter(
            x=times, y=values, name=cell, mode='lines+markers',
            line={'color': colors[cell], 'width': 1.6}, marker={'size': 3}, connectgaps=False,
            customdata=list(range(len(times))),
            hovertemplate=(f'<b>{cell}</b><br>Video time: %{{x:.3f}} s<br>Frame: %{{customdata}}'
                           '<br>Area: %{y:,} pixels<extra></extra>'),
        ))
    interactive.update_layout(
        template='plotly_white', title={'text': title},
        xaxis_title='Video time (s)', yaxis_title='Mask area (pixels)',
        yaxis={'rangemode': 'tozero', 'tickformat': ','},
        legend={'title': {'text': 'Cell identity'}, 'itemsizing': 'constant'}, height=800,
        margin={'b': 110, 't': 100}, hovermode='closest',
        annotations=[{'text': 'Gaps = no saved mask. Click a legend entry to hide it; double-click to isolate a cell.',
                      'xref': 'paper', 'yref': 'paper', 'x': 0, 'y': -0.14,
                      'showarrow': False, 'xanchor': 'left'}],
    )
    interactive.write_html(outputs['html'], include_plotlyjs=True, full_html=True,
                           config={'displaylogo': False,
                                   'toImageButtonOptions': {'format': 'svg', 'filename': prefix.name}})
    provenance = {
        'source': str(source), 'source_sha256': hash_file(source),
        'annotations': str(annotations), 'annotation_sha256': hash_file(annotations),
        'title': title, 'time': 'Original source-video timestamps in seconds; not repeated MP4 frames',
        'area': 'sum(x_end - x_start) over saved mask runs', 'missing': 'null / gaps, not zero',
        'cells': len(series), 'frames': len(times), 'mask_measurements': len(masks.masks),
        'colors': colors, 'script': 'scripts/plot-cell-areas.py',
        'script_sha256': hash_file(Path(__file__)),
        'lock_sha256': hash_file(Path(__file__).with_suffix('.py.lock')),
        'outputs': {key: {'file': path.name, 'sha256': hash_file(path)}
                    for key, path in outputs.items() if key != 'provenance.json'},
    }
    outputs['provenance.json'].write_text(json.dumps(provenance, indent=2) + '\n')
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Original source video, not the rendered MP4')
    parser.add_argument('--annotations', required=True, type=Path)
    parser.add_argument('--output-prefix', required=True, type=Path, help='Fresh filename prefix for all five outputs')
    parser.add_argument('--title', default='Cell mask area over time')
    args = parser.parse_args()
    outputs = plot(args.source, args.annotations, args.output_prefix, args.title)
    print(json.dumps({key: str(path) for key, path in outputs.items()}, indent=2))


if __name__ == '__main__':
    main()
