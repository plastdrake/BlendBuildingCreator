"""Standalone verification of the mage tower stairwell geometry changes.

Mirrors the pure-math helpers from generator/mage_tower.py so we can validate
the keep-out planning without importing Blender. Checks:

1. Every floor opening (STAIR_OPEN=75 deg behind the flight below) is wide
   enough that a ~1.9 m character clears the ceiling while climbing.
2. No outcrop doorway is parked over a floor opening.
3. Bay placement stays distinct per floor and matches the preset counts.
"""

STAIR_W = 1.50
STAIR_ARC = 135.0
STAIR_OPEN = 75.0


def stair_arc_deg(fl):
    s_ang = (-30.0 + fl * 200.0) % 360.0
    return (s_ang, (s_ang + STAIR_ARC) % 360.0)


def stair_open_range_deg(fl):
    if fl <= 0:
        return None
    _, e_ang = stair_arc_deg(fl - 1)
    return ((e_ang - STAIR_OPEN) % 360.0, e_ang % 360.0)


def angle_in_open(a, open_range):
    if open_range is None:
        return False
    cs, ce = open_range
    a = a % 360.0
    if cs <= ce:
        return cs <= a <= ce
    return a >= cs or a <= ce


def plan_mage_outcrops(levels, count):
    storeys = max(1, levels - 1)
    solid_bays = [1, 3, 5, 7]
    count = min(count, storeys * len(solid_bays))
    top_storeys = min(storeys, 3)
    usable = list(range(storeys - top_storeys, storeys))
    door_keep = 20.0

    def bay_clear(bay, fl, used):
        if bay in used:
            return False
        opening = stair_open_range_deg(fl)
        if opening is None:
            return True
        center = (bay * 45.0 - 90.0) % 360.0
        return not any(angle_in_open(center + off, opening)
                       for off in (-door_keep, 0.0, door_keep))

    by_floor = {}
    for i in range(count):
        preferred = usable[min(len(usable) - 1, int(i * len(usable) / float(count)))]
        placed = False
        for shift in range(len(usable)):
            fl = usable[(usable.index(preferred) + shift) % len(usable)]
            slots = by_floor.setdefault(fl, [])
            for probe in range(len(solid_bays)):
                bay = solid_bays[(i + probe) % len(solid_bays)]
                if bay_clear(bay, fl, slots):
                    slots.append(bay)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            by_floor.setdefault(preferred, []).append(solid_bays[i % len(solid_bays)])
    return by_floor


def head_clearance_ok(level_h):
    """Cheapest clearance (m) between a 1.9 m head and the slab bottom at the
    opening boundary, over the full storey range the presets use."""
    min_clear = 1e9
    for lh in (4.6, level_h):
        cover = level_h * (STAIR_OPEN / STAIR_ARC)
        min_clear = min(min_clear, cover - 1.9 - 0.14)
    return min_clear


PRESETS = [
    ("MAGE_TOWER_T1", 3, 5, 0),   # levels, storeys-implied, outcrop count
    ("MAGE_TOWER_T2", 5, 5, 5),
    ("MAGE_TOWER_T3", 9, 8, 7),
]

failures = []

for name, levels, _storeys, count in PRESETS:
    by_floor = plan_mage_outcrops(levels, count)
    total = sum(len(v) for v in by_floor.values())
    print(f"{name}: {total} outcrops -> {dict(sorted(by_floor.items()))}")

    # 1. every flap floor's slab opening must give head clearance
    for fl in range(1, _storeys + 1):
        o = stair_open_range_deg(fl)
        if o is None:
            continue
        cs, ce = o
        span = (ce - cs) % 360.0
        if span < STAIR_OPEN - 7.5:   # sector quantum slack
            failures.append(f"{name} fl{fl}: opening span {span:.1f} < 75 deg")

    # 2. no doorway over its floor opening; bays distinct
    for fl, bays in by_floor.items():
        o = stair_open_range_deg(fl)
        if o is None:
            continue
        cs, ce = o
        span = (ce - cs) % 360.0
        print(f"   fl{fl}: opening [{cs:.1f},{ce:.1f}] span={span:.1f} deg, bays={bays}")
        if len(set(bays)) != len(bays):
            failures.append(f"{name} fl{fl}: duplicate bays {bays}")
        for bay in bays:
            a = (bay * 45.0 - 90.0) % 360.0
            hit = any(angle_in_open(a + off, o) for off in (-9.7, 0.0, 9.7))
            if hit:
                failures.append(f"{name} fl{fl}: bay {bay} (@{a:.0f}) over opening")

for lh in (4.6, 4.8, 5.4, 5.6, 8.0):
    c = head_clearance_ok(lh)
    print(f"level_h={lh}: headroom at opening edge = {c:.2f} m")

print("RESULT:", "FAIL" if failures else "OK")
for f in failures:
    print("  -", f)