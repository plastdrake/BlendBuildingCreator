"""Footprint / facade layout helpers.

Pure geometry math for compound footprints (L / T / U), wing bounds per floor
and evenly-spaced facade openings. Extracted from ``building.py`` so the
orchestrator no longer owns footprint logic.
"""


def get_facade_window_positions(span_min, span_max, target_spacing=2.4, min_margin=0.85):
    """
    Computes dynamic window center positions along a facade segment.
    Automatically scales window count smoothly as width or depth increases.
    """
    length = span_max - span_min
    avail = length - min_margin * 2.0
    if avail < 0.4:
        return []

    count = max(1, int(round(avail / target_spacing)))
    if count == 1:
        return [(span_min + span_max) * 0.5]
    step = avail / max(1, count - 1)
    return [span_min + min_margin + i * step for i in range(count)]


def get_wings_setup(shape, wing_placement, wing_side, base_w, base_d, raw_wing_w, raw_wing_d, courtyard_w):
    """
    Computes base boundary coordinates and alignment descriptors for compound building shapes:
    L-Shape, T-Shape, and U-Shape (dual wings forming a courtyard).
    Supports FRONT, BACK, LEFT, RIGHT facade attachments.
    """
    wings = []
    if shape == 'L_SHAPE':
        if wing_placement == 'FRONT':
            w_w = min(base_w * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wx1, wx2 = -base_w * 0.5, -base_w * 0.5 + w_w
                align = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5 - w_w, base_w * 0.5
                align = 'RIGHT'
            wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
            wings.append({'id': 0, 'wall': 'FRONT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'BACK':
            w_w = min(base_w * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wx1, wx2 = -base_w * 0.5, -base_w * 0.5 + w_w
                align = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5 - w_w, base_w * 0.5
                align = 'RIGHT'
            wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
            wings.append({'id': 0, 'wall': 'BACK', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'LEFT':
            w_w = min(base_d * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wy1, wy2 = -base_d * 0.5, -base_d * 0.5 + w_w
                align = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5 - w_w, base_d * 0.5
                align = 'BACK'
            wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
            wings.append({'id': 0, 'wall': 'LEFT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'RIGHT':
            w_w = min(base_d * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wy1, wy2 = -base_d * 0.5, -base_d * 0.5 + w_w
                align = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5 - w_w, base_d * 0.5
                align = 'BACK'
            wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
            wings.append({'id': 0, 'wall': 'RIGHT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
    elif shape == 'T_SHAPE':
        if wing_placement in ('FRONT', 'BACK'):
            w_w = min(base_w * 0.85, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            hw = w_w * 0.5
            wx1, wx2 = -hw, hw
            if wing_placement == 'FRONT':
                wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
                wall = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
                wall = 'BACK'
            wings.append({'id': 0, 'wall': wall, 'align': 'CENTER', 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        else: # LEFT or RIGHT
            w_w = min(base_d * 0.85, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            hd = w_w * 0.5
            wy1, wy2 = -hd, hd
            if wing_placement == 'LEFT':
                wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
                wall = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
                wall = 'RIGHT'
            wings.append({'id': 0, 'wall': wall, 'align': 'CENTER', 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
    elif shape == 'U_SHAPE':
        # Dual wings forming a central courtyard
        if wing_placement in ('FRONT', 'BACK'):
            max_w = max(1.8, (base_w - courtyard_w) * 0.5)
            w_w = min(max_w, max(1.8, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            wx1_l, wx2_l = -base_w * 0.5, -base_w * 0.5 + w_w
            wx1_r, wx2_r = base_w * 0.5 - w_w, base_w * 0.5
            if wing_placement == 'FRONT':
                wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
                wall = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
                wall = 'BACK'
            wings.append({'id': 0, 'wall': wall, 'align': 'LEFT', 'base': (wx1_l, wx2_l, wy1, wy2), 'w': w_w, 'd': w_d})
            wings.append({'id': 1, 'wall': wall, 'align': 'RIGHT', 'base': (wx1_r, wx2_r, wy1, wy2), 'w': w_w, 'd': w_d})
        else: # LEFT or RIGHT
            max_w = max(1.8, (base_d - courtyard_w) * 0.5)
            w_w = min(max_w, max(1.8, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            wy1_f, wy2_f = -base_d * 0.5, -base_d * 0.5 + w_w
            wy1_b, wy2_b = base_d * 0.5 - w_w, base_d * 0.5
            if wing_placement == 'LEFT':
                wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
                wall = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
                wall = 'RIGHT'
            wings.append({'id': 0, 'wall': wall, 'align': 'FRONT', 'base': (wx1, wx2, wy1_f, wy2_f), 'w': w_w, 'd': w_d})
            wings.append({'id': 1, 'wall': wall, 'align': 'BACK', 'base': (wx1, wx2, wy1_b, wy2_b), 'w': w_w, 'd': w_d})
    return wings


def compute_fl_wing_bounds(wing, fl_idx, fl_overhang, x_min, x_max, y_min, y_max):
    """Calculates per-floor coordinates of a wing factoring in cantilever overhang."""
    wall = wing['wall']
    w_w = wing['w']
    w_d = wing['d']
    align = wing['align']
    if wall == 'FRONT':
        if align == 'LEFT':
            wx1, wx2 = x_min, x_min + (w_w + fl_overhang * 2.0)
        elif align == 'RIGHT':
            wx1, wx2 = x_max - (w_w + fl_overhang * 2.0), x_max
        else: # CENTER
            hw = (w_w + fl_overhang * 2.0) * 0.5
            wx1, wx2 = -hw, hw
        wy1 = y_min - w_d
        wy2 = y_min
        return (wx1, wx2, wy1, wy2)
    elif wall == 'BACK':
        if align == 'LEFT':
            wx1, wx2 = x_min, x_min + (w_w + fl_overhang * 2.0)
        elif align == 'RIGHT':
            wx1, wx2 = x_max - (w_w + fl_overhang * 2.0), x_max
        else:
            hw = (w_w + fl_overhang * 2.0) * 0.5
            wx1, wx2 = -hw, hw
        wy1 = y_max
        wy2 = y_max + w_d
        return (wx1, wx2, wy1, wy2)
    elif wall == 'LEFT':
        if align == 'FRONT':
            wy1, wy2 = y_min, y_min + (w_w + fl_overhang * 2.0)
        elif align == 'BACK':
            wy1, wy2 = y_max - (w_w + fl_overhang * 2.0), y_max
        else:
            hd = (w_w + fl_overhang * 2.0) * 0.5
            wy1, wy2 = -hd, hd
        wx1 = x_min - w_d
        wx2 = x_min
        return (wx1, wx2, wy1, wy2)
    elif wall == 'RIGHT':
        if align == 'FRONT':
            wy1, wy2 = y_min, y_min + (w_w + fl_overhang * 2.0)
        elif align == 'BACK':
            wy1, wy2 = y_max - (w_w + fl_overhang * 2.0), y_max
        else:
            hd = (w_w + fl_overhang * 2.0) * 0.5
            wy1, wy2 = -hd, hd
        wx1 = x_max
        wx2 = x_max + w_d
        return (wx1, wx2, wy1, wy2)
    return (0.0, 0.0, 0.0, 0.0)
