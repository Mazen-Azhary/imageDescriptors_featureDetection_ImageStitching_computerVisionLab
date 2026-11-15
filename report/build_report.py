"""Fills Part 3, Part 4 and the bonus of the team report from results/ (run part3.py, part4.py, bonus.py and
report/make_figures.py first). Parts 1 and 2 of the input report are left exactly as they are.

    python report/build_report.py "<input report.docx>" "<output report.docx>"
"""
import os, re, sys, copy, json
import docx
from docx.shared import Inches
from docx.oxml.ns import qn

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(LAB, 'results')
FIG = {'p3': os.path.join(RES, 'part3'), 'p4': os.path.join(RES, 'part4'), 'b': os.path.join(RES, 'bonus'),
       'r': os.path.join(RES, 'report')}


# ------------------------------------------------------------------ numbers from the result tables
def md_table(path):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip().startswith('|')]
    head = [c.strip() for c in lines[0].strip('|').split('|')]
    return head, [[c.strip() for c in l.strip('|').split('|')] for l in lines[2:]]


def num(s):
    return float(s.replace('+', ''))


_, t31 = md_table(f"{FIG['p3']}/q3_1_errors.md")
Q31 = {r[0]: dict(frames=int(r[1]), lost=int(r[2]), mean=num(r[3]), final=num(r[4])) for r in t31}
_, t32 = md_table(f"{FIG['p3']}/q3_2_models.md")
Q32 = {(r[0], r[1]): dict(mean=num(r[2]), final=num(r[3])) for r in t32}
_, t42 = md_table(f"{FIG['p4']}/q4_2_errors.md")
Q42 = {(r[0], r[1]): dict(mean=num(r[2]), final=num(r[3])) for r in t42}
_, tk = md_table(f"{FIG['b']}/bonus_kappa.md")
KAP = {r[0]: dict(best=num(r[1]), gain=num(r[2]), used=num(r[3]), shift=num(r[4])) for r in tk}
_, tb = md_table(f"{FIG['b']}/bonus_models.md")
BON = {(r[0], r[1]): dict(m0=num(r[2]), f0=num(r[3]), m1=num(r[4]), f1=num(r[5])) for r in tb}
with open(f"{FIG['r']}/numbers.json") as f:
    NUMS = json.load(f)


def m(v):
    return f'{v:,.0f} m'


# ------------------------------------------------------------------ document helpers
class Report:
    def __init__(self, path):
        self.doc = docx.Document(path)
        self.body = self.doc.element.body
        self.sect = self.body.find(qn('w:sectPr'))
        ps = {p.text.strip(): p for p in self.doc.paragraphs}
        self.tpl = {
            'h2': ps['Part 3: Odometry and the Map']._p.pPr,
            'h3': ps['Q3.2: Similarity or Homography?']._p.pPr,      # style spacing, no override
            'h4': ps['Results']._p.pPr,
            'body': next(p for p in self.doc.paragraphs if p.text.startswith('What the figure shows'))._p.pPr,
            'bullet': next(p for p in self.doc.paragraphs if p.text.startswith('Blur before differentiating'))._p.pPr,
            'caption': next(p for p in self.doc.paragraphs if p.text.startswith('Figure 1:'))._p.pPr,
            'formula': next(p for p in self.doc.paragraphs if p.text.startswith('R = det(M)'))._p.pPr,
        }
        self.table_tpl = next(t for t in self.doc.tables if t.rows[0].cells[0].text == 'Flight')._tbl
        self.fig_no = 7                                    # Part 1 ends at Figure 7
        self.ref = {}                                      # figure numbers referred to from later sections
        # remove the placeholder text of Parts 3, 4 and the bonus, keep the "Part 3" heading
        start = ps['Part 3: Odometry and the Map']._p
        el = start.getnext()
        while el is not None and el is not self.sect:
            nxt = el.getnext()
            self.body.remove(el)
            el = nxt

    def _p(self, kind):
        p = self.doc.add_paragraph()
        p._p.insert(0, copy.deepcopy(self.tpl[kind]))
        return p

    def _runs(self, p, text, italic=False, color=None):
        """**bold**, _{subscript}, ^{superscript}."""
        for part in re.split(r'(\*\*.+?\*\*|_\{.+?\}|\^\{.+?\})', text):
            if not part:
                continue
            if part.startswith('**'):
                r = p.add_run(part[2:-2]); r.bold = True
            elif part.startswith('_{'):
                r = p.add_run(part[2:-1]); r.font.subscript = True
            elif part.startswith('^{'):
                r = p.add_run(part[2:-1]); r.font.superscript = True
            else:
                r = p.add_run(part)
            if italic:
                r.italic = True
            if color:
                r.font.color.rgb = docx.shared.RGBColor.from_string(color)
        return p

    def h2(self, t): self._runs(self._p('h2'), t)
    def h3(self, t): self._runs(self._p('h3'), t)
    def h4(self, t): self._runs(self._p('h4'), t)
    def para(self, t): self._runs(self._p('body'), t)
    def bullet(self, t): self._runs(self._p('bullet'), t)
    def formula(self, t): self._runs(self._p('formula'), t)

    def figure(self, path, caption, width=5.9):
        p = self._p('caption')
        p.paragraph_format.keep_with_next = True               # the caption stays with its picture
        p.add_run().add_picture(path, width=Inches(width))
        self.fig_no += 1
        self._runs(self._p('caption'), f'Figure {self.fig_no}: {caption}', italic=True, color='555555')
        return self.fig_no

    def table(self, header, rows, widths):
        """A table in the style of the report's data table (shaded header, gray borders)."""
        tbl = copy.deepcopy(self.table_tpl)
        trs = tbl.findall(qn('w:tr'))
        head_tr, body_tr = trs[0], trs[1]
        for tr in trs:
            tbl.remove(tr)
        grid = tbl.find(qn('w:tblGrid'))
        for g in list(grid):
            grid.remove(g)
        total = 9360
        cols = [int(total * w / sum(widths)) for w in widths]
        for c in cols:
            gc = grid.makeelement(qn('w:gridCol'), {qn('w:w'): str(c)})
            grid.append(gc)

        def make_row(tpl_tr, values, bold=False):
            tr = copy.deepcopy(tpl_tr)
            tcs = tr.findall(qn('w:tc'))
            tc_tpl = tcs[0]
            for tc in tcs:
                tr.remove(tc)
            for v, c in zip(values, cols):
                tc = copy.deepcopy(tc_tpl)
                tcw = tc.find(qn('w:tcPr')).find(qn('w:tcW'))
                if tcw is not None:
                    tcw.set(qn('w:w'), str(c)); tcw.set(qn('w:type'), 'dxa')
                ps = tc.findall(qn('w:p'))
                for extra in ps[1:]:
                    tc.remove(extra)
                p = ps[0]
                for r in p.findall(qn('w:r')):
                    p.remove(r)
                para = docx.text.paragraph.Paragraph(p, None)
                self._runs(para, f'**{v}**' if bold and v else str(v))
                tr.append(tc)
            return tr

        tbl.append(make_row(head_tr, header))
        for r in rows:
            tbl.append(make_row(body_tr, r))
        for tr in tbl.findall(qn('w:tr'))[:-1]:                # keep the table on one page
            for p in tr.iter(qn('w:p')):
                docx.text.paragraph.Paragraph(p, None).paragraph_format.keep_with_next = True
        self.sect.addprevious(tbl)
        self._p('body')                                    # spacing after the table, as in Part 1

    def save(self, path):
        self.doc.save(path)


# ------------------------------------------------------------------ the content
def part3(R):
    R.para('Part 3 turns the frame-to-frame matches of Parts 1 and 2 into a flight path and a map. Every step is '
           'the motion between two consecutive frames, found with our Harris corners, oriented descriptors, the '
           'ratio test and RANSAC with the similarity. Our Part 1 features worked well enough, so we did not use '
           'the SIFT fallback.')

    # Q3.1 ---------------------------------------------------------------------------------------------
    R.h3('Q3.1: Chaining the Flight')
    R.h4('The idea')
    R.para('Each step gives a transform H_{k} that takes frame k − 1 to frame k. Frame 0\'s pixel coordinates are '
           'the coordinate system of the whole flight, so for every frame we keep T_{k}, which takes frame-k pixels '
           'to frame-0 pixels. To go from frame k back to frame 0 we first step back to frame k − 1 (the inverse '
           'of H_{k}) and then use T_{k−1}, which we already know:')
    R.formula('T_{0} = I,      T_{k} = T_{k−1} · H_{k}^{−1}')
    f_chain = R.figure(f"{FIG['r']}/fig_chain_diagram.png",
                       'Chaining: each frame is placed with the transform of the frame before it.')
    R.h4('What we implemented')
    R.bullet('**chain() (TODO 3.1).** For every step we call estimate() on frames k − 1 and k, record H_{k} and '
             'its inlier count, and append T_{k−1} · H_{k}^{−1} to the path.')
    R.bullet('**Lost steps.** A step with no plausible fit or fewer than 15 inliers is lost: we record it in '
             'the list of lost steps, store None and 0 inliers, and reuse the motion of the last good step (a constant-velocity '
             'guess, including its rotation). The checks confirm T_{k+1} = T_{k} · H^{−1} exactly and that a lost '
             'step repeats the previous motion.')
    R.h4('Results')
    R.table(['Flight', 'Frames', 'Lost steps', 'Mean error', 'Final error'],
            [[fl, Q31[fl]['frames'], Q31[fl]['lost'], m(Q31[fl]['mean']), m(Q31[fl]['final'])]
             for fl in ('corniche', 'loop', 'lost_at_sea')], [2, 1.2, 1.3, 1.6, 1.6])
    figs = []
    for fl, what in (('corniche', 'corniche (19 km along the coast)'), ('loop', 'loop (41 km, ends at its start)'),
                     ('lost_at_sea', 'lost_at_sea (out over open sea and back)')):
        figs.append(R.figure(f"{FIG['p3']}/q3_1_path_{fl}.png",
                             f'Chained path of {what} against the ground truth (left) and its error against '
                             f'distance flown (right).'))
    f_inl = R.figure(f"{FIG['r']}/fig_inliers.png", 'Inliers of every step. Red steps are lost (fewer than 15 '
                                                    'inliers); the dashed line is the 15-inlier threshold.')
    lost = NUMS['lost_at_sea']['lost']
    R.h4('Discussion')
    R.bullet(f'**Drift grows with distance.** Every step carries a small error (a fraction of a pixel, and a tiny '
             f'rotation), and chaining multiplies all of them. A small rotation error early on bends the rest of the '
             f'path, so the error curves in Figures {figs[0]} and {figs[1]} grow with the distance flown: '
             f'{m(Q31["corniche"]["final"])} after 19 km on corniche and {m(Q31["loop"]["final"])} after 41 km '
             f'on loop, although no step was lost on either flight.')
    R.bullet(f'**Inliers.** Over land a step has hundreds of inliers (Figure {f_inl}). The dips are blurred '
             f'frames and frames over water, where fewer corners survive.')
    R.bullet(f'**lost_at_sea over open sea.** Water has no stable corners and looks different in every frame, so '
             f'the inliers fall to almost zero and steps {lost[0]} to {lost[-1]} ({len(lost)} steps) are lost. '
             f'For all of them chain() repeats the last good motion, which was still turning, so the path keeps '
             f'turning at the same rate and curls into a circle that the aircraft never flew (Figure {figs[2]}). '
             f'The error jumps as soon as the aircraft leaves the coast and is never recovered: when the flight '
             f'finds the coast again it continues from the wrong place, ending {m(Q31["lost_at_sea"]["final"])} '
             f'from the truth. Odometry has no way to notice this; Part 4 fixes it.')

    # Q3.2 ---------------------------------------------------------------------------------------------
    R.h3('Q3.2: Similarity or Homography?')
    R.h4('The idea')
    R.para('Seen from high above, the ground is nearly flat, so Lecture 8 says the motion between two frames is a '
           'homography (8 degrees of freedom), which also models the tilt of the aircraft. A similarity (rotation, '
           'uniform scale and translation, 4 degrees of freedom) ignores the tilt but has half the unknowns. '
           'The Part 3 script chains corniche and loop again with the homography.')
    rows = []
    for fl in ('corniche', 'loop'):
        for mo in ('similarity', 'homography'):
            rows.append([fl, mo, m(Q32[fl, mo]['mean']), m(Q32[fl, mo]['final'])])
    R.table(['Flight', 'Model', 'Mean error', 'Final error'], rows, [2, 2, 1.6, 1.6])
    f_pl = R.figure(f"{FIG['p3']}/q3_2_paths_loop.png", 'loop chained with the similarity and with the homography.')
    f_rad = R.figure(f"{FIG['p3']}/q3_2_error_vs_radius.png",
                     'Error of each match (distance from its second point to where the ground truth maps its '
                     'first point) against the distance of its first point from the image center.')
    R.ref['radius'] = f_rad
    R.h4('Discussion')
    cs, ch = Q32['corniche', 'similarity'], Q32['corniche', 'homography']
    ls_, lh = Q32['loop', 'similarity'], Q32['loop', 'homography']
    cw = 'homography' if ch['mean'] < cs['mean'] else 'similarity'
    lw = 'homography' if lh['mean'] < ls_['mean'] else 'similarity'
    R.bullet(f'**corniche:** the {cw} drifts less ({m(min(cs["mean"], ch["mean"]))} against '
             f'{m(max(cs["mean"], ch["mean"]))} mean error)'
             + (', as Lecture 8 predicts.' if cw == 'homography' else ', which is not what Lecture 8 predicts.'))
    extra = ''
    if (lh['final'] < ls_['final']) != (lw == 'homography'):
        extra = (f' Its final error happens to be {"lower" if lw == "similarity" else "higher"} '
                 f'({m(lh["final"])} against {m(ls_["final"])}) only because the homography path crosses back '
                 f'near the truth at the end (Figure {f_pl}); over the whole flight it is clearly worse.')
    R.bullet(f'**loop:** the {lw} drifts less ({m(min(ls_["mean"], lh["mean"]))} against '
             f'{m(max(ls_["mean"], lh["mean"]))} mean error)'
             + (', as Lecture 8 predicts.' if lw == 'homography' else
                ', the opposite of what Lecture 8 predicts.') + extra)
    R.bullet(f'**The match-error plots (Figure {f_rad}) explain it.** On corniche the error stays flat at about '
             f'half a pixel across the frame: the camera is an ideal pinhole camera, the only model error is the '
             f'tilt, and the homography captures it. On loop the error grows with the distance from the center, '
             f'to about 2 px at the border for consecutive frames and about 9 px for frames 3 and 132, which see '
             f'the same ground at very different positions in the frame. That is the signature of **radial lens '
             f'distortion**: the camera that filmed loop bends straight lines, more strongly near the border.')
    R.bullet('**Why the homography loses on loop.** Distortion is not a homography. With 8 free parameters, the '
             'homography absorbs part of it as fake perspective (tilt) terms that differ from step to step, and '
             'chaining 137 steps compounds them. The similarity is too rigid to fit the distortion, so it is less '
             'affected. The flat-ground argument of Lecture 8 only holds for an ideal camera; the bonus confirms '
             'this by removing the distortion.')

    # Q3.3 ---------------------------------------------------------------------------------------------
    R.h3('Q3.3: The Map')
    R.h4('The idea and what we implemented')
    R.para('Putting every frame into frame 0\'s coordinates gives a map. The given code computes the canvas, the '
           'transform S (a scale and a shift) that takes frame 0 onto it, and which frame owns each map pixel (the '
           'frame in which that pixel lies farthest from the border).')
    R.bullet('**make_map() (TODO 3.3).** Each frame is warped onto the canvas with cv2.warpPerspective using '
             'S · T_{k}: T_{k} takes it to frame 0 and S takes frame 0 to the map. The warped frame is fed to '
             'OpenCV\'s multiband blender together with the mask of the map pixels it owns, so the seams between '
             'frames are blended across several frequency bands (as in Assignment 1).')
    f_maps = R.figure(f"{FIG['r']}/fig_maps_synthetic.png", 'Maps of the three synthetic flights, built from '
                                                            'the chained paths (similarity).')
    R.figure(f"{FIG['r']}/fig_map_vpair.png", f'Map of the real vpair flight: 200 frames over forest, suburbs, '
                                              f'fields and the Rhine.', width=6.5)
    f_cl = R.figure(f"{FIG['r']}/fig_closeups_p3.png", 'Close-ups: where loop returns to its start (left) and '
                                                       'where lost_at_sea comes back to the coast (right).',
                    width=5.6)
    R.h4('Discussion')
    R.para('Locally the maps look right: consecutive frames are consistent, so roads, the coast and the lakes '
           'continue smoothly and the blender hides the exposure changes between frames. The problems appear '
           f'where the flight sees the same ground twice (Figure {f_cl}):')
    R.bullet(f'**loop:** the last frames should land exactly on the first ones, but after 41 km of drift they are '
             f'about {m(Q31["loop"]["final"])} away. Two different places are blended on top of each other, so '
             f'streets are doubled, ghosted and smeared where the old and the new frames meet.')
    R.bullet(f'**lost_at_sea:** after the lost steps over the sea, the frames that see the coast again are placed '
             f'about {m(Q31["lost_at_sea"]["final"])} from where they belong, so the coastline is cut and '
             f'repeated: the coast seen on the way out and on the way back do not line up.')
    R.para('The cause is the same in both: chaining only ever compares neighbours, so nothing tells it that the new '
           'frames show ground it has already mapped. That is exactly the information Part 4 adds.')


def part4(R):
    R.h2('Part 4: Loop Closure')
    R.para('Every step of Q3.1 carries a small error and chaining adds them all up. The drift is invisible while '
           'the flight covers new ground, but it shows when the flight returns to ground it has seen: the old and '
           'the new frames should show the same streets in the same place, and they do not. Loop closure finds '
           'those returns and uses them to correct the whole flight at once.')

    R.h3('Q4.1: Finding Revisits')
    R.h4('What we implemented')
    R.bullet('**Keyframes.** Every third frame (0, 3, 6, ...) is a keyframe, which cuts the number of pairs to try '
             'by about nine without missing returns: neighbouring frames overlap almost completely.')
    R.bullet('**revisits() (TODO 4.1).** For each keyframe j we try every keyframe i at least 30 frames earlier '
             '(so that neighbours do not count as revisits) and fit a similarity from frame i to frame j with our '
             'matching and RANSAC.')
    R.bullet('**Acceptance.** A pair needs at least 40 inliers, much stricter than the 15 of a step: a false '
             'revisit would tie two different places together and bend the whole map. For each j we keep only the '
             'partner with the most inliers.')
    rl, rs = NUMS['loop']['revisits'], NUMS['lost_at_sea']['revisits']
    f_rev = R.figure(f"{FIG['r']}/fig_revisits.png", 'Accepted revisits drawn on the chained paths of loop (left) '
                                                     'and lost_at_sea (right).', width=6.0)
    R.h4('Results')
    R.table(['Flight', 'Accepted revisits'], [['loop', rl], ['lost_at_sea', rs]], [2, 2])
    R.para(f'loop has {rl} revisits: the end of the flight overlaps its start, and the two long legs through the city '
           f'see each other (frames about 3 km apart still overlap, since each frame covers about 6 km of ground). '
           f'lost_at_sea has {rs}, all between the way out and the way back along the coast; over open sea there is '
           f'nothing to match, so no revisit can link the frames there.')

    R.h3('Q4.2: Correcting the Whole Flight')
    R.h4('The idea: a pose graph')
    R.para('Each frame gets 4 unknowns (a_{k}, b_{k}, t_{x,k}, t_{y,k}), the similarity that places it in frame 0\'s '
           'coordinates:')
    R.formula('T_{k}(p) = [ a_{k}  −b_{k} ; b_{k}  a_{k} ] p + [ t_{x,k} ; t_{y,k} ]')
    R.para('Every measured transform H from frame k to frame l (a step of Q3.1 or a revisit of Q4.1) says that a '
           'point p of frame k and the point H(p) of frame l show the same spot on the ground, so the map must put '
           'them in the same place:')
    R.formula('T_{k}(p) = T_{l}(H(p))')
    f_pg = R.figure(f"{FIG['r']}/fig_pose_graph.png", 'The pose graph: frames are nodes, steps and revisits are '
                                                      'edges. Least squares finds the poses that satisfy all edges '
                                                      'as well as possible.')
    R.para(f'The frames are the nodes of a graph and every measurement is an edge (Figure {f_pg}). One can think of '
           f'each edge as a spring: chaining laid the springs end to end, so every error piled up at the end; '
           f'solving all the equations together lets every spring stretch a little, so the error is spread over '
           f'the whole flight instead.')
    R.h4('What we implemented')
    R.bullet('**measurement_rows() (TODO 4.2).** With p = (x, y) and H(p) = (u, v), the equation T_{k}(p) = '
             'T_{l}(H(p)) gives, after moving everything to one side, one equation per coordinate, both linear in '
             'the unknowns:')
    R.formula('x:   a_{k}·x − b_{k}·y + t_{x,k} − a_{l}·u + b_{l}·v − t_{x,l} = 0')
    R.formula('y:   b_{k}·x + a_{k}·y + t_{y,k} − b_{l}·u − a_{l}·v − t_{y,l} = 0')
    R.para('We write these coefficients in the columns of frames k and l, at each of the four corners of frame k, '
           'so each measurement adds 8 equations. The similarity is what keeps the problem linear: a homography '
           'divides by its last row and would not be.')
    R.bullet('**correct() (given).** Stacks the equations of every step and every revisit, adds the equations of '
             'the last good step for each lost step with all coefficients multiplied by 0.02, fixes frame 0 to the '
             'identity (otherwise the whole map could slide or turn freely) and solves by linear least squares.')
    R.h4('Results')
    rows = []
    for fl in ('loop', 'lost_at_sea'):
        for pa, lab in (('chained', 'before (chained)'), ('loop closure', 'after loop closure')):
            rows.append([fl, lab, m(Q42[fl, pa]['mean']), m(Q42[fl, pa]['final'])])
    R.table(['Flight', 'Path', 'Mean error', 'Final error'], rows, [2, 2.4, 1.6, 1.6])
    f_pl = R.figure(f"{FIG['p4']}/q4_2_path_loop.png", 'loop before and after loop closure, against the truth.')
    f_ps = R.figure(f"{FIG['p4']}/q4_2_path_lost_at_sea.png", 'lost_at_sea before and after loop closure.')
    f_ml = R.figure(f"{FIG['r']}/fig_maps_p4_loop.png", 'Map of loop before (left) and after (right) loop closure.',
                    width=5.0)
    f_ms = R.figure(f"{FIG['r']}/fig_maps_p4_lost_at_sea.png", 'Map of lost_at_sea before (left) and after (right) '
                                                               'loop closure.', width=4.4)
    f_cu = R.figure(f"{FIG['r']}/fig_closeups_p4.png", 'Close-ups of where each flight returns to known ground, '
                                                       'before and after loop closure.')
    lb, la = Q42['loop', 'chained'], Q42['loop', 'loop closure']
    sb, sa = Q42['lost_at_sea', 'chained'], Q42['lost_at_sea', 'loop closure']
    R.h4('Discussion')
    R.bullet(f'**loop.** The mean error falls from {m(lb["mean"])} to {m(la["mean"])} and the final error from '
             f'{m(lb["final"])} to {m(la["final"])}. The corrected path follows the truth over the whole flight '
             f'(Figure {f_pl}), and in the close-up (Figure {f_cu}) the streets where the flight returns to its start '
             f'now line up instead of being doubled.')
    R.bullet(f'**lost_at_sea.** The mean error falls from {m(sb["mean"])} to {m(sa["mean"])} and the final error '
             f'from {m(sb["final"])} to {m(sa["final"])}. Everything that the revisits can see is pulled back into '
             f'place: the way back along the coast now lies on the way out, and the coastline in the close-up is '
             f'continuous. The stretch over open sea is still a guess (Figure {f_ps}): no measurement exists there, '
             f'so loop closure can only bend it, not measure it.')
    R.bullet('**What the 0.02 equations do on lost_at_sea.** A lost step has no measured H. Without any equation '
             'there, the graph would split into two pieces (before and after the sea) that could move freely '
             'against each other, and the least-squares problem would have no unique solution. The equations of '
             'the last good step keep the two pieces connected with a constant-motion guess, but at weight 0.02 '
             '(0.0004 in the squared error) they are weak springs: they decide the shape of the path only where '
             'nothing else does, and give way as soon as the strong step and revisit equations disagree with them. '
             'So the revisits near the coast place the second half of the flight where it really is, and the whole '
             'correction is absorbed by the stretch over the sea, where the guess was wrong anyway. In Part 3 the '
             'same guess was trusted completely, which produced the circle.')


def sanity(R):
    R.h4('Sanity checks of Parts 3 and 4')
    R.figure(f"{FIG['r']}/fig_checks.png", 'Output of python check.py 3.1 3.3 4.1 4.2: every check passes.')


def bonus(R):
    R.h2('Bonus: Fix the Camera')
    kl, kc = KAP['loop'], KAP['corniche']
    R.h4('The model')
    R.para('Q3.2 showed that the camera of loop has radial distortion. We model it as in the handout: an ideal '
           'point p appears in the frame at')
    R.formula('p_{d} = c + (p − c) · (1 + κ |p − c|^{2} / 600^{2})')
    R.para('where c is the image center. κ < 0 is barrel distortion (points are pulled toward the center), κ > 0 '
           'pincushion. We wrote it as a script of our own, code/bonus.py, which uses only our own matches to find '
           'κ; the ground truth is used only to score the results, as in the part scripts.')
    R.h4('Finding κ from our own matches')
    R.bullet('**The idea.** The ground is flat, so for an ideal camera the motion between two frames is exactly a '
             'homography. With the right κ, undistorting the matched corners makes a homography fit them best.')
    R.bullet('**The cost.** For a candidate κ we undistort the corners of 34 pairs of frames (k, k + 2) by inverting '
             'the model (a fixed-point iteration), fit a homography with our matching and RANSAC, and take the '
             'median distance between where it maps each corner and its match. The cost is the mean of the '
             'medians over the pairs.')
    R.bullet('**The search.** A coarse grid from −0.3 to 0.3 (step 0.05) and then a fine grid (step 0.005) around '
             'the best value. We keep κ = 0 unless the best κ lowers the cost by at least 5%: a flat curve means '
             'there is no distortion that the matches can measure, and undistorting with a noise value would only '
             'hurt.')
    R.table(['Flight', 'Minimum of the curve', 'Cost reduction vs κ = 0', 'κ used', 'Shift at the frame corner'],
            [['corniche', f'{kc["best"]:+.3f}', f'{kc["gain"]:.1f}%', f'{kc["used"]:+.3f}', f'{kc["shift"]:.1f} px'],
             ['loop', f'{kl["best"]:+.3f}', f'{kl["gain"]:.1f}%', f'{kl["used"]:+.3f}', f'{kl["shift"]:.1f} px']],
            [1.4, 1.8, 2.0, 1.2, 2.0])
    f_k = R.figure(f"{FIG['b']}/bonus_kappa_search.png", 'The cost against κ for corniche and loop.', width=4.8)
    R.para(f'The loop curve in Figure {f_k} has a clear minimum at κ = {kl["used"]:+.3f} ({kl["gain"]:.0f}% lower '
           f'than κ = 0): barrel distortion that moves the frame corners by about {kl["shift"]:.0f} px. The corniche '
           f'curve is flat (only {kc["gain"]:.1f}% gain), so its camera is ideal, which agrees with its flat '
           f'match-error plot in Q3.2 (Figure {R.ref["radius"]}).')
    R.h4('Undistorting the frames')
    R.para('Every frame is resampled with cv2.remap: each pixel p of the undistorted frame reads the original '
           'frame at p_{d}.')
    R.figure(f"{FIG['b']}/bonus_undistort_loop.png", 'A loop frame as filmed, undistorted, and the distortion '
                                                     'shift at each point (arrows magnified 4 times).')
    f_r = R.figure(f"{FIG['b']}/bonus_error_vs_radius.png", 'The match-error plots of Q3.2 repeated on the '
                                                            'undistorted frames.')
    R.para(f'After undistortion the match errors of loop no longer grow toward the border (Figure {f_r}): for '
           f'frames 3 and 132 the error at the border falls from about 9 px to about 1 px, the same level as '
           f'corniche.')
    R.h4('Q3.2 again: which model wins now?')
    rows = []
    for fl in ('corniche', 'loop'):
        for mo in ('similarity', 'homography'):
            b = BON[fl, mo]
            rows.append([fl, mo, m(b['m0']), m(b['m1']), m(b['f0']), m(b['f1'])])
    R.table(['Flight', 'Model', 'Mean before', 'Mean after', 'Final before', 'Final after'], rows,
            [1.5, 1.6, 1.5, 1.5, 1.5, 1.5])
    f_bp = R.figure(f"{FIG['b']}/bonus_paths_loop.png", 'Undistorted loop chained with both models.')
    hs, hh = BON['loop', 'similarity'], BON['loop', 'homography']
    win = 'homography' if hh['m1'] < hs['m1'] else 'similarity'
    R.bullet(f'**loop:** with the distortion removed, the {win} wins clearly: {m(hh["m1"])} mean and '
             f'{m(hh["f1"])} final error for the homography, against {m(hs["m1"])} and {m(hs["f1"])} for the '
             f'similarity (Figure {f_bp}). The homography improves from {m(hh["m0"])} to {m(hh["m1"])} mean error, '
             f'because its 8 parameters now only have to model the real tilt of the aircraft. The similarity does '
             f'not improve, because it cannot model the tilt either way.')
    R.bullet('**corniche:** κ = 0, so its frames and results are unchanged; the homography already won there.')
    R.para('With an ideal camera the homography is the better model on both flights, which is what Lecture 8 '
           'predicts. The result of Q3.2 on loop was caused by the lens, not by the motion model.')


def main():
    src, dst = sys.argv[1], sys.argv[2]
    R = Report(src)
    part3(R)
    part4(R)
    sanity(R)
    bonus(R)
    R.save(dst)
    print('wrote', dst, '- figures up to', R.fig_no)


if __name__ == '__main__':
    main()
