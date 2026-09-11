"""
Conical Wizard Turret Roof Generator.
Adheres to Single Responsibility principle.
"""

import math
from mathutils import Vector
from ..mesh_utils import create_cone, create_cylinder
from ..materials import MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER, MAT_INDEX_STONE

def build_conical_turret_roof(bm, center_pos, radius=2.2, height=3.8, segments=12):
    """
    Builds a wizard turret / conical roof with flared eaves and a finial spire.
    """
    cx, cy, z_base = center_pos
    # Main cone — assign shingle UV so tiling is visible (cylindrical unwrap)
    uv_layer_c = bm.loops.layers.uv.verify()
    cone_faces = create_cone(
        bm,
        radius1=radius,
        radius2=0.08,
        height=height,
        segments=segments,
        location=(cx, cy, z_base + height * 0.5),
        mat_index=MAT_INDEX_SHINGLES
    )
    for f in cone_faces:
        if f.material_index == MAT_INDEX_SHINGLES:
            for loop in f.loops:
                co = loop.vert.co
                ang = math.atan2(co.y - cy, co.x - cx)
                u = (ang + math.pi) / (2.0 * math.pi) * 1.0
                v = co.z * 0.32
                loop[uv_layer_c].uv = Vector((u, v))
    # Eaves rim
    create_cylinder(
        bm,
        radius=radius + 0.12,
        height=0.20,
        segments=segments,
        location=(cx, cy, z_base + 0.10),
        mat_index=MAT_INDEX_TIMBER
    )
    # Spire / finial
    create_cone(
        bm,
        radius1=0.12,
        radius2=0.02,
        height=1.0,
        segments=8,
        location=(cx, cy, z_base + height + 0.5),
        mat_index=MAT_INDEX_STONE
    )
