import math
from mathutils import Vector
from .common import (
    _get_facade_frame, _planar_uv_faces
)
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
)

def build_lumbermill_yard(bm, yard_x, yard_y, z_ground=0.0, rot_angle=0.0, grade='GRADE_1'):
    cos_r = math.cos(rot_angle)
    sin_r = math.sin(rot_angle)

    log_r = 0.24
    log_l = 3.4
    for off_s in [-0.50, 0.0, 0.50]:
        lx = yard_x + (-sin_r * off_s)
        ly = yard_y + (cos_r * off_s)
        create_horizontal_cylinder(
            bm, radius_y=log_r, radius_z=log_r, length=log_l, segments=12,
            location=(lx, ly, z_ground + log_r - 0.02),
            mat_index=MAT_INDEX_LOG
        )
    for off_s in [-0.25, 0.25]:
        lx = yard_x + (-sin_r * off_s)
        ly = yard_y + (cos_r * off_s)
        create_horizontal_cylinder(
            bm, radius_y=log_r * 0.95, radius_z=log_r * 0.95, length=log_l * 0.97, segments=12,
            location=(lx, ly, z_ground + log_r * 2.55),
            mat_index=MAT_INDEX_LOG
        )
    create_horizontal_cylinder(
        bm, radius_y=log_r * 0.90, radius_z=log_r * 0.90, length=log_l * 0.94, segments=12,
        location=(yard_x, yard_y, z_ground + log_r * 4.05),
        mat_index=MAT_INDEX_LOG
    )
    for chock_s in [-0.82, 0.82]:
        cx = yard_x + (-sin_r * chock_s)
        cy = yard_y + (cos_r * chock_s)
        create_beveled_box(
            bm, size=(0.35, 0.20, 0.22),
            location=(cx, cy, z_ground + 0.09),
            rotation=(0.0, 0.0, rot_angle),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.01
        )

    plank_x = yard_x - cos_r * 1.8 - sin_r * 1.4
    plank_y = yard_y - sin_r * 1.8 + cos_r * 1.4
    for b_off in [-0.6, 0.6]:
        create_beveled_box(
            bm, size=(0.14, 1.10, 0.12),
            location=(plank_x + cos_r * b_off, plank_y + sin_r * b_off, z_ground + 0.06),
            rotation=(0.0, 0.0, rot_angle),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    for row_i in range(5):
        rz = z_ground + 0.12 + row_i * 0.14
        create_beveled_box(
            bm, size=(1.85, 0.95, 0.09),
            location=(plank_x, plank_y, rz),
            rotation=(0.0, 0.0, rot_angle + 0.02),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
        if row_i < 4:
            for s_off in [-0.65, 0.0, 0.65]:
                create_box(
                    bm, size=(0.04, 0.95, 0.035),
                    location=(plank_x + cos_r * s_off, plank_y + sin_r * s_off, rz + 0.06),
                    rotation=(0.0, 0.0, rot_angle),
                    mat_index=MAT_INDEX_TIMBER
                )

    if grade in ('GRADE_2', 'GRADE_3'):
        from .crane import build_courtyard_crane
        crane_x = yard_x + cos_r * 3.6 + sin_r * 1.4
        crane_y = yard_y + sin_r * 3.6 - cos_r * 1.4
        if grade == 'GRADE_2':
            build_courtyard_crane(bm, yard_x=crane_x, yard_y=crane_y, z_ground=z_ground,
                                   mast_height=3.0, jib_length=2.6, rot_angle=rot_angle - 0.35)
        else:
            build_courtyard_crane(bm, yard_x=crane_x, yard_y=crane_y, z_ground=z_ground,
                                   mast_height=3.6, jib_length=3.0, rot_angle=rot_angle - 0.35)

def build_treadwheel_sawmill(bm, mill_cx=0.4, mill_cy=0.55, z_floor=0.4, grade='GRADE_1'):
    specs = {
        'GRADE_1': {'wheel_r': 1.05, 'wheel_w': 1.00, 'blade_r': 0.42, 'bench_l': 3.2,
                    'gear': False, 'carriage': False, 'hoist': 'NONE', 'rollers': False,
                    'dust': (0.85, 0.55), 'stack_rows': 3},
        'GRADE_2': {'wheel_r': 1.45, 'wheel_w': 1.45, 'blade_r': 0.55, 'bench_l': 4.0,
                    'gear': True, 'carriage': True, 'hoist': 'CRANE', 'rollers': False,
                    'dust': (1.15, 0.70), 'stack_rows': 3},
        'GRADE_3': {'wheel_r': 1.45, 'wheel_w': 2.20, 'blade_r': 0.55, 'bench_l': 4.0,
                    'gear': True, 'carriage': False, 'hoist': 'CRANE', 'rollers': True,
                    'dust': (1.35, 0.85), 'stack_rows': 5},
    }
    sp = specs.get(grade, specs['GRADE_1'])
    wheel_r = sp['wheel_r']
    wheel_w = sp['wheel_w']
    blade_r = sp['blade_r']
    bench_l = sp['bench_l']

    bench_top = z_floor + 0.85
    blade_x = mill_cx + bench_l * 0.12
    wheel_x = mill_cx - (bench_l * 0.5 + wheel_r + 1.60)
    axle_z = z_floor + wheel_r + 0.12
    # Chain drive runs outboard of the treadwheel A-frame legs
    # Pulley system height is now anchored to lowered_arbor_z
    pulley_y = mill_cy + wheel_w * 0.5 + 0.68
    pulley_z = lowered_arbor_z

    num_benches = 2 if grade == 'GRADE_3' else 1
    bench_spacing_y = 1.2 if grade == 'GRADE_3' else 0.0
    lowered_arbor_z = bench_top - 0.20
    for b_idx in range(num_benches):
        y_off = (b_idx - 0.5) * bench_spacing_y
        b_mill_cy = mill_cy + y_off
        
        for tx in (mill_cx - bench_l * 0.32, mill_cx, mill_cx + bench_l * 0.32):
            for ly in (b_mill_cy - 0.33, b_mill_cy + 0.33):
                create_beveled_box(
                    bm, size=(0.13, 0.13, 0.85),
                    location=(tx, ly, z_floor + 0.425),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
                )
            create_beveled_box(
                bm, size=(0.14, 0.92, 0.12),
                location=(tx, b_mill_cy, z_floor + 0.06),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
        for ry in (b_mill_cy - 0.28, b_mill_cy + 0.28):
            create_beveled_box(
                bm, size=(bench_l, 0.14, 0.12),
                location=(mill_cx, ry, bench_top - 0.06),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
            )
        deck_l = (blade_x - 0.24) - (mill_cx - bench_l * 0.5)
        create_beveled_box(
            bm, size=(deck_l, 0.72, 0.07),
            location=(mill_cx - bench_l * 0.5 + deck_l * 0.5, b_mill_cy, bench_top - 0.023),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
        deck_r = (mill_cx + bench_l * 0.5) - (blade_x + 0.24)
        create_beveled_box(
            bm, size=(deck_r, 0.72, 0.07),
            location=(blade_x + 0.24 + deck_r * 0.5, b_mill_cy, bench_top - 0.023),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )

    _teeth = 26
    _bt = 0.05
    _root = blade_r * 0.86
    for b_idx in range(num_benches):
        y_off = (b_idx - 0.5) * (1.2 if grade == 'GRADE_3' else 0.0)
        curr_mill_cy = mill_cy + y_off
        
        _fring = []
        _bring = []
        for bi in range(_teeth * 2):
            _br = blade_r if bi % 2 == 0 else _root
            _ba = (2.0 * math.pi * bi) / (_teeth * 2.0)
            _bx = blade_x + math.cos(_ba) * _br
            _bz = lowered_arbor_z + math.sin(_ba) * _br
            _fring.append(bm.verts.new(Vector((_bx, curr_mill_cy + _bt * 0.5, _bz))))
            _bring.append(bm.verts.new(Vector((_bx, curr_mill_cy - _bt * 0.5, _bz))))
        _cf = bm.verts.new(Vector((blade_x, curr_mill_cy + _bt * 0.5, lowered_arbor_z)))
        _cb = bm.verts.new(Vector((blade_x, curr_mill_cy - _bt * 0.5, lowered_arbor_z)))
        _bfaces = []
        for bi in range(_teeth * 2):
            _bj = (bi + 1) % (_teeth * 2)
            _bfaces.append(bm.faces.new([_cf, _fring[_bj], _fring[bi]]))
            _bfaces.append(bm.faces.new([_cb, _bring[bi], _bring[_bj]]))
            _bfaces.append(bm.faces.new([_fring[_bj], _bring[_bj], _bring[bi], _fring[bi]]))
        for _bf in _bfaces:
            _bf.material_index = MAT_INDEX_IRON
            _bf.smooth = False
        _planar_uv_faces(bm, _bfaces, scale=0.35, axis=1)
        hub_faces = create_cylinder(
            bm, radius=0.09, height=0.14, segments=10,
            location=(blade_x, curr_mill_cy, lowered_arbor_z),
            rotation=(1.5708, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
        _planar_uv_faces(bm, hub_faces[-2:], scale=2.0, axis=1)
        bolt_faces = create_cylinder(
            bm, radius=0.045, height=0.20, segments=8,
            location=(blade_x, curr_mill_cy, lowered_arbor_z),
            rotation=(1.5708, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
        _planar_uv_faces(bm, bolt_faces[-2:], scale=2.0, axis=1)

    arb_y0 = mill_cy - 0.40
    arb_y1 = pulley_y + 0.10
    create_horizontal_cylinder(
        bm, radius_y=0.055, radius_z=0.055, length=arb_y1 - arb_y0, segments=10,
        location=(blade_x, (arb_y0 + arb_y1) * 0.5, lowered_arbor_z),
        rotation=(0.0, 0.0, 1.5708),
        mat_index=MAT_INDEX_IRON
    )
    for by in (mill_cy - 0.38, mill_cy + 0.38):
        bh = abs(lowered_arbor_z - bench_top) + 0.20
        create_beveled_box(
            bm, size=(0.16, 0.14, bh),
            location=(blade_x, by, bench_top - 0.10 + bh * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    create_cylinder(
        bm, radius=0.16, height=0.10, segments=12,
        location=(blade_x, pulley_y, pulley_z),
        rotation=(1.5708, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )

    n_rim = 12
    seg_len = (2.0 * math.pi * wheel_r / n_rim) * 1.06
    for side in (-1.0, 1.0):
        rim_y = mill_cy + side * wheel_w * 0.5
        for k in range(n_rim):
            a = (2.0 * math.pi * k) / n_rim
            create_beveled_box(
                bm, size=(seg_len, 0.13, 0.15),
                location=(wheel_x + math.cos(a) * wheel_r, rim_y, axle_z + math.sin(a) * wheel_r),
                rotation=(0.0, -a - 1.5708, 0.0),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
            )
        for k in range(4):
            a = (math.pi * k) / 2.0 + (0.0 if side < 0 else math.pi / 4.0)
            _slen = wheel_r - 0.08
            _sc = (0.05 + wheel_r - 0.03) * 0.5
            create_beveled_box(
                bm, size=(_slen, 0.10, 0.12),
                location=(wheel_x + math.cos(a) * _sc, rim_y, axle_z + math.sin(a) * _sc),
                rotation=(0.0, -a, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
    n_slats = max(18, int(round((2.0 * math.pi * wheel_r) / 0.30)))
    for k in range(n_slats):
        a = (2.0 * math.pi * k) / n_slats + math.pi / n_slats
        create_box(
            bm, size=(0.22, wheel_w, 0.055),
            location=(wheel_x + math.cos(a) * wheel_r, mill_cy, axle_z + math.sin(a) * wheel_r),
            rotation=(0.0, -a - 1.5708, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )

    create_horizontal_cylinder(
        bm, radius_y=0.17, radius_z=0.17, length=wheel_w + 0.30, segments=12,
        location=(wheel_x, mill_cy, axle_z),
        rotation=(0.0, 0.0, 1.5708),
        mat_index=MAT_INDEX_TIMBER
    )
    for hy in (mill_cy - wheel_w * 0.5 + 0.10, mill_cy + wheel_w * 0.5 - 0.10):
        create_cylinder(
            bm, radius=0.185, height=0.05, segments=12,
            location=(wheel_x, hy, axle_z),
            rotation=(1.5708, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
    ax_y0 = mill_cy - wheel_w * 0.5 - 0.60
    ax_y1 = pulley_y + 0.15
    create_horizontal_cylinder(
        bm, radius_y=0.085, radius_z=0.085, length=ax_y1 - ax_y0, segments=10,
        location=(wheel_x, (ax_y0 + ax_y1) * 0.5, axle_z),
        rotation=(0.0, 0.0, 1.5708),
        mat_index=MAT_INDEX_TIMBER
    )
    create_cylinder(
        bm, radius=0.30, height=0.10, segments=14,
        location=(wheel_x, pulley_y, axle_z),
        rotation=(1.5708, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )

    for sy in (mill_cy - wheel_w * 0.5 - 0.42, mill_cy + wheel_w * 0.5 + 0.42):
        create_beveled_box(
            bm, size=(1.50, 0.18, 0.15),
            location=(wheel_x, sy, z_floor + 0.075),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
        for fx in (wheel_x - 0.50, wheel_x + 0.50):
            create_beveled_box(
                bm, size=(0.42, 0.42, 0.24),
                location=(fx, sy, z_floor + 0.12),
                mat_index=MAT_INDEX_STONE, bevel_amount=0.02
            )
        leg_dz = axle_z - (z_floor + 0.24)
        leg_len = math.sqrt(0.50 * 0.50 + leg_dz * leg_dz) + 0.10
        lean = math.atan2(0.50, leg_dz)
        create_beveled_box(
            bm, size=(0.15, 0.15, leg_len),
            location=(wheel_x - 0.25, sy, (z_floor + 0.24 + axle_z) * 0.5),
            rotation=(0.0, lean, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(0.15, 0.15, leg_len),
            location=(wheel_x + 0.25, sy, (z_floor + 0.24 + axle_z) * 0.5),
            rotation=(0.0, -lean, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
        )
        create_box(
            bm, size=(0.18, 0.16, 0.16),
            location=(wheel_x, sy, axle_z),
            mat_index=MAT_INDEX_IRON
        )

    if sp['gear']:
        gear_r = 0.55 if grade == 'GRADE_2' else 0.68
        gear_y = mill_cy - wheel_w * 0.5 - 0.20
        gear_faces = create_cylinder(
            bm, radius=gear_r, height=0.13, segments=16,
            location=(wheel_x, gear_y, axle_z),
            rotation=(1.5708, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )
        _planar_uv_faces(bm, gear_faces[-2:], scale=0.8, axis=1)
        for gi in range(12):
            ga = (2.0 * math.pi * gi) / 12.0
            create_box(
                bm, size=(0.12, 0.15, 0.10),
                location=(wheel_x + math.cos(ga) * (gear_r + 0.04), gear_y, axle_z + math.sin(ga) * (gear_r + 0.04)),
                rotation=(0.0, -ga, 0.0),
                mat_index=MAT_INDEX_TIMBER
            )
