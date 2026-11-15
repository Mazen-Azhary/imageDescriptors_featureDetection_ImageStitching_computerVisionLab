"""Builds the extra report figures for Parts 3, 4 and the bonus from results/ (run part3.py, part4.py and
bonus.py first). Run from the lab folder:  python report/make_figures.py
Writes to results/report/.
"""
import os, sys, textwrap
import numpy as np, cv2, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, 'code'))
import utils
from features import features
from odometry import chain

RES = os.path.join(LAB, 'results')
OUT = os.path.join(RES, 'report')
os.makedirs(OUT, exist_ok=True)
GREEN, RED, GRAY, ORANGE, BLUE = '#1F9E6E', '#E5483B', '#8A8A8A', '#D08C00', '#3B78C4'


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def rgb(path):
    return cv2.imread(path)[..., ::-1]


def row(paths, titles, name, height=3.2, rotate=None):
    """Images side by side at the same height, with titles."""
    ims = [rgb(p) for p in paths]
    if rotate is not None:
        ims = [np.rot90(im) if r else im for im, r in zip(ims, rotate)]
    widths = [im.shape[1] / im.shape[0] for im in ims]
    fig, ax = plt.subplots(1, len(ims), figsize=(height * sum(widths) + 0.3 * len(ims), height + 0.4),
                           gridspec_kw={'width_ratios': widths})
    for a, im, t in zip(np.atleast_1d(ax), ims, titles):
        a.imshow(im); a.set_title(t, fontsize=10); a.axis('off')
    save(fig, name)


def box(ax, x, y, w, h, text, fc, ec, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.08', fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fs)


def arrow(ax, a, b, text='', color='k', rad=0.0, ls='-', fs=9, off=(0, 0.12)):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=12, color=color, lw=1.2, ls=ls,
                                 connectionstyle=f'arc3,rad={rad}'))
    if text:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], text, ha='center', va='center',
                fontsize=fs, color=color)


def chain_diagram():
    """How chaining and the map transform fit together."""
    fig, ax = plt.subplots(figsize=(10, 3.0))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis('off')
    xs = [0.2, 2.2, 4.2, 6.6]
    names = ['frame 0', 'frame 1', 'frame 2', 'frame k']
    for x, n in zip(xs, names):
        box(ax, x, 1.6, 1.3, 0.7, n, '#EEF3FA', BLUE)
    ax.text(5.85, 1.95, '...', fontsize=16, ha='center', va='center')
    for i, lab in enumerate(['H1', 'H2']):
        arrow(ax, (xs[i] + 1.3, 2.1), (xs[i + 1], 2.1), lab, BLUE)
    arrow(ax, (6.15, 2.1), (xs[3], 2.1), 'Hk', BLUE)
    arrow(ax, (xs[3] + 0.3, 1.6), (xs[0] + 1.0, 1.6), 'Tk = Tk-1 · Hk⁻¹   (frame k  →  frame 0)', GREEN,
          rad=-0.25, off=(0, -0.85))
    box(ax, 8.4, 1.6, 1.4, 0.7, 'map canvas', '#F4F4F2', GRAY)
    arrow(ax, (xs[3] + 1.3, 1.95), (8.4, 1.95), '', GRAY)
    ax.text(8.15, 1.25, 'S · Tk', ha='center', fontsize=9, color=GRAY)
    ax.text(5.0, 2.75, 'Each Hk is measured between neighbours (features, ratio test, RANSAC). '
            'A lost step (fewer than 15 inliers) reuses the previous H.', ha='center', fontsize=9, color='#444')
    save(fig, 'fig_chain_diagram.png')


def pose_graph_diagram():
    """Pose graph: frames are nodes, steps and revisits are edges (springs)."""
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.set_xlim(-0.2, 10.2); ax.set_ylim(-0.3, 3.3); ax.axis('off'); ax.set_aspect('equal')
    t = np.linspace(0.25 * np.pi, 2.15 * np.pi, 14)
    P = np.c_[2.6 + 2.0 * np.cos(t), 1.5 + 1.3 * np.sin(t)]
    weak = {5, 6, 7}
    for k in range(len(P) - 1):
        ls, col = (':', BLUE) if k in weak else ('-', GRAY)
        ax.plot(P[k:k + 2, 0], P[k:k + 2, 1], ls=ls, color=col, lw=2)
    for i, j in ((0, 13), (1, 12), (0, 12)):
        ax.plot([P[i, 0], P[j, 0]], [P[i, 1], P[j, 1]], '--', color=ORANGE, lw=1.6)
    ax.scatter(P[:, 0], P[:, 1], s=60, color='white', edgecolor='k', zorder=3)
    ax.scatter(P[:1, 0], P[:1, 1], s=60, color='k', zorder=4)
    ax.text(P[0, 0] + 0.2, P[0, 1] + 0.42, 'frame 0 (fixed to I)', fontsize=8.5, ha='left')
    items = [(GRAY, '-', 'step k → k+1: 8 equations, weight 1'),
             (BLUE, ':', 'lost step: last good H, weight 0.02'),
             (ORANGE, '--', 'revisit i → j: 8 equations, weight 1')]
    for n, (c, ls, s) in enumerate(items):
        y = 2.7 - 0.55 * n
        ax.plot([5.9, 6.6], [y, y], ls=ls, color=c, lw=2)
        ax.text(6.75, y, s, va='center', fontsize=9.5)
    ax.text(5.9, 0.75, 'Unknowns per frame: (a, b, tx, ty) of Tk.\n'
            'Each edge: Tk(p) = Tl(H(p)) at the 4 corners p of frame k.\n'
            'All equations together are solved by linear least squares.', fontsize=9.5, va='center')
    save(fig, 'fig_pose_graph.png')


def inliers_figure():
    """Inliers of every step for the three synthetic flights, lost steps in red. Also saves numbers.json
    (lost steps and revisit counts) for build_report.py."""
    import json
    from loop_closure import revisits
    numbers = {}
    fig, ax = plt.subplots(3, 1, figsize=(10, 6.2), sharey=True)
    for a, fl in zip(ax, ('corniche', 'loop', 'lost_at_sea')):
        F = [features(im) for im in utils.load_frames(utils.flight(fl))]
        _, _, lost, n = chain(F)
        numbers[fl] = {'lost': [int(k) for k in lost],
                       'revisits': None if fl == 'corniche' else len(revisits(F))}
        cols = [RED if k in lost else GREEN for k in range(len(n))]
        a.bar(range(len(n)), n, color=cols, width=1)
        for k in lost:
            a.axvspan(k - 0.5, k + 0.5, color=RED, alpha=.15, lw=0)
        a.axhline(15, color='k', lw=0.8, ls='--')
        a.set_title(f'{fl}: {len(n)} steps, {len(lost)} lost (red), dashed line = 15 inliers', fontsize=10)
        a.set_ylabel('inliers'); a.grid(alpha=.3, axis='y')
    ax[-1].set_xlabel('step k (frame k to frame k + 1)')
    fig.tight_layout()
    save(fig, 'fig_inliers.png')
    with open(os.path.join(OUT, 'numbers.json'), 'w') as f:
        json.dump(numbers, f, indent=1)


def terminal(text, name, width_chars=104):
    lines = text.rstrip('\n').split('\n')
    fig = plt.figure(figsize=(10, 0.165 * len(lines) + 0.3))
    fig.patch.set_facecolor('#1E1E1E')
    fig.text(0.01, 0.98, '\n'.join(l[:width_chars] for l in lines), family='monospace', fontsize=8.2,
             color='#D4D4D4', va='top', ha='left')
    fig.savefig(os.path.join(OUT, name), dpi=150, facecolor='#1E1E1E')
    plt.close(fig)


def main():
    chain_diagram()
    pose_graph_diagram()
    p3, p4 = os.path.join(RES, 'part3'), os.path.join(RES, 'part4')
    with open(os.path.join(LAB, 'report', 'check_output.txt')) as f:
        terminal('$ python check.py 3.1 3.3 4.1 4.2\n\n' + f.read(), 'fig_checks.png')
    row([f'{p3}/q3_3_map_corniche.jpg', f'{p3}/q3_3_map_loop.jpg', f'{p3}/q3_3_map_lost_at_sea.jpg'],
        ['corniche', 'loop', 'lost_at_sea'], 'fig_maps_synthetic.png', height=4.0)
    row([f'{p3}/q3_3_map_vpair.jpg'], ['vpair (200 frames, rotated 90°)'], 'fig_map_vpair.png', height=2.2,
        rotate=[True])
    row([f'{p3}/q3_3_closeup_loop.jpg', f'{p3}/q3_3_closeup_lost_at_sea.jpg'],
        ['loop: where the flight returns to its start', 'lost_at_sea: where it comes back to the coast'],
        'fig_closeups_p3.png', height=3.4)
    row([f'{p4}/q4_1_revisits_loop.png', f'{p4}/q4_1_revisits_lost_at_sea.png'], ['', ''],
        'fig_revisits.png', height=3.6)
    for fl in ('loop', 'lost_at_sea'):
        row([f'{p4}/q4_2_map_{fl}_before.jpg', f'{p4}/q4_2_map_{fl}_after.jpg'],
            [f'{fl}: before (chained)', f'{fl}: after loop closure'], f'fig_maps_p4_{fl}.png', height=3.6)
    row([f'{p4}/q4_2_closeup_loop_before.jpg', f'{p4}/q4_2_closeup_loop_after.jpg',
         f'{p4}/q4_2_closeup_lost_at_sea_before.jpg', f'{p4}/q4_2_closeup_lost_at_sea_after.jpg'],
        ['loop, before', 'loop, after', 'lost_at_sea, before', 'lost_at_sea, after'],
        'fig_closeups_p4.png', height=2.4)
    inliers_figure()
    print('figures in', OUT)


if __name__ == '__main__':
    main()
