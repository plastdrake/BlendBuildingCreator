import re
import os

filepath = r"d:\BlendBuildingCreator\blend_building_creator\presets.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update base_settings
base_settings_old = """    return {
        # Footprint & floors
        'building_shape': 'RECTANGLE',
        'wing_placement': 'FRONT', 'wing_side': 'RIGHT',
        'num_floors': 1, 'wing_floors': 1, 'floor_height': 2.8,
        'width': 8.0, 'depth': 8.0, 'wing_width': 3.5, 'wing_depth': 3.0,
        'courtyard_width': 3.5, 'wall_thickness': 0.28,
        'has_cantilever': False, 'overhang_mode': 'SECOND_FLOOR_ONLY',
        'cantilever_overhang': 0.35, 'wonkiness': 0.0,
        'has_foundation': True, 'foundation_type': 'STONE',
        'foundation_height': 0.5, 'ground_floor_stone': False,
        'has_front_steps': True,
        # Interior
        'has_stairs': True, 'stair_style': 'STRAIGHT', 'stair_width': 1.1,
        'has_ceiling_beams': True,
        'has_interior_walls': True, 'interior_partition_style': 'AUTO',
        'interior_wall_thickness': 0.16,
        # Openings
        'has_front_door': True, 'front_door_offset_x': 0.0,
        'has_back_door': False, 'has_back_portal': False,
        'has_side_door': False, 'side_door_facade': 'RIGHT',
        'door_width': 1.2, 'door_height': 2.2, 'door_angle': 0.0,
        'door_shape': 'SQUARE',
        'has_windows': True, 'window_spacing': 2.4, 'window_density': 1.0,
        'window_width': 0.85, 'window_height': 1.2,"""

base_settings_new = """    return {
        # Footprint & floors
        'building_shape': 'RECTANGLE',
        'wing_placement': 'FRONT', 'wing_side': 'RIGHT',
        'num_floors': 1, 'wing_floors': 1, 'floor_height': 3.6,
        'width': 8.0, 'depth': 8.0, 'wing_width': 3.5, 'wing_depth': 3.0,
        'courtyard_width': 3.5, 'wall_thickness': 0.28,
        'has_cantilever': False, 'overhang_mode': 'SECOND_FLOOR_ONLY',
        'cantilever_overhang': 0.35, 'wonkiness': 0.0,
        'has_foundation': True, 'foundation_type': 'STONE',
        'foundation_height': 0.5, 'ground_floor_stone': False,
        'has_front_steps': True,
        # Interior
        'has_stairs': True, 'stair_style': 'STRAIGHT', 'stair_width': 1.45,
        'has_ceiling_beams': True,
        'has_interior_walls': True, 'interior_partition_style': 'AUTO',
        'interior_wall_thickness': 0.16,
        # Openings
        'has_front_door': True, 'front_door_offset_x': 0.0,
        'has_back_door': False, 'has_back_portal': False,
        'has_side_door': False, 'side_door_facade': 'RIGHT',
        'door_width': 1.45, 'door_height': 2.80, 'door_angle': 0.0,
        'door_shape': 'SQUARE',
        'has_windows': True, 'window_spacing': 2.4, 'window_density': 1.0,
        'window_width': 0.95, 'window_height': 1.40,"""

if base_settings_old in content:
    content = content.replace(base_settings_old, base_settings_new, 1)
    print("Replaced base_settings successfully.")
else:
    print("Warning: base_settings_old not found exactly.")

# Mapping scale dictionaries
floor_h_map = {
    '2.6': '3.4',
    '2.7': '3.5',
    '2.8': '3.6',
    '2.9': '3.7',
    '3.0': '3.8',
    '3.1': '3.9',
    '3.2': '4.0',
    '3.3': '4.1',
    '3.4': '4.2',
    '3.5': '4.3',
    '3.6': '4.4',
    '3.8': '4.6',
    '4.0': '4.8',
}

door_w_map = {
    '0.95': '1.40',
    '1.0': '1.40',
    '1.00': '1.40',
    '1.05': '1.45',
    '1.1': '1.45',
    '1.10': '1.45',
    '1.15': '1.50',
    '1.2': '1.50',
    '1.20': '1.50',
    '1.25': '1.55',
    '1.3': '1.55',
    '1.30': '1.55',
    '1.4': '1.60',
    '1.40': '1.60',
}

door_h_map = {
    '2.1': '2.75',
    '2.2': '2.80',
    '2.20': '2.80',
    '2.25': '2.85',
    '2.3': '2.85',
    '2.30': '2.85',
    '2.35': '2.90',
    '2.4': '2.90',
    '2.40': '2.90',
    '2.45': '2.95',
    '2.5': '2.95',
    '2.50': '2.95',
}

stair_w_map = {
    '0.9': '1.40',
    '0.95': '1.40',
    '1.0': '1.40',
    '1.00': '1.40',
    '1.05': '1.45',
    '1.1': '1.45',
    '1.10': '1.45',
    '1.15': '1.50',
    '1.2': '1.50',
    '1.20': '1.50',
    '1.25': '1.55',
    '1.3': '1.55',
    '1.30': '1.55',
}

# Function to scale properties inside PRESETS
def scale_preset_lines(text):
    # Scale floor_height
    for old_v, new_v in floor_h_map.items():
        text = re.sub(rf"'floor_height':\s*{re.escape(old_v)}\b", f"'floor_height': {new_v}", text)
    # Scale door_width
    for old_v, new_v in door_w_map.items():
        text = re.sub(rf"'door_width':\s*{re.escape(old_v)}\b", f"'door_width': {new_v}", text)
    # Scale door_height
    for old_v, new_v in door_h_map.items():
        text = re.sub(rf"'door_height':\s*{re.escape(old_v)}\b", f"'door_height': {new_v}", text)
    # Scale stair_width
    for old_v, new_v in stair_w_map.items():
        text = re.sub(rf"'stair_width':\s*{re.escape(old_v)}\b", f"'stair_width': {new_v}", text)
    return text

content = scale_preset_lines(content)

# Specific Artisan updates:
# T1: num_floors = 2, has_stairs = True
# T2: num_floors = 3, has_stairs = True
# T3: num_floors = 3 or 4, has_stairs = True
artisan_families = [
    'ARTISAN_BAKERY', 'ARTISAN_TAILOR', 'ARTISAN_TOOLSMITH', 'ARTISAN_JEWELER',
    'ARTISAN_BREWERY', 'ARTISAN_FISHER', 'ARTISAN_FURNITURE_MAKER', 'ARTISAN_BUTCHER'
]

for fam in artisan_families:
    # T1
    t1_key = f"'{fam}_T1':"
    if t1_key in content:
        # replace num_floors: 1 with num_floors: 2
        # extract block
        idx = content.find(t1_key)
        end_idx = content.find(f"'{fam}_T2':", idx)
        block = content[idx:end_idx]
        block_new = re.sub(r"'num_floors':\s*1\b", "'num_floors': 2", block)
        block_new = re.sub(r"'has_stairs':\s*False\b", "'has_stairs': True", block_new)
        content = content[:idx] + block_new + content[end_idx:]

    # T2
    t2_key = f"'{fam}_T2':"
    if t2_key in content:
        idx = content.find(t2_key)
        end_idx = content.find(f"'{fam}_T3':", idx)
        block = content[idx:end_idx]
        block_new = re.sub(r"'num_floors':\s*2\b", "'num_floors': 3", block)
        content = content[:idx] + block_new + content[end_idx:]

    # T3
    t3_key = f"'{fam}_T3':"
    if t3_key in content:
        idx = content.find(t3_key)
        # next key
        next_match = re.search(r"\n    '[A-Z0-9_]+': \{", content[idx + len(t3_key):])
        end_idx = idx + len(t3_key) + next_match.start() if next_match else idx + 2000
        block = content[idx:end_idx]
        # ensure at least 3 or 4 floors
        block_new = re.sub(r"'num_floors':\s*2\b", "'num_floors': 3", block)
        content = content[:idx] + block_new + content[end_idx:]

# Military & chapel updates:
# INFANTRY_BARRACKS
def update_floors_for(key, old_fl, new_fl):
    global content
    k = f"'{key}':"
    if k in content:
        idx = content.find(k)
        next_match = re.search(r"\n    '[A-Z0-9_]+': \{", content[idx + len(k):])
        end_idx = idx + len(k) + next_match.start() if next_match else idx + 2000
        block = content[idx:end_idx]
        block_new = re.sub(rf"'num_floors':\s*{old_fl}\b", f"'num_floors': {new_fl}", block)
        block_new = re.sub(r"'has_stairs':\s*False\b", "'has_stairs': True", block_new)
        content = content[:idx] + block_new + content[end_idx:]

update_floors_for('INFANTRY_BARRACKS_T1', 1, 2)
update_floors_for('INFANTRY_BARRACKS_T2', 2, 3)
update_floors_for('INFANTRY_BARRACKS_T3', 2, 3)

update_floors_for('ARCHERY_RANGE_T1', 1, 2)
update_floors_for('ARCHERY_RANGE_T2', 1, 2)
update_floors_for('ARCHERY_RANGE_T3', 2, 3)

update_floors_for('KNIGHTS_MANOR_T1', 1, 2)
update_floors_for('KNIGHTS_MANOR_T2', 2, 3)
update_floors_for('KNIGHTS_MANOR_T3', 2, 3)

update_floors_for('HEALERS_CHAPEL_T1', 1, 2)
update_floors_for('HEALERS_CHAPEL_T2', 2, 3)
update_floors_for('HEALERS_CHAPEL_T3', 2, 3)

# Mage Tower specific sizing
content = re.sub(r"('MAGE_TOWER_T1':[\s\S]*?'width':\s*)8\.4", r"\g<1>10.5", content)
content = re.sub(r"('MAGE_TOWER_T1':[\s\S]*?'depth':\s*)8\.4", r"\g<1>10.5", content)
content = re.sub(r"('MAGE_TOWER_T1':[\s\S]*?'floor_height':\s*)4\.8", r"\g<1>5.4", content)
content = re.sub(r"('MAGE_TOWER_T1':[\s\S]*?'stair_width':\s*)1\.[0-9]+", r"\g<1>1.85", content)

content = re.sub(r"('MAGE_TOWER_T2':[\s\S]*?'width':\s*)9\.4", r"\g<1>12.5", content)
content = re.sub(r"('MAGE_TOWER_T2':[\s\S]*?'depth':\s*)9\.4", r"\g<1>12.5", content)
content = re.sub(r"('MAGE_TOWER_T2':[\s\S]*?'floor_height':\s*)5\.4", r"\g<1>5.8", content)
content = re.sub(r"('MAGE_TOWER_T2':[\s\S]*?'stair_width':\s*)1\.[0-9]+", r"\g<1>1.85", content)

content = re.sub(r"('MAGE_TOWER_T3':[\s\S]*?'width':\s*)11\.0", r"\g<1>15.0", content)
content = re.sub(r"('MAGE_TOWER_T3':[\s\S]*?'depth':\s*)11\.0", r"\g<1>15.0", content)
content = re.sub(r"('MAGE_TOWER_T3':[\s\S]*?'floor_height':\s*)5\.6", r"\g<1>6.0", content)
content = re.sub(r"('MAGE_TOWER_T3':[\s\S]*?'stair_width':\s*)1\.[0-9]+", r"\g<1>1.85", content)

# 4. Add Tenement Presets
tenement_presets_text = """    # =========================================================================
    # RESIDENTIAL: TENEMENT ROW (Medium Plot: 12m x 20m / 20m x 20m)
    # Wall-to-wall plot filling street row with separate apartments (kitchen + bed each)
    # =========================================================================
    'TENEMENT_ROW_MEDIUM_T1': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_ROW_MEDIUM',
        'tier': 1,
        'name': "Tenement Row (Tier 1)",
        'plot': "12m x 20m",
        'description': "Two-storey timber tenement filling a 12m street plot wall-to-wall: twin entrance doorways, ground floor and upper apartments each split into an independent kitchen and bedroom.",
        'settings': {
            **base_settings(),
            'building_shape': 'RECTANGLE',
            'material_tier': 'TIER_1',
            'num_floors': 2, 'floor_height': 3.6,
            'width': 11.8, 'depth': 14.5, 'wall_thickness': 0.28,
            'has_cantilever': True, 'overhang_mode': 'SECOND_FLOOR_ONLY',
            'cantilever_overhang': 0.35,
            'has_foundation': True, 'foundation_height': 0.45, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.45, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.45, 'door_height': 2.80,
            'has_windows': True, 'window_spacing': 2.2, 'window_width': 0.95, 'window_height': 1.40,
            'roof_style': 'SWAY', 'roof_height': 3.8, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 2, 'dormer_sides': 'FRONT',
            'has_chimney': True, 'chimney_pos_x': 0.60, 'chimney_pos_y': 0.60,
        },
    },
    'TENEMENT_ROW_MEDIUM_T2': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_ROW_MEDIUM',
        'tier': 2,
        'name': "Tenement Row (Tier 2)",
        'plot': "12m x 20m",
        'description': "Three-storey half-timbered urban tenement row: ground stone masonry, double jettied timber storeys, independent apartment suites with kitchens and bedrooms, multiple chimneys and front dormers.",
        'settings': {
            **base_settings(),
            'building_shape': 'RECTANGLE',
            'material_tier': 'TIER_2',
            'num_floors': 3, 'floor_height': 3.6,
            'width': 11.8, 'depth': 15.5, 'wall_thickness': 0.28,
            'has_cantilever': True, 'overhang_mode': 'ALL_FLOORS',
            'cantilever_overhang': 0.38,
            'has_foundation': True, 'foundation_height': 0.55, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.45, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.50, 'door_height': 2.85,
            'has_windows': True, 'window_spacing': 2.2, 'window_width': 0.95, 'window_height': 1.40,
            'roof_style': 'SWAY', 'roof_height': 4.0, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 3, 'dormer_sides': 'FRONT',
            'has_chimney': True, 'chimney_pos_x': 0.65, 'chimney_pos_y': 0.65,
        },
    },
    'TENEMENT_ROW_MEDIUM_T3': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_ROW_MEDIUM',
        'tier': 3,
        'name': "Tenement Row (Tier 3)",
        'plot': "20m x 20m",
        'description': "Four-storey grand guild-city tenement block: full 20m street frontage, cut stone arcade ground floor, 4 storeys of partitioned apartments with private kitchens and chambers, dormers, and stone chimneys.",
        'settings': {
            **base_settings(),
            'building_shape': 'RECTANGLE',
            'material_tier': 'TIER_3',
            'num_floors': 4, 'floor_height': 3.7,
            'width': 19.6, 'depth': 16.5, 'wall_thickness': 0.32,
            'has_cantilever': True, 'overhang_mode': 'ALL_FLOORS',
            'cantilever_overhang': 0.40,
            'has_foundation': True, 'foundation_height': 0.70, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.50, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.60, 'door_height': 2.90,
            'has_windows': True, 'window_spacing': 2.4, 'window_width': 1.0, 'window_height': 1.45,
            'roof_style': 'SWAY', 'roof_height': 4.4, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 4, 'dormer_sides': 'BOTH',
            'has_chimney': True, 'chimney_pos_x': 0.70, 'chimney_pos_y': 0.70,
        },
    },

    # =========================================================================
    # RESIDENTIAL: TENEMENT COMPLEX (Large Plot: 40m x 40m)
    # Multi-apartment complex filling a large plot with courtyard and multi-entrance wings
    # =========================================================================
    'TENEMENT_COMPLEX_LARGE_T1': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_COMPLEX_LARGE',
        'tier': 1,
        'name': "Tenement Complex (Tier 1)",
        'plot': "40m x 40m",
        'description': "Sprawling two-storey residential court complex: broad central block with twin residential wings, separate apartment portals, kitchens, bedrooms, and central courtyard well.",
        'settings': {
            **base_settings(),
            'building_shape': 'U_SHAPE',
            'wing_placement': 'FRONT',
            'material_tier': 'TIER_1',
            'num_floors': 2, 'wing_floors': 2, 'floor_height': 3.6,
            'width': 32.0, 'depth': 18.0, 'wing_width': 8.5, 'wing_depth': 12.0,
            'courtyard_width': 15.0, 'wall_thickness': 0.30,
            'has_cantilever': True, 'overhang_mode': 'SECOND_FLOOR_ONLY',
            'cantilever_overhang': 0.35,
            'has_foundation': True, 'foundation_height': 0.50, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.45, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.55, 'door_height': 2.85,
            'has_windows': True, 'window_spacing': 2.4, 'window_width': 0.95, 'window_height': 1.40,
            'roof_style': 'SWAY', 'roof_height': 4.2, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 4, 'dormer_sides': 'BOTH',
            'has_chimney': True, 'chimney_pos_x': 0.65, 'chimney_pos_y': 0.65,
            'has_well': True,
        },
    },
    'TENEMENT_COMPLEX_LARGE_T2': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_COMPLEX_LARGE',
        'tier': 2,
        'name': "Tenement Complex (Tier 2)",
        'plot': "40m x 40m",
        'description': "Three-storey courtyard apartment complex: cut stone foundation, half-timbered upper storeys with timber galleries, housing up to six discrete dual-room apartment flats.",
        'settings': {
            **base_settings(),
            'building_shape': 'U_SHAPE',
            'wing_placement': 'FRONT',
            'material_tier': 'TIER_2',
            'num_floors': 3, 'wing_floors': 3, 'floor_height': 3.7,
            'width': 35.0, 'depth': 20.0, 'wing_width': 9.5, 'wing_depth': 14.0,
            'courtyard_width': 16.0, 'wall_thickness': 0.30,
            'has_cantilever': True, 'overhang_mode': 'ALL_FLOORS',
            'cantilever_overhang': 0.40,
            'has_foundation': True, 'foundation_height': 0.65, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.50, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.60, 'door_height': 2.90,
            'has_windows': True, 'window_spacing': 2.4, 'window_width': 1.0, 'window_height': 1.45,
            'roof_style': 'SWAY', 'roof_height': 4.5, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 6, 'dormer_sides': 'BOTH',
            'has_chimney': True, 'chimney_pos_x': 0.70, 'chimney_pos_y': 0.70,
            'has_well': True,
        },
    },
    'TENEMENT_COMPLEX_LARGE_T3': {
        'category': 'RESIDENTIAL',
        'family': 'TENEMENT_COMPLEX_LARGE',
        'tier': 3,
        'name': "Tenement Complex (Tier 3)",
        'plot': "40m x 40m",
        'description': "Grand four-storey palatial urban tenement block: fills the 40m plot with imposing cut stone plinth, ornate half-timbering, clock spire, balconies, well courtyard, and eight luxury dual-room apartment residences.",
        'settings': {
            **base_settings(),
            'building_shape': 'U_SHAPE',
            'wing_placement': 'FRONT',
            'material_tier': 'TIER_3',
            'num_floors': 4, 'wing_floors': 4, 'floor_height': 3.8,
            'width': 38.0, 'depth': 22.0, 'wing_width': 10.5, 'wing_depth': 15.0,
            'courtyard_width': 17.0, 'wall_thickness': 0.34,
            'has_cantilever': True, 'overhang_mode': 'ALL_FLOORS',
            'cantilever_overhang': 0.42,
            'has_foundation': True, 'foundation_height': 0.85, 'ground_floor_stone': True,
            'has_front_steps': True, 'has_stairs': True, 'stair_style': 'STRAIGHT',
            'stair_width': 1.55, 'has_ceiling_beams': True,
            'has_interior_walls': True, 'interior_partition_style': 'AUTO',
            'has_front_door': True, 'door_width': 1.70, 'door_height': 2.95,
            'has_windows': True, 'window_spacing': 2.4, 'window_width': 1.05, 'window_height': 1.50,
            'roof_style': 'SWAY', 'roof_height': 4.8, 'has_roof_shingles': True,
            'has_dormers': True, 'dormer_count': 6, 'dormer_sides': 'BOTH',
            'has_chimney': True, 'chimney_pos_x': 0.75, 'chimney_pos_y': 0.75,
            'has_balcony': True, 'balcony_side': 'FRONT', 'balcony_floor': 2,
            'has_well': True, 'has_roof_clock_spire': True,
        },
    },
"""

# Insert tenement presets before PRESET_FAMILIES
idx_pf = content.find("PRESET_FAMILIES = [")
if idx_pf != -1:
    content = content[:idx_pf] + tenement_presets_text + "\n" + content[idx_pf:]
    print("Inserted Tenement Presets into PRESETS successfully.")

# 5. Add Tenement families to PRESET_FAMILIES
tenement_families_text = """    {
        'id': 'TENEMENT_ROW_MEDIUM',
        'name': "Tenement Row",
        'category': 'RESIDENTIAL',
        'plot': "12m - 20m",
        'shape': "Wall-to-Wall Row",
        'icon': 'ALIGN_JUSTIFY',
        'tiers': [
            ('T1', 'TENEMENT_ROW_MEDIUM_T1', "Tier 1: 2-Storey Timber Tenement Row"),
            ('T2', 'TENEMENT_ROW_MEDIUM_T2', "Tier 2: 3-Storey Half-Timbered Tenement"),
            ('T3', 'TENEMENT_ROW_MEDIUM_T3', "Tier 3: 4-Storey Urban Tenement Block"),
        ]
    },
    {
        'id': 'TENEMENT_COMPLEX_LARGE',
        'name': "Tenement Complex",
        'category': 'RESIDENTIAL',
        'plot': "40m x 40m",
        'shape': "Courtyard Tenement Complex",
        'icon': 'COMMUNITY',
        'tiers': [
            ('T1', 'TENEMENT_COMPLEX_LARGE_T1', "Tier 1: 2-Storey Courtyard Complex"),
            ('T2', 'TENEMENT_COMPLEX_LARGE_T2', "Tier 2: 3-Storey Apartment Court"),
            ('T3', 'TENEMENT_COMPLEX_LARGE_T3', "Tier 3: 4-Storey Palatial Tenement Block"),
        ]
    },
"""

idx_scaffold = content.find("{'id': 'SCAFFOLD'")
if idx_scaffold == -1:
    idx_scaffold = content.find("'id': 'SCAFFOLD'")
if idx_scaffold != -1:
    # find line start
    line_start = content.rfind("\n    {", 0, idx_scaffold)
    if line_start != -1:
        content = content[:line_start + 1] + tenement_families_text + content[line_start + 1:]
        print("Inserted Tenement families into PRESET_FAMILIES successfully.")

# 6. Add to ARCHETYPE_MAP
tenement_archetypes = """    'TENEMENT_ROW_MEDIUM_T1': 'TENEMENT',
    'TENEMENT_ROW_MEDIUM_T2': 'TENEMENT',
    'TENEMENT_ROW_MEDIUM_T3': 'TENEMENT',
    'TENEMENT_COMPLEX_LARGE_T1': 'TENEMENT',
    'TENEMENT_COMPLEX_LARGE_T2': 'TENEMENT',
    'TENEMENT_COMPLEX_LARGE_T3': 'TENEMENT',
"""
idx_arch = content.find("ARCHETYPE_MAP = {")
if idx_arch != -1:
    content = content[:idx_arch + 17] + "\n" + tenement_archetypes + content[idx_arch + 17:]
    print("Inserted Tenement archetypes into ARCHETYPE_MAP successfully.")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Presets update complete!")
