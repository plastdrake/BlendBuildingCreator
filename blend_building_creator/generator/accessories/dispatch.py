"""
Accessory dispatch.

Builds the optional architectural accessories that layer onto the finished main
mass: the mini-wing outcrop, timber balconies, the pillared overhang and the
civic landmarks. Splitting this out of ``building.generate_building`` keeps the
orchestrator focused on the building itself and gives each accessory a single
named entry point.
"""

from .mini_wing import build_mini_wing
from .pillared_overhang import build_pillared_overhang
from .balcony import build_balcony
from .hospitality import build_hospitality_scene
from .tower import build_clock_tower, build_corner_turret
from .rampart import build_entry_ramp, build_side_rampart_for_shape
from .porch import build_arched_porch
from .town_hall import build_town_hall_composer
from .annex import build_side_annex
from .blacksmith import build_blacksmith_forge
from .windmill import build_windmill_sails
from .watchtower import build_watchtower_lookout
from .fisherman import build_fisherman_stilts
from .bakery import build_bakery_oven
from .archery import build_archery_range
from .chapel import build_chapel_kit
from .tournament import build_tournament_yard
from .crane import build_courtyard_crane
from .mill import build_lumbermill_yard, build_treadwheel_sawmill, choose_entry_bay
from .palisade import (
    build_palisade_enclosure, compound_bounds, fortification_offset,
    fortification_depth_extra,
)
from .banner import build_banner_pole
from .military_props import build_military_props
from ..openings import build_front_steps


def _prop(props, name, default):
    return getattr(props, name, default)


def _build_mini_wing(bm, props, ctx, tier):
    """Build the outcrops laid out by :func:`mini_wing_spread` (ctx owns the slots)."""
    if not _prop(props, 'has_mini_wing', False):
        return
    for fl, placements in sorted(ctx.mini_wing_spread.items()):
        bounds = ctx.bounds_for(fl)
        lower = ctx.bounds_for(max(0, fl - 1))
        mode = 'GROUND' if fl == 0 else 'UPPER'
        for side_i, off, width, depth in placements:
            build_mini_wing(
                bm,
                side=side_i,
                floor_mode=mode,
                wall_x_min=bounds[0], wall_x_max=bounds[1],
                wall_y_min=bounds[2], wall_y_max=bounds[3],
                z_base=ctx.found_h + fl * ctx.floor_h,
                width=width,
                depth=depth,
                height=min(2.05, ctx.floor_h * 0.72),
                roof_style=_prop(props, 'mini_wing_roof', 'LEAN_TO'),
                tier=tier, floor_h=ctx.floor_h, lower_bounds=lower,
                win_w=_prop(props, 'window_width', 0.85),
                win_h=_prop(props, 'window_height', 1.2),
                shingle_scale=_prop(props, 'mini_wing_shingle_scale', 0.32),
                shingle_rot=int(_prop(props, 'mini_wing_shingle_rot', '0')),
                off_along=off,
            )


def _build_balconies(bm, props, ctx, tier):
    if not _prop(props, 'has_balcony', False) or ctx.num_floors < 2 or not ctx.floor_balc_side:
        return
    width = _prop(props, 'balcony_width', 2.4)
    depth = _prop(props, 'balcony_depth', 1.3)
    for fl_idx in ctx.active_balc_floors:
        side = ctx.floor_balc_side.get(fl_idx)
        if side is None:
            continue
        bounds = ctx.bounds_for(fl_idx)
        lower = ctx.bounds_for(max(0, fl_idx - 1))
        build_balcony(
            bm, side=side,
            wall_x_min=bounds[0], wall_x_max=bounds[1],
            wall_y_min=bounds[2], wall_y_max=bounds[3],
            lower_wall_x_min=lower[0], lower_wall_x_max=lower[1],
            lower_wall_y_min=lower[2], lower_wall_y_max=lower[3],
            z_floor=ctx.found_h + fl_idx * ctx.floor_h,
            width=width, depth=depth, tier=tier,
            door_angle_deg=_prop(props, 'door_angle', 0.0),
        )


def _build_pillared_overhang(bm, props, ctx, tier):
    if not _prop(props, 'has_pillared_overhang', False):
        return
    bounds = ctx.bounds_for(0)
    build_pillared_overhang(
        bm,
        side=_prop(props, 'pillared_overhang_side', 'FRONT'),
        wall_x_min=bounds[0], wall_x_max=bounds[1],
        wall_y_min=bounds[2], wall_y_max=bounds[3],
        z_ground=0.0, z_ceiling=ctx.found_h + ctx.floor_h,
        depth=_prop(props, 'pillared_overhang_depth', 1.6),
        pillar_count=_prop(props, 'pillared_overhang_pillars', 3),
        pillar_style=_prop(props, 'pillared_overhang_style', 'TIMBER_STONE'),
        tier=tier,
    )


def _build_hospitality(bm, props, ctx, tier):
    """Tavern/inn front-of-house plus any reusable yard decor toggles."""
    build_hospitality_scene(bm, props, ctx, tier)


def _build_civic_landmarks(bm, props, ctx, tier):
    base_hx = ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    floor_decks = [ctx.found_h + i * ctx.floor_h for i in range(1, ctx.num_floors)]
    wing_front = -base_hy - ctx.raw_wing_d

    if _prop(props, 'has_clock_tower', False):
        t_size = _prop(props, 'clock_tower_size', 3.0)
        t_sgn = 1.0 if _prop(props, 'clock_tower_side', 'RIGHT') == 'RIGHT' else -1.0
        # When a rampart shares the tower's side, nudge the tower out so it lines
        # up with the middle of the ramp / walk.
        _ramp_same = (_prop(props, 'has_side_rampart', False)
                      and _prop(props, 'rampart_side', 'RIGHT')
                      == _prop(props, 'clock_tower_side', 'RIGHT'))
        if _ramp_same:
            _fl1 = ctx.floor_wall_bounds.get(1, None)
            _r_face = ((_fl1[1] if t_sgn > 0 else _fl1[0]) if _fl1 else t_sgn * base_hx)
            t_cx = _r_face + t_sgn * 1.30           # half the 2.6 m walk width
        else:
            t_cx = t_sgn * (base_hx + t_size * 0.5 - 0.7)
        build_clock_tower(
            bm,
            cx=t_cx,
            cy=wing_front + t_size * 0.5 - 0.25,
            z_ground=0.0, size=t_size,
            shaft_top_z=ctx.found_h + ctx.num_floors * ctx.floor_h + props.roof_height * 1.15,
            tier=tier,
            roof_flare=_prop(props, 'roof_flare', 0.38),
            floor_levels=floor_decks, front_y=wing_front,
            arch_passage=bool(_prop(props, 'town_hall_composer', False)),
        )
    if _prop(props, 'has_corner_turrets', False):
        # Square corner towers, ~30% taller than before, mounted on the BACK
        # wall (so the hall stairs never block their doorway). They sit just
        # outside the back wall plane and connect via a doorway per storey.
        _eave = ctx.found_h + ctx.num_floors * ctx.floor_h
        tur_top = (_eave + ctx.floor_h * 0.95) * 1.30
        tur_half = max(1.0, min(2.0, _prop(props, 'corner_turret_size', 1.35)))
        _levels = [ctx.found_h + i * ctx.floor_h for i in range(ctx.num_floors)]
        _wt = ctx.wall_t
        _t_cx = base_hx - tur_half
        for _sx in (-1.0, 1.0):
            build_corner_turret(
                bm,
                cx=_sx * _t_cx, cy=base_hy + _wt * 0.5 + tur_half,
                z_ground=0.0, half=tur_half, wall_top_z=tur_top, tier=tier,
                out_dir=(0.0, 1.0), floor_levels=_levels,
                floor_h=ctx.floor_h, main_wall_top=_eave,
                attach_tuck=max(0.30, _wt),
                plank_direction=ctx.plank_dir, seed=ctx.seed)
    if (_prop(props, 'has_arched_porch', False)
            and getattr(ctx, 'effective_archetype', None) != 'STABLE'):
        # A jettied upper storey overhangs the ground-floor wall, so the porch
        # must abut the outermost storey's face. Anchoring it to the ground
        # wall would push the tall porch ridge up through the cantilever slab
        # and into the interior. Tuck it under the jetty instead.
        _porch_front = ctx.main_door_yf
        _ptop = ctx.floor_wall_bounds.get(ctx.num_floors - 1)
        if _ptop is not None and _ptop[2] < _porch_front:
            _porch_front = _ptop[2]
        build_arched_porch(bm, door_x=ctx.main_door_cx, front_y=_porch_front,
                           z_ground=0.0, z_floor=ctx.found_h,
                           tier=tier, plank_direction=ctx.plank_dir)
    if _prop(props, 'has_entry_ramp', False):
        build_entry_ramp(bm, door_x=ctx.main_door_cx, front_y=ctx.main_door_yf,
                         z_floor=ctx.found_h, width=1.6, side_offset=2.2)
    # Town Hall composer: annex volume + forecourt ramparts (tower arch above)
    if _prop(props, 'town_hall_composer', False) and ctx.shape == 'T_SHAPE':
        build_town_hall_composer(bm, props, {
            'tier': tier, 'base_hx': base_hx, 'base_d': ctx.base_d,
            'found_h': ctx.found_h, 'floor_h': ctx.floor_h, 'num_floors': ctx.num_floors,
            'wing_front': wing_front, 'door_x': ctx.main_door_cx,
            'seed': ctx.seed, 'fl1_bounds': ctx.floor_wall_bounds.get(1, None),
            'floor_wall_bounds': ctx.floor_wall_bounds, 'wall_t': ctx.wall_t,
        })
    # Generic reusable side annex for any other building/preset.
    elif _prop(props, 'has_side_annex', False):
        _build_generic_annex(bm, props, ctx, tier)
    # Rampart walk for any other footprint (the T-shaped composer owns its own).
    elif _prop(props, 'has_side_rampart', False):
        build_side_rampart_for_shape(bm, props, ctx)


def _build_generic_annex(bm, props, ctx, tier):
    """Attach the reusable half-timbered side annex to any footprint."""
    side_sgn = 1.0 if _prop(props, 'annex_side', 'LEFT') == 'RIGHT' else -1.0
    a_floors = max(1, min(2, _prop(props, 'annex_floors', 2)))
    base_hx = ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    a_w = min(6.0, max(3.6, ctx.base_d * 0.72))
    a_d = 3.6 if tier == 'TIER_1' else 4.0
    a_roof = 3.0 if tier == 'TIER_3' else 2.6
    build_side_annex(
        bm, side_sgn=side_sgn, main_hx=base_hx,
        main_cy0=-base_hy, main_cy1=base_hy,
        z_ground=0.0, found_h=ctx.found_h, floors=a_floors, floor_h=ctx.floor_h,
        tier=tier, width=a_w, depth=a_d, roof_h=a_roof,
        plank_direction=ctx.plank_dir,
        main_bounds_by_floor=ctx.floor_wall_bounds,
        main_roof={
            'num_floors': ctx.num_floors, 'rotated': ctx.is_rotated_roof,
            'top_z': ctx.found_h + ctx.num_floors * ctx.floor_h,
            'top_cx': 0.0, 'top_cy': 0.0, 'top_hx': ctx.hx, 'top_hy': ctx.hy,
            'x_min': -ctx.hx, 'x_max': ctx.hx, 'y_min': -ctx.hy, 'y_max': ctx.hy,
            'roof_h': _prop(props, 'roof_height', 3.0),
            'flare': _prop(props, 'roof_flare', 0.40),
            'sway': _prop(props, 'roof_sway', 0.30),
            'style': _prop(props, 'roof_style', 'SWAY'),
            'ov': _prop(props, 'roof_overhang', 0.70),
        },
        # Log (Tier 1) buildings get a plain log annex, never half-timbering.
        timber_framing=bool(_prop(props, 'has_timber_framing', True)) and tier != 'TIER_1',
        diagonals=bool(_prop(props, 'timber_diagonals', True)),
    )


def build_architectural_accessories(bm, props, ctx):
    """Build every enabled outcrop, balcony, overhang, estate grounds and civic landmark.

    The main manor (shell plus everything attached to it) can be pushed back on the
    plot via ``plot_setback``. That translation happens after the manor-attached
    pieces and before the detached grounds, so the outbuildings, fountain and
    perimeter enclosure stay put and the front honor court simply deepens.
    """
    tier = _prop(props, 'material_tier', 'TIER_3')
    _build_mini_wing(bm, props, ctx, tier)
    _build_balconies(bm, props, ctx, tier)
    _build_pillared_overhang(bm, props, ctx, tier)
    _build_hospitality(bm, props, ctx, tier)
    _build_civic_landmarks(bm, props, ctx, tier)
    # Manor-borne fortifications (mounted shields, gable crests) travel with it.
    _build_manor_fortifications(bm, props, ctx)

    setback = _prop(props, 'plot_setback', 0.0)
    off_x = _prop(props, 'plot_offset_x', 0.0)
    if abs(setback) > 1e-6 or abs(off_x) > 1e-6:
        for v in bm.verts:
            v.co.y += setback
            v.co.x += off_x

    _build_estate_grounds(bm, props, ctx)
    # Plot-borne fortifications (enclosure, bastions, banners, drill yard) stay put.
    _build_plot_fortifications(bm, props, ctx)
    # Plot-borne archetype grounds (the archery field, the knights' yard) stay
    # put, laid out in plot space so the hall can be offset/set back without
    # dragging the grounds with it.
    _plot_arch = _prop(props, 'building_archetype', '')
    if _plot_arch == 'ARCHERY_RANGE':
        build_archery_range(bm, props, ctx, tier)
    elif _plot_arch == 'KNIGHTS_MANOR':
        build_tournament_yard(bm, props, ctx, tier)


def _build_estate_grounds(bm, props, ctx):
    """Procedurally construct detached outbuildings and courtyard fountain."""
    from .estate import build_estate_outbuildings
    build_estate_outbuildings(bm, props, ctx)


def _place_banners(bm, props, ctx):
    """Raise banner poles around the compound (on the palisade line if present).

    When bastion towers are present the front corner slots are shifted inward to
    sit between the gate and the tower, not on top of the tower itself.
    """
    count = max(2, int(_prop(props, 'banner_count', 4)))
    has_enclosure = (_prop(props, 'has_palisade', False)
                     or _prop(props, 'has_curtain_wall', False))
    off = fortification_offset(props) if has_enclosure else 1.2
    x_min, x_max, y_min, y_max = compound_bounds(
        ctx, off, fortification_depth_extra(props) if has_enclosure else 0.0)
    _is_curtain = _prop(props, 'has_curtain_wall', False)
    wall_h = (_prop(props, 'curtain_wall_height', 3.2)
              if _is_curtain
              else _prop(props, 'palisade_height', 2.3))
    # Curtain walls carry a raised wall-walk and crenellated merlons, so raise
    # the standard further or the hanging cloth overlaps the parapet.
    height = max(4.2, wall_h + 2.2 + (1.15 if _is_curtain else 0.0))

    has_towers = _prop(props, 'has_bastion_towers', False)
    t_size = _prop(props, 'bastion_tower_size', 3.2) if has_towers else 0.0
    t_half = t_size * 0.5
    # Front palisade clear zone starts at x_min + t_size + 0.5 from each side
    t_clear_front = t_size + 0.5 if has_towers else 0.0
    px_min = x_min + t_clear_front   # leftmost safe banner X on front run
    px_max = x_max - t_clear_front   # rightmost safe banner X on front run
    gate_cx = ctx.main_door_cx

    # Candidate positions — front corners shift to midpoint between tower and gate
    front_left_x  = (px_min + gate_cx) * 0.5 if has_towers else x_min
    front_right_x = (px_max + gate_cx) * 0.5 if has_towers else x_max

    cands = [
        (front_left_x,           y_min, (0.0, -1.0)),               # Front-left mid
        (front_right_x,          y_min, (0.0, -1.0)),               # Front-right mid
        (gate_cx - 1.8,          y_min, (0.0, -1.0)),               # Front gate left
        (gate_cx + 1.8,          y_min, (0.0, -1.0)),               # Front gate right
        (x_max,                  y_max, (0.0,  1.0)),               # Back-right corner
        (x_min,                  y_max, (0.0,  1.0)),               # Back-left corner
        (x_min, (y_min + y_max) * 0.5, (-1.0, 0.0)),               # Left side flank
        (x_max, (y_min + y_max) * 0.5, ( 1.0, 0.0)),               # Right side flank
    ]
    for i in range(count):
        bx, by, d = cands[i % len(cands)]
        build_banner_pole(bm, bx, by, 0.0, height=height, flag_dir=d)




def _build_manor_fortifications(bm, props, ctx):
    """Fortification pieces that are physically mounted on the manor itself.

    Built before the plot setback is applied so they travel with the building:
    mounted entrance shields and heraldic gable crests.
    """
    # A few mounted round shields flanking the main entrance only — no more
    # heraldry strung along the outer enclosure walls.
    if _prop(props, 'has_mounted_shields', False):
        from .shield import build_round_shield
        is_curtain = _prop(props, 'has_curtain_wall', False)
        door_half = _prop(props, 'door_width', 1.2) * 0.5
        base_x = door_half + 0.90
        n_each = 2 if is_curtain else 1
        wall_face = ctx.main_door_yf - ctx.wall_t * 0.5 - 0.02
        sh_z = ctx.found_h + 1.75
        for s in (-1.0, 1.0):
            for i in range(n_each):
                sx = ctx.main_door_cx + s * (base_x + i * 0.85)
                build_round_shield(bm, (sx, wall_face, sh_z),
                                   normal=(0.0, -1.0, 0.0), radius=0.30,
                                   pattern='QUARTERED' if i % 2 == 0 else 'SOLID')

    # Mounted heraldic gable banners (Concept 1 barracks)
    if _prop(props, 'has_gable_crest', False):
        _build_gable_crests(bm, props, ctx)


def _build_plot_fortifications(bm, props, ctx):
    """Plot-level fortifications that stay anchored to the estate grounds:
    palisades, curtain walls, bastions, banners and military drill props."""
    # 1. Corner bastion towers (Citadel Tier 3)
    if _prop(props, 'has_bastion_towers', False):
        from .bastion import build_bastion_courtyard_towers
        build_bastion_courtyard_towers(bm, props, ctx)

    # 2. Perimeter enclosure. A stone curtain wall supersedes the timber palisade.
    is_curtain = _prop(props, 'has_curtain_wall', False)
    if is_curtain:
        from .curtain_wall import build_curtain_wall_enclosure
        build_curtain_wall_enclosure(bm, props, ctx)
    elif _prop(props, 'has_palisade', False):
        build_palisade_enclosure(
            bm, props, ctx,
            height=_prop(props, 'palisade_height', 2.3),
            style=_prop(props, 'palisade_style', 'STAKES'),
            offset=_prop(props, 'palisade_offset', 3.0))

    # 4. Military drill yard apparatus (archery targets, weapon rack, quintain)
    if _prop(props, 'has_military_props', False):
        build_military_props(bm, props, ctx)

    # 5. Heraldic standards / banner poles
    if _prop(props, 'has_banners', False):
        _place_banners(bm, props, ctx)


def _build_gable_crests(bm, props, ctx):
    """Mount a banner plaque on the main hall's gables and every wing gable.

    The main ridge contributes two gable ends (front/back or left/right when the
    roof is rotated) and each wing contributes its outer gable face; the inner
    wing gable dies into the main roof so it is skipped.
    """
    from .heraldic_crest import build_gable_heraldic_crest
    wall_t = ctx.wall_t
    num_fl = getattr(props, 'num_floors', 1)
    fl_h = getattr(props, 'floor_height', 2.8)
    found_h = getattr(props, 'foundation_height', 0.5)
    c_scale = getattr(props, 'gable_crest_scale', 1.0)
    c_style = getattr(props, 'gable_crest_style', 'KITE_SHIELD')
    roof_h = getattr(props, 'roof_height', 3.0)
    # Sit the banner a little further off the gable face so the timber framing
    # reads clearly in front of it rather than fighting the frame.
    _off = wall_t * 0.5 + 0.08

    # Main hall: top-storey jettied bounds so the banner sits proud of the real
    # gable face instead of buried inside a cantilevered overhang.
    eave_z = found_h + num_fl * fl_h
    _fb = ctx.floor_wall_bounds.get(num_fl - 1)
    if _fb is None:
        _fb = (-ctx.base_w * 0.5, ctx.base_w * 0.5,
               -ctx.base_d * 0.5, ctx.base_d * 0.5)
    crest_z = eave_z + roof_h * 0.40 + 1.25
    if ctx.is_rotated_roof:
        # Ridge runs side-to-side: the real gables are the left/right walls.
        build_gable_heraldic_crest(
            bm, (_fb[0] - _off, 0.0, crest_z),
            normal=(-1.0, 0.0, 0.0), scale=c_scale, style=c_style)
        build_gable_heraldic_crest(
            bm, (_fb[1] + _off, 0.0, crest_z),
            normal=(1.0, 0.0, 0.0), scale=c_scale, style=c_style)
    else:
        build_gable_heraldic_crest(
            bm, (ctx.main_door_cx, _fb[2] - _off, crest_z),
            normal=(0.0, -1.0, 0.0), scale=c_scale, style=c_style)
        build_gable_heraldic_crest(
            bm, (ctx.main_door_cx, _fb[3] + _off, crest_z),
            normal=(0.0, 1.0, 0.0), scale=c_scale, style=c_style)

    # Wing gables (outer face only).
    if not ctx.has_wing:
        return
    w_top_fl = min(ctx.wing_floors, num_fl)
    w_fl_idx = w_top_fl - 1
    w_top_z = found_h + w_top_fl * fl_h
    _wr_scale = getattr(props, 'wing_roof_scale', 0.88)
    w_roof_h = roof_h if ctx.wing_floors == num_fl else roof_h * _wr_scale
    w_crest_z = w_top_z + w_roof_h * 0.40 + 1.25
    for w in ctx.wings:
        wb = (w.get('bounds_fl') or {}).get(w_fl_idx)
        if wb is None:
            continue
        wx0, wx1, wy0, wy1 = wb
        wall = w.get('wall')
        if wall == 'FRONT':
            loc = ((wx0 + wx1) * 0.5, wy0 - _off, w_crest_z)
            nrm = (0.0, -1.0, 0.0)
        elif wall == 'BACK':
            loc = ((wx0 + wx1) * 0.5, wy1 + _off, w_crest_z)
            nrm = (0.0, 1.0, 0.0)
        elif wall == 'LEFT':
            loc = (wx0 - _off, (wy0 + wy1) * 0.5, w_crest_z)
            nrm = (-1.0, 0.0, 0.0)
        else:  # RIGHT
            loc = (wx1 + _off, (wy0 + wy1) * 0.5, w_crest_z)
            nrm = (1.0, 0.0, 0.0)
        build_gable_heraldic_crest(bm, loc, normal=nrm, scale=c_scale, style=c_style)


def build_archetype_accessories(bm, props, ctx, _loft_spec):
    """Archetype-specific structures (forge, sails, crane, mill, ...) and loft hatch."""
    effective_archetype = ctx.effective_archetype
    base_w = ctx.base_w
    found_h = ctx.found_h
    hx = ctx.hx
    hy = ctx.hy
    main_door_cx = ctx.main_door_cx
    main_door_yf = ctx.main_door_yf
    seed = ctx.seed
    shape = ctx.shape
    top_hx = ctx.top_hx
    top_hy = ctx.top_hy
    top_z = ctx.top_z
    wall_t = ctx.wall_t
    wings = ctx.wings
    open_timber = getattr(props, 'open_timber_frame', False)
    tier = _prop(props, 'material_tier', 'TIER_1')

    # 4.5. Specialized Architectural Archetype Accessories
    if effective_archetype == 'BLACKSMITH':
        build_blacksmith_forge(bm, -hx, hx, -hy, hy, z_ground=0.04, wall_thickness=wall_t, seed=seed)
    elif effective_archetype == 'WINDMILL':
        hub_z = top_z - 0.35
        build_windmill_sails(bm, cx=0.0, front_y=-hy, hub_z=hub_z, radius=max(2.6, props.width * 0.48), wall_y=-hy + 0.35)
    elif effective_archetype == 'WATCHTOWER':
        build_watchtower_lookout(bm, -top_hx, top_hx, -top_hy, top_hy, z_platform=top_z)
    elif effective_archetype == 'FISHERMAN':
        build_fisherman_stilts(bm, -hx, hx, -hy, hy, z_ground=0.0, z_floor=found_h)
    elif effective_archetype == 'BAKERY':
        build_bakery_oven(bm, props, ctx, tier)
    elif effective_archetype == 'CHAPEL':
        build_chapel_kit(bm, props, ctx, tier)
    elif effective_archetype == 'STABLE':
        from .estate import build_stable_yard_for_building
        build_stable_yard_for_building(bm, props, ctx)
    elif effective_archetype == 'WAREHOUSE':
        if getattr(props, 'material_tier', 'TIER_1') != 'TIER_1' and props.roof_style != 'NONE':
            yard_x = 0.0
            yard_y = -hy - 1.8
            rot_crane = -1.57
            if shape == 'L_SHAPE' and wings:
                w_elem = wings[0]
                wx1, wx2, wy1, wy2 = w_elem['base']
                # The crane sits toward the courtyard mouth (away from both roofs) with
                # the jib pointing out of the courtyard so the boom/rope clears the eaves.
                if w_elem['wall'] == 'FRONT':
                    if w_elem.get('align') == 'RIGHT':
                        yard_x = (-hx + wx1) * 0.5 - 0.6
                        yard_y = (wy1 - hy) * 0.5 - 1.2
                        rot_crane = -1.40
                    else:
                        yard_x = (wx2 + hx) * 0.5 + 0.6
                        yard_y = (wy1 - hy) * 0.5 - 1.2
                        rot_crane = -1.75
                elif w_elem['wall'] == 'BACK':
                    if w_elem.get('align') == 'RIGHT':
                        yard_x = (-hx + wx1) * 0.5 - 0.6
                        yard_y = (hy + wy2) * 0.5 + 1.2
                        rot_crane = 1.40
                    else:
                        yard_x = (wx2 + hx) * 0.5 + 0.6
                        yard_y = (hy + wy2) * 0.5 + 1.2
                        rot_crane = 1.75
            build_courtyard_crane(bm, yard_x=yard_x, yard_y=yard_y, z_ground=0.0, rot_angle=rot_crane)
        # For primitive / supply-depot tier, dress the yard with crates, barrels, lumber piles, sacks, and awnings
        if getattr(props, 'material_tier', 'TIER_3') == 'TIER_1' or props.roof_style in ('NONE', 'MAKESHIFT'):
            from .warehouse import build_supply_depot_yard
            build_supply_depot_yard(bm, min_x=-hx, max_x=hx, min_y=-hy, max_y=hy, z_floor=found_h, seed=seed)
            if shape == 'L_SHAPE' and wings:
                wx1, wx2, wy1, wy2 = wings[0]['base']
                build_supply_depot_yard(bm, min_x=wx1, max_x=wx2, min_y=wy1, max_y=wy2, z_floor=found_h, seed=seed + 31)
    elif effective_archetype == 'LUMBERMILL':
        mill_grade = getattr(props, 'mill_grade', 'GRADE_1')
        is_enclosed_mill = (mill_grade in ('GRADE_2', 'GRADE_3') or not open_timber)
        rot_yard = 0.0
        dock_planks = None
        if is_enclosed_mill:
            # Staged in the open yard between entrance corridor and dock, rotated ~85 deg
            yard_x = -1.4
            yard_y = -hy - 3.4 if mill_grade == 'GRADE_2' else -hy - 4.0
            # Sawn planks placed directly on the cargo dock floor (right side of freight portal)
            dock_x = 4.8 if mill_grade == 'GRADE_2' else 5.2
            dock_y = -hy - 1.0 if mill_grade == 'GRADE_2' else -hy - 1.2
            dock_z = found_h + 0.05
            dock_planks = (dock_x, dock_y, dock_z, 0.03)
        else:
            yard_x = 0.0
            yard_y = -hy - 2.2

        if shape == 'L_SHAPE' and wings:
            w_elem = wings[0]
            wx1, wx2, wy1, wy2 = w_elem['base']
            if w_elem['wall'] == 'FRONT':
                if w_elem.get('align') == 'RIGHT':
                    yard_x = (-hx + wx1) * 0.5
                    yard_y = (wy1 - hy) * 0.5
                else:
                    yard_x = (wx2 + hx) * 0.5
                    yard_y = (wy1 - hy) * 0.5
            elif w_elem['wall'] == 'BACK':
                if w_elem.get('align') == 'RIGHT':
                    yard_x = (-hx + wx1) * 0.5
                    yard_y = (hy + wy2) * 0.5
                else:
                    yard_x = (wx2 + hx) * 0.5
                    yard_y = (hy + wy2) * 0.5

        build_lumbermill_yard(
            bm, yard_x=yard_x, yard_y=yard_y, z_ground=0.0,
            rot_angle=rot_yard, grade=mill_grade, dock_planks_pos=dock_planks
        )
        build_treadwheel_sawmill(bm, mill_cx=0.4, mill_cy=0.55, z_floor=found_h, grade=mill_grade)
        # Mill worker steps: grounded cut-stone steps on the clearest entrance bay.
        # Only on open-timber / Tier 1 pavilions; Tier 2 and 3 have enclosed front walls with their own offset front door and steps.
        mill_sx = choose_entry_bay(base_w, hx, yard_x, mill_grade)
        if props.has_front_steps and props.has_foundation and (open_timber or mill_grade == 'GRADE_1'):
            build_front_steps(bm, center_x=mill_sx, y_front=-hy, z_base=found_h,
                              num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y')

    # 4.5b Optional gable loft hatch frame, open leaf and leaning ladder.
    # The wall opening itself was left by the roof builders from _loft_arg.
    if _loft_spec:
        from .loft import build_gable_loft_hatch
        _lout = 1.0 if _loft_spec['side'] in ('BACK', 'RIGHT') else -1.0
        build_gable_loft_hatch(
            bm, wall_axis=_loft_spec['axis'], wall_face=_loft_spec['face'],
            center=_loft_spec['center'], sill_z=_loft_spec['sill'], outward=_lout,
        )
