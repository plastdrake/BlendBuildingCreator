"""
Valley flashing for wing-to-main roof junctions (cross-hipped U/L, T intersections).

Research notes (carpentry framing guides):
- Valleys bisect *inside* corners; hips bisect *outside* corners (45 deg plan for
  equal-pitch 90 deg junctions).
- Secondary ridges join the main ridge at equal height (L = one valley, T = two),
  or die into the main slope at lower height for unequal spans.
- Valley rafters are structural (deeper section than commons) and carry jack
  rafters from both planes; open valleys get wide metal flashing run under the
  shingle edges, extended well past the valley foot over the eaves.

Because our bell-cast decks sag below a straight foot-to-apex chord, a single
straight board floats above mid-valley and leaves the stepped notch edges
exposed. These segmented strips instead sample both deck surfaces along the
valley plan line and ride max(deck) + lift, so every slit is covered.
"""

import math
from mathutils import Vector, Matrix
from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_TIMBER


def deck_top_z(x, y, cx, half_w, z_base, roof_h, flare, sway, ry_min, ry_max, ez, top_off=0.05):
    """Replicates the builder deck-top surface height (no bmesh needed)."""
    u = min(1.0, max(0.0, abs(x - cx) / max(0.001, half_w)))
    drop = (1.0 - flare) * u + flare * (1.0 - (1.0 - u) ** 2)
    span = max(0.001, ry_max - ry_min)
    t = max(0.0, min(1.0, (y - ry_min) / span))
    sag = math.sin(t * math.pi) * sway
    rz = z_base + roof_h - sag
    return rz - drop * (rz - ez) + top_off


def build_valley_strip(bm, foot_xy, apex_xy, main_fn, wing_fn, width=0.45,
                       thickness=0.05, lift=0.03, segs=7, foot_extend=0.35,
                       mat_index=MAT_INDEX_TIMBER):
    """Builds a segmented flashing strip along a valley plan line.

    foot_xy/apex_xy: 2D plan endpoints. main_fn/wing_fn: callables (x, y) -> deck
    top z in world coords. The strip rides max(main, wing) + lift per sample and
    extends past the foot over the eave to cap the corner.
    """
    fx, fy = foot_xy
    ax, ay = apex_xy
    dx, dy = ax - fx, ay - fy
    plan_len = math.hypot(dx, dy)
    if plan_len < 0.3:
        return
    ux, uy = dx / plan_len, dy / plan_len

    # Sample from slightly past the foot (over the eave) to the apex.
    pts = []
    total = plan_len + foot_extend
    for i in range(segs + 1):
        s = -foot_extend + (total * i / segs)
        px = fx + ux * s
        py = fy + uy * s
        try:
            mz = main_fn(px, py)
        except Exception:
            mz = -1e9
        try:
            wz = wing_fn(px, py)
        except Exception:
            wz = -1e9
        pz = max(mz, wz) + lift
        pts.append(Vector((px, py, pz)))

    for i in range(segs):
        p0 = pts[i]
        p1 = pts[i + 1]
        seg = p1 - p0
        seg_len = seg.length
        if seg_len < 0.05:
            continue
        mid = (p0 + p1) * 0.5
        rot_z = math.atan2(seg.y, seg.x)
        horiz = math.hypot(seg.x, seg.y)
        pitch = -math.atan2(seg.z, max(1e-5, horiz))
        rot_mat = Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y')
        create_beveled_box(
            bm,
            size=(seg_len + 0.06, width, thickness),
            location=mid,
            rotation=rot_mat.to_euler(),
            mat_index=mat_index,
            bevel_amount=0.008
        )


def build_valley_rafters(bm, foot_xy, apex_xy, main_fn, wing_fn, beam_w=0.24,
                         beam_h=0.22, segs=8, foot_extend=0.14, apex_extend=0.10,
                         embed=0.04, mat_index=MAT_INDEX_TIMBER):
    """Single central structural valley beam running down the roof seam.

    Samples max(main, wing) deck height along the valley center line,
    embedding into both roof planes to bridge the intersection cleanly.
    """
    fx, fy = foot_xy
    ax, ay = apex_xy
    dx, dy = ax - fx, ay - fy
    plan_len = math.hypot(dx, dy)
    if plan_len < 0.3:
        return
    ux, uy = dx / plan_len, dy / plan_len

    pts = []
    total = plan_len + foot_extend + apex_extend
    for i in range(segs + 1):
        s = -foot_extend + (total * i / segs)
        px = fx + ux * s
        py = fy + uy * s
        try:
            mz = main_fn(px, py)
        except Exception:
            mz = -1e9
        try:
            wz = wing_fn(px, py)
        except Exception:
            wz = -1e9
        pz = max(mz, wz) + beam_h * 0.5 - embed
        pts.append(Vector((px, py, pz)))
    for i in range(segs):
        p0 = pts[i]
        p1 = pts[i + 1]
        seg = p1 - p0
        seg_len = seg.length
        if seg_len < 0.05:
            continue
        mid = (p0 + p1) * 0.5
        rot_z = math.atan2(seg.y, seg.x)
        horiz = math.hypot(seg.x, seg.y)
        pitch = -math.atan2(seg.z, max(1e-5, horiz))
        rot_mat = Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y')
        create_beveled_box(
            bm,
            size=(seg_len + 0.05, beam_w, beam_h),
            location=mid,
            rotation=rot_mat.to_euler(),
            mat_index=mat_index,
            bevel_amount=0.012
        )

