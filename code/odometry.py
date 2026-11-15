"""Q3.1: chaining the flight.

You fill in the block marked TODO. Everything else already runs.
Check your work with:  python check.py 3.1
"""
import numpy as np, cv2
from fitting import estimate
import fitting                                               # added: to reach Part 2's estimate() and plausible()
from features import match                                   # added: our Part 1 matcher, used only by the fallback


# ===================================================================== temporary fallback for Part 2
# TEMPORARY: OpenCV is used here ONLY while Part 2 (fitting.py: fit_similarity, fit_homography, ransac) is unfinished.
# This estimate() replaces the one imported above, so the given line in chain() calls it without any change.
# It ALWAYS calls Part 2's fitting.estimate() first. If that returns data, we return it exactly as it is and the
# OpenCV functions below are NEVER used. Only if Part 2 still raises NotImplementedError do we fall back to
# OpenCV's RANSAC, and we return the same (H, n_inliers, (p_inliers, q_inliers)) that fitting.estimate() returns.
# The assignment bans OpenCV's transform estimators in the submitted code: delete this block once Part 2 passes.
def estimate(F1, F2, model='similarity', thresh=3.0):
    try:
        return fitting.estimate(F1, F2, model, thresh)       # Part 2 is done: use it, no OpenCV
    except NotImplementedError:
        pass                                                 # Part 2 not done yet: fall back to OpenCV below
    (k1, d1), (k2, d2) = F1, F2
    mm = match(d1, d2)                                       # same matches as fitting.estimate() would use
    if len(mm) < 8:                                          # same rule as fitting.estimate()
        return None, 0, None
    p, q = k1[mm[:, 0]], k2[mm[:, 1]]
    P, Q = p.astype(np.float32), q.astype(np.float32)
    if model == 'similarity':                                # OpenCV returns a (2, 3) matrix and an inlier mask
        A, mask = cv2.estimateAffinePartial2D(P, Q, method=cv2.RANSAC, ransacReprojThreshold=thresh,
                                              maxIters=5000, confidence=0.99)
        T = None if A is None else np.vstack([A, [0, 0, 1.0]])  # (2, 3) -> (3, 3)
    else:                                                    # OpenCV returns a (3, 3) matrix and an inlier mask
        T, mask = cv2.findHomography(P, Q, cv2.RANSAC, thresh, maxIters=5000, confidence=0.99)
    if T is None or not fitting.plausible(T, homography=(model != 'similarity')):
        return None, 0, None                                 # same "no plausible fit" answer as Part 2
    inl = mask.ravel().astype(bool)
    return T / T[2, 2], int(inl.sum()), (p[inl], q[inl])     # same (H, n, _) shape as fitting.estimate()


def chain(F, model='similarity', min_inliers=15):
    """Chain the transforms between consecutive frames into one path.

    Args:
        F: features of every frame, [(keypoints, descriptors), ...].
        model: 'similarity' or 'homography'.
        min_inliers: a step with fewer inliers than this is lost.

    Returns:
        T: list of N (3, 3) transforms; T[k] takes frame-k pixels to frame-0 pixels, and T[0] is the identity.
        steps: list of N - 1 transforms; steps[k] takes frame k to frame k + 1, or is None if that step was lost.
        lost: list of the indices k of the lost steps.
        n_inliers: list of N - 1 inlier counts, 0 for a lost step.
    """
    T, steps, lost, n_inliers = [np.eye(3)], [], [], []
    last = np.eye(3)                                    # the motion of the last step that was not lost
    for k in range(1, len(F)):
        H, n, _ = estimate(F[k - 1], F[k], model)       # H takes frame k - 1 to frame k
        # ------------------------------------------------------------ TODO 3.1 -----
        # A step is lost when H is None or n < min_inliers: record k - 1 in `lost`, None in `steps` and 0 in
        # `n_inliers`, and use `last` as its motion. Otherwise record H and n, and remember H in `last`.
        # Then append T_k = T_{k-1} M^-1 to T, where M is the step's motion: H, or `last` for a lost step.
        if H is None or n < min_inliers:               # lost step: no fit, or too few matches to trust it
            lost.append(k - 1)                         # step k-1 is the one from frame k-1 to frame k
            steps.append(None)
            n_inliers.append(0)
            M = last                                   # assume the plane kept moving like last time
        else:                                          # good step
            steps.append(H)
            n_inliers.append(n)
            last = H                                   # remember it in case the next step is lost
            M = H
        T.append(T[-1] @ np.linalg.inv(M))             # T_k = T_{k-1} M^-1   (frame k -> k-1 -> 0)
        # ------------------------------------------------------------ end TODO -----
    return T, steps, lost, n_inliers
