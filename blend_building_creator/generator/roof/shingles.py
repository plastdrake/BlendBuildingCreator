"""
3D Roof Shingles Generator with whimsical jitter and dormer aperture clipping.
Adheres to Single Responsibility and Open/Closed principles.
"""

import math
import random
from mathutils import Vector
from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_SHINGLES

def build_shingle_layers(bm, x_min, x_max, y_min, y_max, z_base, roof_height=2.8,
                         rows=6, seed=42, overhang=0.45, sway_amount=0.25, roof_style='SWAY',
                         abut_back=False, roof_flare=0.35, dormer_apertures=None):
    """
    Generates chunky stylized overlapping shingle rows that match the exact roof slope
    and sway sag profile, offset safely above the timber deck to eliminate clipping and overlap.
    abut_back: If True, shingles stop flush at y_max with zero rear overhang.
    """
    rng = random.Random(seed)
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max if abut_back else (y_max + overhang)
    total_w = rx_max - rx_min
    total_d = ry_max - ry_min
    
    cx = (rx_min + rx_max) * 0.5
    half_w = total_w * 0.5
    ez = z_base - 0.12
    
    shingle_w = 0.98
    usable_d = max(0.5, total_d - shingle_w)
    cols = max(3, int(usable_d / (shingle_w * 0.78)) + 1)
    step_y = usable_d / max(1, cols - 1)
    
    for side in [-1, 1]:
        tilt_sign = 1 if side < 0 else -1
        
        for r in range(rows):
            t = (r + 0.45) / max(1, rows)
            
            y_positions = [ry_min + shingle_w * 0.5 + c * step_y for c in range(cols)]
            if r % 2 == 1:
                shifted = [y + step_y * 0.5 for y in y_positions[:-1]]
                y_positions = [ry_min + shingle_w * 0.5] + shifted + [ry_max - shingle_w * 0.5]
            
            for cur_y in y_positions:
                u = 1.0 - t
                if dormer_apertures:
                    skip_shingle = False
                    for ap in dormer_apertures:
                        if ap.get('side') == side:
                            if (ap['y_min'] + 0.02) <= cur_y <= (ap['y_max'] - 0.02) and ap['u_min'] <= u <= ap['u_max']:
                                skip_shingle = True
                                break
                    if skip_shingle:
                        continue
                
                t_y = max(0.0, min(1.0, (cur_y - ry_min) / max(0.01, total_d)))
                
                sag = math.sin(t_y * math.pi) * sway_amount if (roof_style == 'SWAY') else 0.0
                rz = z_base + roof_height - sag
                
                delta_z = rz - ez
                delta_x = half_w
                drop_frac = (1.0 - roof_flare) * u + roof_flare * (1.0 - (1.0 - u) ** 2)
                cur_z = rz - drop_frac * delta_z
                cur_x = cx + side * (u * half_w)
                
                slope_mult = (1.0 - roof_flare) + roof_flare * 2.0 * (1.0 - u)
                pitch_ang = math.atan2(delta_z * slope_mult, delta_x)
                slope_len = math.sqrt(delta_x * delta_x + delta_z * delta_z)
                shingle_l = (slope_len / rows) * 2.85
                shingle_t = 0.09
                
                norm_x = math.sin(pitch_ang)
                norm_z = math.cos(pitch_ang)
                
                cur_x += side * (norm_x * 0.14)
                cur_z += norm_z * 0.14
                
                jitter_y = (rng.random() - 0.5) * 0.03
                jitter_tilt = (rng.random() - 0.5) * 0.03
                jitter_rot = (rng.random() - 0.5) * 0.04
                
                slope_angle = -pitch_ang if side < 0 else pitch_ang
                overlap_tilt = 0.05 * tilt_sign
                final_angle = slope_angle + overlap_tilt + jitter_tilt
                
                create_beveled_box(
                    bm,
                    size=(shingle_l, shingle_w, shingle_t),
                    location=(cur_x, cur_y + jitter_y, cur_z),
                    rotation=(0.0, final_angle, jitter_rot),
                    mat_index=MAT_INDEX_SHINGLES,
                    bevel_amount=0.032,
                    bevel_segments=3
                )
