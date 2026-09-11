"""
Roof Generator Package for Stylized Fantasy Buildings.
Modularized following SOLID, GRASP, and DRY principles:
- sway_roof: Curved bell-cast sway roofs
- gable_roof: Straight medieval gable roofs
- turret_roof: Conical turret spire roofs
- shingles: Layered 3D roof shingles with aperture clipping
- dormer: Bell-cast flared dormer windows
- features: Bargeboards, roof turrets, chimneys, hoist beams
- gable_wall: Shared DRY gable end wall and log siding builders
"""

from .sway_roof import build_sway_roof
from .gable_roof import build_gable_roof
from .turret_roof import build_conical_turret_roof
from .shingles import build_shingle_layers
from .dormer import build_dormer
from .features import (
    build_curved_bargeboards,
    build_roof_turret,
    build_fantasy_chimney,
    build_hoist_beam
)
from .gable_wall import (
    build_gable_end_wall,
    build_gable_physical_siding
)

__all__ = [
    'build_sway_roof',
    'build_gable_roof',
    'build_conical_turret_roof',
    'build_shingle_layers',
    'build_dormer',
    'build_roof_turret',
    'build_fantasy_chimney',
    'build_hoist_beam',
    'build_curved_bargeboards',
    'build_gable_end_wall',
    'build_gable_physical_siding',
]
