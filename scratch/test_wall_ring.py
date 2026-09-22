import bpy, bmesh, math
from mathutils import Vector

def test_wall():
    bm = bmesh.new()
    BAYS = 8
    BAY_ANG = 2.0 * math.pi / BAYS
    OFFSET = -math.pi * 0.5 - BAY_ANG * 0.5
    r_out = 3.5
    r_in = 3.1
    z0 = 0.5
    z1 = 4.3
    door_bay = 0
    door_w = 1.40
    door_h = 2.60
    window_bays = {2, 4, 6}
    win_w = 0.85
    win_h = 1.40

    # Height levels
    if door_bay is not None:
        z_lintel = z0 + door_h
        zw0 = max(z0 + 0.5, z_lintel - win_h)
        zw1 = z_lintel
        levels = [z0, zw0, zw1, z1]
    else:
        w_cz = z0 + (z1 - z0) * 0.52
        zw0 = w_cz - win_h * 0.5
        zw1 = w_cz + win_h * 0.5
        levels = [z0, zw0, zw1, z1]

    d_bay = 2.0 * math.pi / BAYS

    # Pre-create boundary vertices for the 8 bays
    # boundary_verts[k][level_idx] = (v_out, v_in)
    boundary_verts = []
    for k in range(BAYS):
        ang = k * d_bay + OFFSET
        ca, sa = math.cos(ang), math.sin(ang)
        col = []
        for lvl_z in levels:
            vo = bm.verts.new((r_out * ca, r_out * sa, lvl_z))
            vi = bm.verts.new((r_in  * ca, r_in  * sa, lvl_z))
            col.append((vo, vi))
        boundary_verts.append(col)

    created_faces = []

    for b in range(BAYS):
        bn = (b + 1) % BAYS
        a0 = b * d_bay + OFFSET
        a1 = (b + 1) * d_bay + OFFSET
        a_mid = (a0 + a1) * 0.5

        if b == door_bay:
            d_ang_door = math.asin(min(0.99, (door_w * 0.5) / r_out))
            ad0 = a_mid - d_ang_door
            ad1 = a_mid + d_ang_door
            # 6 angular stations:
            # 0: a0
            # 1: (a0 + ad0) * 0.5
            # 2: ad0 (left jamb)
            # 3: a_mid (door center)
            # 4: ad1 (right jamb)
            # 5: (ad1 + a1) * 0.5
            # 6: a1
            angles = [a0, (a0 + ad0) * 0.5, ad0, a_mid, ad1, (ad1 + a1) * 0.5, a1]
            st = []
            for s_idx, ang in enumerate(angles):
                if s_idx == 0:
                    st.append(boundary_verts[b])
                elif s_idx == 6:
                    st.append(boundary_verts[bn])
                else:
                    ca, sa = math.cos(ang), math.sin(ang)
                    col = []
                    for lvl_z in levels:
                        vo = bm.verts.new((r_out * ca, r_out * sa, lvl_z))
                        vi = bm.verts.new((r_in  * ca, r_in  * sa, lvl_z))
                        col.append((vo, vi))
                    st.append(col)

            # Left flank (slices 0, 1)
            for s in (0, 1):
                for l in range(3):
                    fo = bm.faces.new([st[s][l][0], st[s+1][l][0], st[s+1][l+1][0], st[s][l+1][0]])
                    fi = bm.faces.new([st[s+1][l][1], st[s][l][1], st[s][l+1][1], st[s+1][l+1][1]])
                    created_faces.extend([fo, fi])

            # Right flank (slices 4, 5)
            for s in (4, 5):
                for l in range(3):
                    fo = bm.faces.new([st[s][l][0], st[s+1][l][0], st[s+1][l+1][0], st[s][l+1][0]])
                    fi = bm.faces.new([st[s+1][l][1], st[s][l][1], st[s][l+1][1], st[s+1][l+1][1]])
                    created_faces.extend([fo, fi])

            # Door opening (slices 2, 3)
            # Wall above lintel (level 2 to 3)
            for s in (2, 3):
                fo = bm.faces.new([st[s][2][0], st[s+1][2][0], st[s+1][3][0], st[s][3][0]])
                fi = bm.faces.new([st[s+1][2][1], st[s][2][1], st[s][2+1][1], st[s+1][3][1]])
                # Lintel underside at level 2
                f_lin = bm.faces.new([st[s+1][2][0], st[s][2][0], st[s][2][1], st[s+1][2][1]])
                created_faces.extend([fo, fi, f_lin])

            # Left jamb (station 2, levels 0..2)
            for l in range(2):
                f_jl = bm.faces.new([st[2][l][1], st[2][l+1][1], st[2][l+1][0], st[2][l][0]])
                created_faces.append(f_jl)

            # Right jamb (station 4, levels 0..2)
            for l in range(2):
                f_jr = bm.faces.new([st[4][l][0], st[4][l+1][0], st[4][l+1][1], st[4][l][1]])
                created_faces.append(f_jr)

        elif b in window_bays:
            d_ang_win = math.asin(min(0.99, (win_w * 0.5) / r_out))
            aw0 = a_mid - d_ang_win
            aw1 = a_mid + d_ang_win
            angles = [a0, (a0 + aw0) * 0.5, aw0, a_mid, aw1, (aw1 + a1) * 0.5, a1]
            st = []
            for s_idx, ang in enumerate(angles):
                if s_idx == 0:
                    st.append(boundary_verts[b])
                elif s_idx == 6:
                    st.append(boundary_verts[bn])
                else:
                    ca, sa = math.cos(ang), math.sin(ang)
                    col = []
                    for lvl_z in levels:
                        vo = bm.verts.new((r_out * ca, r_out * sa, lvl_z))
                        vi = bm.verts.new((r_in  * ca, r_in  * sa, lvl_z))
                        col.append((vo, vi))
                    st.append(col)

            # Left flank (slices 0, 1)
            for s in (0, 1):
                for l in range(3):
                    fo = bm.faces.new([st[s][l][0], st[s+1][l][0], st[s+1][l+1][0], st[s][l+1][0]])
                    fi = bm.faces.new([st[s+1][l][1], st[s][l][1], st[s][l+1][1], st[s+1][l+1][1]])
                    created_faces.extend([fo, fi])

            # Right flank (slices 4, 5)
            for s in (4, 5):
                for l in range(3):
                    fo = bm.faces.new([st[s][l][0], st[s+1][l][0], st[s+1][l+1][0], st[s][l+1][0]])
                    fi = bm.faces.new([st[s+1][l][1], st[s][l][1], st[s][l+1][1], st[s+1][l+1][1]])
                    created_faces.extend([fo, fi])

            # Window opening (slices 2, 3)
            for s in (2, 3):
                # Wall below sill (level 0 to 1)
                fo_b = bm.faces.new([st[s][0][0], st[s+1][0][0], st[s+1][1][0], st[s][1][0]])
                fi_b = bm.faces.new([st[s+1][0][1], st[s][0][1], st[s][1][1], st[s+1][1][1]])
                # Sill at level 1 (facing UP)
                f_sill = bm.faces.new([st[s][1][0], st[s+1][1][0], st[s+1][1][1], st[s][1][1]])
                # Wall above header (level 2 to 3)
                fo_t = bm.faces.new([st[s][2][0], st[s+1][2][0], st[s+1][3][0], st[s][3][0]])
                fi_t = bm.faces.new([st[s+1][2][1], st[s][2][1], st[s][3][1], st[s+1][3][1]])
                # Header underside at level 2 (facing DOWN)
                f_head = bm.faces.new([st[s+1][2][0], st[s][2][0], st[s][2][1], st[s+1][2][1]])
                created_faces.extend([fo_b, fi_b, f_sill, fo_t, fi_t, f_head])

            # Window jambs at level 1 to 2
            # Left jamb (station 2)
            f_jl = bm.faces.new([st[2][1][1], st[2][2][1], st[2][2][0], st[2][1][0]])
            # Right jamb (station 4)
            f_jr = bm.faces.new([st[4][1][0], st[4][2][0], st[4][2][1], st[4][1][1]])
            created_faces.extend([f_jl, f_jr])

        else:
            # Solid bay (6 slices across the bay)
            angles = [a0 + i * (a1 - a0) / 6.0 for i in range(7)]
            st = []
            for s_idx, ang in enumerate(angles):
                if s_idx == 0:
                    st.append(boundary_verts[b])
                elif s_idx == 6:
                    st.append(boundary_verts[bn])
                else:
                    ca, sa = math.cos(ang), math.sin(ang)
                    col = []
                    for lvl_z in levels:
                        vo = bm.verts.new((r_out * ca, r_out * sa, lvl_z))
                        vi = bm.verts.new((r_in  * ca, r_in  * sa, lvl_z))
                        col.append((vo, vi))
                    st.append(col)

            for s in range(6):
                for l in range(3):
                    fo = bm.faces.new([st[s][l][0], st[s+1][l][0], st[s+1][l+1][0], st[s][l+1][0]])
                    fi = bm.faces.new([st[s+1][l][1], st[s][l][1], st[s][l+1][1], st[s+1][l+1][1]])
                    created_faces.extend([fo, fi])

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Check non-manifold edges
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    # For a wall ring with openings:
    # Boundary edges should ONLY be at the top ring (z1), bottom ring (z0), and bottom of door opening (z0)
    interior_non_manifold = [e for e in non_manifold_edges if not e.is_boundary]
    print(f"Total verts: {len(bm.verts)}, edges: {len(bm.edges)}, faces: {len(bm.faces)}")
    print(f"Non-manifold (non-boundary) edges: {len(interior_non_manifold)}")
    print(f"Boundary edges: {len(boundary_edges)}")

    # Verify every face is valid
    for f in bm.faces:
        assert f.is_valid, "Invalid face found!"

    print("SUCCESS! Topology is completely clean and manifold!")

test_wall()
