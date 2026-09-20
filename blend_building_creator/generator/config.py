"""
Typed generation context.

``generate_building`` computes a large amount of layout state (floor heights,
per-floor wall bounds, resolved balcony facades, the main door position, ...)
and then hands slices of it to the accessory builders. ``BuildingContext``
packages that state once so the accessory dispatch can be a small, typed
function instead of a 100-line block of ``getattr`` calls buried in the
orchestrator.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


Bounds = Tuple[float, float, float, float]


@dataclass
class BuildingContext:
    """Resolved layout state shared by the accessory builders."""

    num_floors: int
    floor_h: float
    found_h: float
    floor_wall_bounds: Dict[int, Bounds]
    hx: float
    hy: float
    base_w: float
    base_d: float
    raw_wing_d: float
    main_door_cx: float
    main_door_yf: float
    shape: str
    seed: int
    plank_dir: str
    floor_balc_side: Dict[int, str] = field(default_factory=dict)
    active_balc_floors: List[int] = field(default_factory=list)
    # Mini-wing outcrop slots: {floor: [(facade, offset, width, depth), ...]}
    # laid out once so the walls, the timber masks and the outcrop builders all
    # agree (the size travels with the slot for the random-size option).
    mini_wing_spread: Dict[int, Any] = field(default_factory=dict)
    # Extended state populated by the setup/floor phases and consumed by the
    # roof, archetype and accessory phases.
    wall_t: float = 0.28
    cantilever: float = 0.0
    open_timber: bool = False
    effective_archetype: str = 'NONE'
    wings: List[Any] = field(default_factory=list)
    has_wing: bool = False
    wing_floors: int = 1
    raw_wing_w: float = 3.5
    wing_placement: str = 'FRONT'
    wing_side: str = 'RIGHT'
    total_height: float = 0.0
    floor_stair_holes: Dict[int, Any] = field(default_factory=dict)
    # World-space window sill centres: {floor: {facade: [(x, y, sill_z), ...]}}
    # recorded by the wall phase so accessories can align to real windows.
    window_centers: Dict[int, Any] = field(default_factory=dict)
    wx_base_min: float = 0.0
    wx_base_max: float = 0.0
    wy_base_min: float = 0.0
    wy_base_max: float = 0.0
    top_z: float = 0.0
    top_hx: float = 0.0
    top_hy: float = 0.0
    is_rotated_roof: bool = False

    def bounds_for(self, floor_idx: int) -> Bounds:
        """Wall bounds for a floor, falling back to the base footprint."""
        return self.floor_wall_bounds.get(floor_idx, (-self.hx, self.hx, -self.hy, self.hy))
