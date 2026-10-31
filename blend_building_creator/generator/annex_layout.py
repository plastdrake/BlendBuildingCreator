"""Resolve side-annex placement before the floors and roof phases run.

The annex volume itself lives outside the main wall, so it never collides with
the staircase.  Its *walk-in portal*, however, is cut through the main side
wall, and that wall is exactly where a straight/turned/spiral staircase usually
runs.  This module works out, once, a side and a portal position that stay clear
of the stair run, then hands the same answer to the floor phase (portal cut and
window suppression), the accessory dispatch (annex volume, roof band) and the
attic phase (loft-hatch avoidance).

Only the standard ``props`` attribute interface is used so the helper is safe
to call from tests that build a plain ``SimpleNamespace``.
"""

from .walls import __name__ as _walls_name  # noqa: F401  (keeps relative imports valid)

# Main-wall portal cut dimensions, mirrored from floors.build_floors.
PORTAL_WIDTH = 1.65
PORTAL_JAMB = 0.16
PORTAL_HALF = PORTAL_WIDTH * 0.5 + PORTAL_JAMB * 0.5  # 0.905 m
PORTAL_CLEAR = 0.10
WALL_EDGE_MARGIN = 0.05
ANNEX_DOOR_MARGIN = 0.08
MAX_REAR_PROJECTION = 0.22


def _prop(props, name, default):
    try:
        value = getattr(props, name, default)
    except Exception:
        return default
    return default if value is None else value


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _interior(base_w, base_d, wall_t):
    return (-base_w * 0.5 + wall_t * 0.5, base_w * 0.5 - wall_t * 0.5,
            -base_d * 0.5 + wall_t * 0.5, base_d * 0.5 - wall_t * 0.5)


def _straight_stair_span(props, ix_min, ix_max, iy_min, iy_max):
    """Mirror the straight-stair Y run computed by ``floors.build_floors``."""
    stair_w = float(_prop(props, 'stair_width', 1.0) or 1.0)
    landing_depth = max(1.85, stair_w * 0.85)
    d_int = iy_max - iy_min

    is_tenement = (_prop(props, 'building_archetype', '') == 'TENEMENT')
    if is_tenement and d_int >= 7.4:
        if d_int >= 11.0:
            end_landing = 2.50
        else:
            end_landing = max(2.00, min(2.50, (d_int - 2.0 * 2.4) / 3.0))
        run_avail = d_int - 2.0 * end_landing - end_landing
        stair_len = min(3.8, max(2.4, run_avail * 0.5))
        y_s0 = iy_min + end_landing
        y_s1 = y_s0 + stair_len
        y_n1 = iy_max - end_landing
        y_n0 = y_n1 - stair_len
        return min(y_s0, y_n0), max(y_s1, y_n1)

    min_land = 2.00
    if d_int >= 7.6:
        stair_len = min(3.6, max(2.5, d_int - 2.0 * min_land))
    elif d_int >= 6.4:
        stair_len = min(3.4, max(2.3, d_int - 2.0 * min_land))
    elif d_int >= 5.8:
        stair_len = min(3.0, max(2.2, d_int - 3.8))
    else:
        stair_len = max(2.0, min(2.6, d_int * 0.45))

    head = iy_min + landing_depth
    foot = head + stair_len
    return min(head, foot), max(head, foot)


def _stairs_movable(props):
    """Any non-spiral, non-tenement switchback can be moved wall-to-wall."""
    if not bool(_prop(props, 'has_stairs', False)):
        return False
    style = str(_prop(props, 'stair_style', 'STRAIGHT') or 'STRAIGHT').upper()
    if style == 'SPIRAL':
        return False
    return str(_prop(props, 'building_archetype', '') or '').upper() != 'TENEMENT'


_MIN_WALKWAY = 1.00


def _is_switchback(props):
    """Mirror floors.build_floors: every non-tenement, non-spiral stair is a switchback."""
    if not bool(_prop(props, 'has_stairs', False)):
        return False
    if str(_prop(props, 'stair_style', 'STRAIGHT') or 'STRAIGHT').upper() == 'SPIRAL':
        return False
    return str(_prop(props, 'building_archetype', '') or '').upper() != 'TENEMENT'


def _lane_gap_widths(props, tw, placement):
    """(facade, free wall length beyond the dual lane well) for a switchback."""
    stair_w = float(_prop(props, 'stair_width', 1.0) or 1.0)
    lane_gap = 0.20
    total = stair_w * 2.0 + lane_gap
    out = []
    if placement == 'LEFT':
        out.append(('LEFT', tw - (0.08 + total)))
        out.append(('RIGHT', tw - 0.08))
    else:
        out.append(('RIGHT', tw - (0.08 + total)))
        out.append(('LEFT', tw - 0.08))
    return out


def _stair_obstructions(props, ix_min, ix_max, iy_min, iy_max, placement=None):
    """Per-facade (y0, y1) bands occupied by the staircase at wall level."""
    if not bool(_prop(props, 'has_stairs', False)):
        return {}
    style = str(_prop(props, 'stair_style', 'STRAIGHT') or 'STRAIGHT').upper()
    # Plain namespaces (presets, tests) may not carry stair_placement at all;
    # floors.py also treats a missing value as LEFT, so mirror that exactly.
    if placement is None:
        placement = str(_prop(props, 'stair_placement', 'LEFT') or 'LEFT').upper()
    else:
        placement = str(placement or 'LEFT').upper()
    if placement not in ('LEFT', 'RIGHT'):
        placement = 'LEFT'
    # A stair that cannot start for lack of interior depth is skipped by
    # floors.build_floors, so it must not reserve wall either.
    if min(iy_max - iy_min, ix_max - ix_min) < 2.0:
        return {}

    if style == 'SPIRAL':
        stair_w = float(_prop(props, 'stair_width', 1.0) or 1.0)
        radius = min(max(1.35, stair_w * 1.05), (ix_max - ix_min) * 0.42)
        # floors.build_floors places spiral stairs at the front-left corner.
        cy = iy_min + radius + 0.15
        return {'LEFT': (iy_min - 0.25, cy + radius + 0.18)}

    if style == 'TURN':
        tw = ix_max - ix_min
        td = iy_max - iy_min
        col_w = min(7.4, max(4.6, tw - 0.8))
        col_d = min(7.8, max(4.6, td - 0.8))
        x0 = (ix_max - 0.08 - col_w) if placement == 'RIGHT' else (ix_min + 0.08)
        y0 = iy_min + 0.08
        band = (y0 - 0.10, y0 + col_d + 0.10)
        obs = {}
        # A turned stair needs a real corridor beside its column; a gap under
        # 1.05 m cannot serve as the way through an annex doorway.
        if x0 - ix_min < 1.05:
            obs['LEFT'] = band
        if ix_max - (x0 + col_w) < 1.05:
            obs['RIGHT'] = band
        return obs

    span = _straight_stair_span(props, ix_min, ix_max, iy_min, iy_max)
    band = (span[0] - 0.10, span[1] + 0.10)
    obs = {placement: band}
    if _is_switchback(props):
        # The switchback well occupies two lanes and its landing approaches;
        # reserve the full run along the selected facade.
        obs[placement] = (iy_min - 0.10, iy_max + 0.10)
    return obs


def _side_occupied(props, side, wings):
    """True when a wing/landmark already claims this facade."""
    for wing in wings or ():
        try:
            if str(wing.get('wall', '')).upper() == side:
                return True
        except Exception:
            continue
    checks = (
        ('has_clock_tower', 'clock_tower_side', 'RIGHT'),
        ('has_side_rampart', 'rampart_side', 'RIGHT'),
        ('has_side_door', 'side_door_facade', 'RIGHT'),
        ('has_exterior_stairs', 'exterior_stairs_side', 'RIGHT'),
        ('has_water_wheel', 'mill_side', 'LEFT'),
        ('has_pillared_overhang', 'pillared_overhang_side', 'FRONT'),
        ('has_upper_cargo_crane', 'cargo_dock_facade', 'FRONT'),
    )
    for toggle, side_attr, default in checks:
        if not bool(_prop(props, toggle, False)):
            continue
        claimed = str(_prop(props, side_attr, default) or default).upper()
        if claimed == side or claimed == 'BOTH':
            return True
    return False


def _annex_spec(props, ctx):
    """(kind, requested_side, width, floors) for the active annex."""
    # The fishery is built on a tight 12x12 m dock: the deep lean-to annex does
    # not fit alongside the house and its dock/piling kit, so skip it. Other
    # buildings keep their annexes/oriels/balconies where the plot allows.
    if str(_prop(props, 'building_archetype', '') or '').upper() == 'FISHERMAN':
        return '', '', 0.0, 0
    hall = (bool(_prop(props, 'town_hall_composer', False))
            and str(_prop(props, 'building_shape', 'RECTANGLE')).upper() == 'T_SHAPE')
    if hall:
        side = ('LEFT' if str(_prop(props, 'clock_tower_side', 'RIGHT')).upper() == 'RIGHT'
                else 'RIGHT')
        tier = str(_prop(props, 'material_tier', 'TIER_3')).upper()
        width = 4.4 if tier == 'TIER_1' else 5.2
        floors = max(1, min(2, int(_prop(props, 'annex_floors', 2))))
        return 'side', side, width, floors
    if bool(_prop(props, 'has_side_annex', False)):
        raw = str(_prop(props, 'annex_side', 'LEFT') or 'LEFT').upper()
        side = raw if raw in ('LEFT', 'RIGHT', 'BOTH') else 'LEFT'
        width = min(6.0, max(3.6, ctx['base_d'] * 0.72))
        floors = max(1, min(2, int(_prop(props, 'annex_floors', 2))))
        return 'side', side, width, floors
    if bool(_prop(props, 'has_tower_annex', False)):
        raw = str(_prop(props, 'annex_side', 'LEFT') or 'LEFT').upper()
        side = raw if raw in ('LEFT', 'RIGHT', 'BOTH') else 'LEFT'
        return 'tower', side, 12.0, int(ctx['num_floors'])
    return '', '', 0.0, 0


def _portal_interval(obstruction, wall_lo, wall_hi):
    """Allowed portal-centre interval(s) on a wall, split around the stairs."""
    if obstruction is None:
        return [(wall_lo, wall_hi)]
    ob0, ob1 = obstruction
    result = []
    lo_end = ob0 - PORTAL_HALF - PORTAL_CLEAR
    hi_start = ob1 + PORTAL_HALF + PORTAL_CLEAR
    if wall_lo <= lo_end:
        result.append((wall_lo, min(lo_end, wall_hi)))
    if wall_hi >= hi_start:
        result.append((max(hi_start, wall_lo), wall_hi))
    return [(a, b) for a, b in result if b - a > 0.02]


def _fit_side(side, obstruction, annex_cy, annex_w, iy_min, iy_max, base_d):
    """Choose a portal centre and annex centre for one facade.

    Returns ``(portal_cy, cy)`` or ``None`` when no position on the wall can
    open into the annex without sitting inside the stair run.
    """
    wall_lo = iy_min + PORTAL_HALF + WALL_EDGE_MARGIN
    wall_hi = iy_max - PORTAL_HALF - WALL_EDGE_MARGIN
    if wall_lo > wall_hi:
        return None

    spans = _portal_interval(obstruction, wall_lo, wall_hi)
    if not spans:
        return None

    preferred = _clamp(annex_cy, wall_lo, wall_hi)
    chosen = None
    # Prefer the interval containing the requested annex centre; otherwise take
    # the rear-most free interval (away from the entrance/front facade).
    for a, b in spans:
        if a - 1e-9 <= preferred <= b + 1e-9:
            chosen = _clamp(preferred, a, b)
            break
    if chosen is None:
        # SHIFT REARWARD FIRST: slide the portal toward the back of the hall
        # before ever considering flipping the annex to the other facade.
        # Narrow annexes (depth 6.8-8.0) sit mid-wall, exactly where a straight
        # stair lands, and a rear-shifted portal keeps the annex on its natural
        # side instead of an abrupt flip.
        chosen = _clamp(preferred, *spans[-1])
        for a, b in spans:
            if a - 1e-9 <= chosen <= b + 1e-9:
                break

    # Keep the portal inside the annex room width.
    contain = annex_w * 0.5 - PORTAL_HALF - ANNEX_DOOR_MARGIN
    if contain < 0.05:
        return None
    cy_lo = chosen - contain
    cy_hi = chosen + contain

    # Preferred: keep the annex centred on the main hall, allowing only a small
    # rear projection past the wall line on shallow buildings.
    proj = max(0.05, (base_d - annex_w) * 0.5 + MAX_REAR_PROJECTION)
    cy_lo = max(cy_lo, -proj)
    cy_hi = min(cy_hi, proj)
    if cy_lo > cy_hi:
        # The portal is too far out for the projection budget: let the annex
        # follow the portal rather than making the doorway unreachable.
        cy = chosen
    else:
        cy = _clamp(annex_cy, cy_lo, cy_hi)

    # Mirror the constraint in the other direction: if the stair pushed the
    # portal off-centre, grow the annex body so the doorway still lands inside
    # the room with a real margin instead of on its end wall.
    END_WALL_MARGIN = 0.55
    reach = abs(chosen - cy)
    body = reach + PORTAL_HALF + END_WALL_MARGIN
    return chosen, cy, max(annex_w, body * 2.0)


def annex_portal_keepout(bounds, side, portal_cy, wall_t, depth=1.30, half_w=None):
    """Rect outside the facade, in front of the annex doorway, kept free of furniture.

    ``bounds`` is the floor slab ``(x_min, x_max, y_min, y_max)``; ``side`` is the
    facade the annex hangs off.  Annexes carry most of their furnishing, but the
    hall side of the walk-through must stay clear on every storey too.
    """
    if half_w is None:
        half_w = PORTAL_WIDTH * 0.5 + PORTAL_JAMB + PORTAL_CLEAR + 0.35
    if side == 'LEFT':
        return (bounds[0], bounds[0] + depth, portal_cy - half_w, portal_cy + half_w)
    if side == 'RIGHT':
        return (bounds[1] - depth, bounds[1], portal_cy - half_w, portal_cy + half_w)
    if side == 'FRONT':
        return (portal_cy - half_w, portal_cy + half_w, bounds[2], bounds[2] + depth)
    if side == 'BACK':
        return (portal_cy - half_w, portal_cy + half_w, bounds[3] - depth, bounds[3])
    return None


def resolve_annex_layout(props, base_w, base_d, wall_t, num_floors, wings=None, shape=None):
    """Return the resolved annex layout for this building.

    Result keys: ``kind`` ('' | 'side' | 'tower'), ``side`` (''|LEFT|RIGHT|BOTH),
    ``width``, ``floors`` and ``by_side`` mapping each used facade to
    ``{'cy': float, 'portal_cy': float}``.
    """
    ctx = {'base_d': float(base_d), 'base_w': float(base_w),
           'wall_t': float(wall_t), 'num_floors': int(num_floors)}
    kind, requested, width, floors = _annex_spec(props, ctx)
    if not kind:
        return {'kind': '', 'side': '', 'width': 0.0, 'floors': 0, 'by_side': {}}

    # The annex must never rise above the main building.  Vary it between the
    # full main height and one storey lower for a more natural estate mix
    # (deterministic for a given preset/seed, so rebuilding is stable).
    _nf = max(1, int(num_floors))
    if _nf <= 1:
        floors = 1
    else:
        _v = int(abs(float(base_w) * 7.0 + float(base_d) * 13.0
                     + _nf * 3.0 + int(getattr(props, 'seed', 0) or 0))) % 2
        floors = _nf if _v == 0 else max(1, _nf - 1)

    # Hall-side apron of every annex walk-through, kept free of stairs/furniture
    # on every storey the annex spans (see annex_portal_keepout).
    layout = _resolve_layout(kind, requested, width, floors, props, base_w, base_d,
                             wall_t, num_floors, wings)
    layout['clear_rects'] = []
    if layout.get('by_side') and layout.get('floors'):
        _b = _interior(base_w, base_d, wall_t)
        for _side, _lay in sorted(layout['by_side'].items()):
            _rc = annex_portal_keepout(_b, _side, _lay.get('portal_cy', 0.0), wall_t)
            if _rc is not None:
                layout['clear_rects'].append({'rect': _rc, 'side': _side, 'floor_idx': list(
                    range(int(layout['floors'])))})
    return layout


def _resolve_layout(kind, requested, width, floors, props, base_w, base_d,
                    wall_t, num_floors, wings):
    ix_min, ix_max, iy_min, iy_max = _interior(base_w, base_d, wall_t)

    requested_sides = ['LEFT', 'RIGHT'] if requested == 'BOTH' else [requested]
    movable_stairs = _stairs_movable(props)

    # First pass with the stairs where the user asked for them. If the doorway
    # into the annex cannot be cut clear of the flight on any usable facade, the
    # stairs are what has to give: a side annex you cannot walk into is broken,
    # while moving a straight stair to the other wall is invisible from outside.
    obstructions = _stair_obstructions(props, ix_min, ix_max, iy_min, iy_max)
    side_candidates = []
    for side in requested_sides:
        fit = _fit_side(side, obstructions.get(side), 0.0, width, iy_min, iy_max, float(base_d))
        side_candidates.append((side, fit))

    # A doorway that only clears the stair by being squeezed onto the annex
    # end wall is not usable either: treat that as a failed fit so the stairs
    # get moved (or the annex flips) instead.
    def _usable(fit, _w):
        if fit is None:
            return None
        _portal, _cy, _body = fit
        if abs(_portal - _cy) > max(0.05, _body * 0.5 - PORTAL_HALF - PORTAL_CLEAR - 0.20):
            return None
        return fit
    side_candidates = [(s, _usable(f, width)) for s, f in side_candidates]

    # The side annex portal has to remain clear of the stair's full run and landings.
    # For switchbacks, reserve the entire stair wall rather than only visible treads.
    stair_side = None
    # A switchback occupies both approaches along its chosen facade, so move
    # movable stairs or select the free opposite facade before using a fallback.
    _stair_placement = str(_prop(props, 'stair_placement', 'LEFT')).upper()
    _portal_blocked_by_switchback = (
        _is_switchback(props) and requested in ('LEFT', 'RIGHT')
        and requested == _stair_placement)
    _needs_stair_move = (all(fit is None for _s, fit in side_candidates)
                         or _portal_blocked_by_switchback)
    if _needs_stair_move and movable_stairs:
        stair_side = 'RIGHT' if _stair_placement == 'LEFT' else 'LEFT'
        shifted = _stair_obstructions(props, ix_min, ix_max, iy_min, iy_max,
                                      placement=stair_side)
        retry = []
        for side in requested_sides:
            retry.append((side, _usable(_fit_side(side, shifted.get(side), 0.0, width,
                                                 iy_min, iy_max, float(base_d)), width)))
        if any(fit is not None for _s, fit in retry):
            side_candidates = retry
        else:
            stair_side = None

    if _needs_stair_move and not movable_stairs and len(side_candidates) == 1:
        _side, _fit = side_candidates[0]
        _flip = 'RIGHT' if _side == 'LEFT' else 'LEFT'
        _can_flip = (kind == 'side' and requested != 'BOTH'
                     and not (bool(_prop(props, 'town_hall_composer', False))
                              and str(_prop(props, 'building_shape', 'RECTANGLE')).upper() == 'T_SHAPE'))
        if _fit is None and _can_flip and not _side_occupied(props, _flip, wings):
            _flip_fit = _usable(_fit_side(_flip, obstructions.get(_flip), 0.0, width,
                                          iy_min, iy_max, float(base_d)), width)
            if _flip_fit is not None:
                side_candidates[0] = (_flip, _flip_fit)

    by_side = {}
    used_sides = []
    for side, fit in side_candidates:
        chosen_side = side
        if fit is None:
            # Straight/shallow/walled stairs can make one facade unusable.  Flip
            # to the opposite side only when that side is genuinely free; the
            # town-hall annex is pinned opposite its clock tower and never flips.
            flip = 'RIGHT' if side == 'LEFT' else 'LEFT'
            can_flip = (kind == 'side' and requested != 'BOTH'
                        and not (bool(_prop(props, 'town_hall_composer', False))
                                 and str(_prop(props, 'building_shape', 'RECTANGLE')).upper() == 'T_SHAPE'))
            if can_flip and not _side_occupied(props, flip, wings):
                flip_fit = _usable(
                    _fit_side(flip, obstructions.get(flip), 0.0, width,
                              iy_min, iy_max, float(base_d)), width)
                if flip_fit is not None:
                    chosen_side, fit = flip, flip_fit
        side_width = width
        if fit is None:
            # Last resort: keep the requested side and centre the doorway on the
            # annex.  This preserves access and is strictly better than
            # generating an annex with no portal at all.
            wall_lo = iy_min + PORTAL_HALF + WALL_EDGE_MARGIN
            wall_hi = iy_max - PORTAL_HALF - WALL_EDGE_MARGIN
            fit = (_clamp(0.0, wall_lo, wall_hi), 0.0, width)
        portal_cy, cy, side_width = fit
        # Never emit the same facade twice when a flip collapsed BOTH.
        if chosen_side in used_sides:
            continue
        used_sides.append(chosen_side)
        by_side[chosen_side] = {'cy': cy, 'portal_cy': portal_cy,
                                'width': side_width}

    if not by_side:
        return {'kind': '', 'side': '', 'width': 0.0, 'floors': 0, 'by_side': {}}

    side_out = ('BOTH' if len(by_side) == 2
                else next(iter(by_side)))
    if requested != 'BOTH' and kind == 'side' and len(by_side) == 1:
        # A flipped annex is now a single-sided annex.
        side_out = next(iter(by_side))
    primary = by_side.get(side_out, next(iter(by_side.values())))
    return {
        'kind': kind,
        'side': side_out,
        # The body may have grown so the (stair-shifted) portal still opens into
        # the room instead of its end wall.
        'width': max(width, primary.get('width', width)),
        'floors': floors,
        'cy': primary['cy'],
        'portal_cy': primary['portal_cy'],
        'by_side': by_side,
        # None = keep the requested side; otherwise the side the straight stair
        # must move to so the annex doorway stays walkable.
        'stair_side': stair_side,
    }
