"""Bonus: fix the camera of loop (and lost_at_sea).

Model (handout): an ideal point p appears in the frame at
    p_d = c + (p - c) * (1 + kappa * |p - c|^2 / 600^2),    c = the image center.

1. Find kappa from our own matches, without the ground truth: for each candidate kappa, undistort the
   keypoints of many frame pairs, fit a homography with our RANSAC (estimate()), and measure how well it
   explains the matches (median residual). On flat ground the right kappa makes a homography fit exactly.
2. Undistort every frame with cv2.remap.
3. Repeat Q3.2 on the undistorted frames: chain corniche and loop with the similarity and the homography.
The ground truth is used only to score the results (gt.py), as in the part scripts.

    python bonus.py            (add --sift to use the SIFT fallback, as in part3.py; run part3.py first)

Writes to results/bonus/:
    bonus_kappa.md, bonus_kappa_search.png    the kappa of each flight and the cost curve it minimizes
    bonus_undistort_loop.png                  a loop frame before and after undistortion, and the correction
    bonus_error_vs_radius.png                 the match-error plots of Q3.2 after undistortion
    bonus_models.md                           Q3.2 again: both models, before and after undistortion
    bonus_paths_loop.png                      both models on undistorted loop, against the truth
"""
import os, sys
import numpy as np, cv2, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import utils, gt, viz
from utils import apply
from features import features, features_sift, match
from odometry import chain, estimate

R0 = 600.0                                   # the radius in the handout's model
C = np.array([320.0, 240.0])                 # image center of the 640 x 480 synthetic frames
MIN_GAIN = 0.05                              # keep kappa = 0 unless it explains the matches 5% better


def distort(p, kappa):
    """Where an ideal point p appears in the frame (the handout's model)."""
    d = p - C
    return C + d * (1 + kappa * (d ** 2).sum(1, keepdims=True) / R0 ** 2)


def undistort_points(pd, kappa, iters=20):
    """Invert distort() by fixed-point iteration: p = c + (p_d - c) / (1 + kappa |p - c|^2 / 600^2)."""
    d = pd - C
    p = d.copy()
    for _ in range(iters):
        p = d / (1 + kappa * (p ** 2).sum(1, keepdims=True) / R0 ** 2)
    return C + p


def undistort_image(img, kappa):
    """The frame an ideal camera would have taken: each output pixel p reads the input at distort(p)."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    pd = distort(np.c_[xx.ravel(), yy.ravel()].astype(np.float64), kappa)
    mx = pd[:, 0].reshape(h, w).astype(np.float32)
    my = pd[:, 1].reshape(h, w).astype(np.float32)
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def kappa_cost(F, pairs, mms, kappa):
    """Mean over the pairs of the median residual (px) of a homography fitted to undistorted matches."""
    costs = []
    for (i, j), mm in zip(pairs, mms):
        Fi = (undistort_points(F[i][0], kappa), F[i][1])
        Fj = (undistort_points(F[j][0], kappa), F[j][1])
        H, n, _ = estimate(Fi, Fj, 'homography')
        if H is None or len(mm) == 0:
            continue
        e = np.linalg.norm(apply(H, Fi[0][mm[:, 0]]) - Fj[0][mm[:, 1]], axis=1)
        costs.append(np.median(e))
    return float(np.mean(costs))


def find_kappa(F):
    """Coarse grid, then a fine grid around the best value. Returns kappa and the (kappa, cost) samples."""
    pairs = [(k, k + 2) for k in range(0, len(F) - 2, 4)]
    mms = [match(F[i][1], F[j][1]) for i, j in pairs]
    samples = {}
    for k in np.round(np.arange(-0.3, 0.3001, 0.05), 4):
        samples[float(k)] = kappa_cost(F, pairs, mms, k)
    best = min(samples, key=samples.get)
    for k in np.round(np.arange(best - 0.05, best + 0.0501, 0.005), 4):
        if float(k) not in samples:
            samples[float(k)] = kappa_cost(F, pairs, mms, k)
    best = min(samples, key=samples.get)
    gain = (samples[0.0] - samples[best]) / samples[0.0]  # how much better than an ideal camera (kappa = 0)
    if gain < MIN_GAIN:                                    # a flat curve: no distortion we can measure
        best = 0.0
    return best, sorted(samples.items()), gain


def main():
    out = utils.results_dir('bonus')
    feat = features_sift if '--sift' in sys.argv else features
    old = utils.results_dir('part3')
    kap, curves, gains, F, Fu, imgs = {}, {}, {}, {}, {}, {}

    # 1. kappa of each flight, from our own matches
    for fl in ('corniche', 'loop'):
        print(f'... {fl}: features and kappa search', flush=True)
        imgs[fl] = utils.load_frames(utils.flight(fl))
        F[fl] = [feat(im) for im in imgs[fl]]
        kap[fl], curves[fl], gains[fl] = find_kappa(F[fl])
        print(f'    kappa = {kap[fl]:+.3f} (residual {100 * gains[fl]:.1f}% lower than with kappa = 0)')
    utils.table(f'{out}/bonus_kappa.md', ['flight', 'best kappa on the curve', 'residual gain over kappa = 0 (%)',
                                          'kappa used', 'shift at the frame corner (px)'],
                [[fl, f'{min(curves[fl], key=lambda s: s[1])[0]:+.3f}', float(100 * gains[fl]),
                  f'{kap[fl]:+.3f}', float(abs(kap[fl]) * 400 ** 3 / R0 ** 2)] for fl in kap])

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for fl, colr in (('corniche', viz.GRAY), ('loop', viz.GREEN)):
        k, c = np.array(curves[fl]).T
        ax.plot(k, c, '-o', ms=3, color=colr,
                label=f'{fl}: minimum at {k[np.argmin(c)]:+.3f}, {100 * gains[fl]:.1f}% below kappa = 0, '
                      f'kappa used {kap[fl]:+.3f}')
        ax.axvline(kap[fl], color=colr, ls=':', lw=1)
    ax.set_xlabel('kappa'); ax.set_ylabel('median residual of the homography (px)')
    ax.set_title('Finding kappa from our own matches'); ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.savefig(f'{out}/bonus_kappa_search.png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # 2. undistort every frame; picture of one loop frame and of the correction
    k = kap['loop']
    col = utils.load_frames(utils.flight('loop'), color=True)[20]
    und = undistort_image(col, k)
    yy, xx = np.mgrid[20:480:40, 20:640:40]
    p = np.c_[xx.ravel(), yy.ravel()].astype(float)
    d = distort(p, k) - p
    fig, ax = plt.subplots(1, 3, figsize=(15, 3.9))
    ax[0].imshow(col[..., ::-1]); ax[0].set_title('loop frame 20, as filmed')
    ax[1].imshow(und[..., ::-1]); ax[1].set_title(f'undistorted (kappa = {k:+.3f})')
    ax[2].imshow(np.ones((480, 640)), cmap='gray', vmin=0, vmax=1)
    ax[2].quiver(p[:, 0], p[:, 1], d[:, 0], d[:, 1], np.linalg.norm(d, axis=1), angles='xy',
                 scale_units='xy', scale=0.25, cmap='viridis')
    ax[2].set_xlim(0, 640); ax[2].set_ylim(480, 0)
    ax[2].set_title(f'distortion shift (arrows x4), up to {np.linalg.norm(d, axis=1).max():.1f} px')
    for a in ax:
        a.axis('off')
    fig.savefig(f'{out}/bonus_undistort_loop.png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # 3. Q3.2 again on the undistorted frames
    rows, Tu = [], {}
    for fl in ('corniche', 'loop'):
        print(f'... {fl}: undistort, features, chain with both models', flush=True)
        Fu[fl] = [feat(undistort_image(im, kap[fl])) for im in imgs[fl]]
        for model in ('similarity', 'homography'):
            Tu[fl, model], _, _, _ = chain(Fu[fl], model)
            e0 = gt.path_errors(utils.flight(fl), list(np.load(f'{old}/T_{fl}_{model}.npy')))
            e1 = gt.path_errors(utils.flight(fl), Tu[fl, model])
            rows.append([fl, model, float(e0.mean()), float(e0[-1]), float(e1.mean()), float(e1[-1])])
    print('\nBonus  Q3.2 before and after undistortion')
    utils.table(f'{out}/bonus_models.md', ['flight', 'model', 'mean error before (m)', 'final error before (m)',
                                           'mean error after (m)', 'final error after (m)'], rows)
    viz.plot_paths(utils.flight('loop'), {'similarity': Tu['loop', 'similarity'],
                                          'homography': Tu['loop', 'homography']}, f'{out}/bonus_paths_loop.png')
    pairs = []
    for fl, i, j in (('corniche', 20, 21), ('loop', 20, 21), ('loop', 3, 132)):
        (k1, d1), (k2, d2) = Fu[fl][i], Fu[fl][j]
        mm = match(d1, d2)
        pairs.append((f'{fl}, frames {i} and {j} (undistorted)', k1[mm[:, 0]], k2[mm[:, 1]],
                      gt.gt_H(utils.flight(fl), i, j)))
    viz.plot_error_vs_radius(pairs, f'{out}/bonus_error_vs_radius.png')
    print(f'\nEverything is in {os.path.relpath(out)}')


if __name__ == '__main__':
    utils.run(main)
