import math
import random
from PIL import Image

W, H = 512, 512
img = Image.new('RGB', (W, H))
pixels = img.load()

# Tiling parameters
threads_u = 32
threads_v = 32
step_x = W / float(threads_u)
step_y = H / float(threads_v)

# Seeded random for consistent organic variation
rng = random.Random(42)

# Precompute thread random offsets and tones (periodic in grid)
thread_tones_u = [0.92 + 0.16 * rng.random() for _ in range(threads_u)]
thread_tones_v = [0.90 + 0.18 * rng.random() for _ in range(threads_v)]

# Low frequency noise field for painterly blotches / weathering (tileable)
def smooth_noise(x, y, scale=4):
    val = 0.0
    for ox in [-W, 0, W]:
        for oy in [-H, 0, H]:
            d2 = ((x + ox - W * 0.5)**2 + (y + oy - H * 0.5)**2) / (W * 0.5)**2
            val += math.exp(-d2 * scale)
    return val

for y in range(H):
    ty = y / step_y
    idx_v = int(ty) % threads_v
    frac_y = ty - int(ty)  # 0.0 to 1.0 within thread
    
    for x in range(W):
        tx = x / step_x
        idx_u = int(tx) % threads_u
        frac_x = tx - int(tx)
        
        # Warp & Weft thread profile (rounded cylinder slice)
        # Warp is vertical thread, Weft is horizontal thread
        # In a plain weave: one goes over, the other goes under
        cell_phase = (idx_u + idx_v) % 2  # 0: warp on top, 1: weft on top
        
        # Distance to center of respective thread
        dx = abs(frac_x - 0.5) * 2.0  # 0 (center) to 1 (edge)
        dy = abs(frac_y - 0.5) * 2.0
        
        # Organic curve profile
        warp_h = math.sqrt(max(0.0, 1.0 - dx * dx))
        weft_h = math.sqrt(max(0.0, 1.0 - dy * dy))
        
        if cell_phase == 0:
            # Warp on top
            top_h = warp_h * thread_tones_u[idx_u]
            under_h = weft_h * thread_tones_v[idx_v] * 0.55
            # Crevice between threads
            crevice = min(1.0, (1.0 - dx) * 2.2) * (0.5 + 0.5 * warp_h)
            h = max(under_h, top_h * crevice)
            is_warp = True
        else:
            # Weft on top
            top_h = weft_h * thread_tones_v[idx_v]
            under_h = warp_h * thread_tones_u[idx_u] * 0.55
            crevice = min(1.0, (1.0 - dy) * 2.2) * (0.5 + 0.5 * weft_h)
            h = max(under_h, top_h * crevice)
            is_warp = False
            
        # Subtle cross-fiber micro texture
        micro = math.sin(x * 0.6) * math.cos(y * 0.6) * 0.04
        
        # Color gradient: warm rustic unbleached canvas / khaki burlap
        # Deep shadow crevice
        c_shadow = (98, 76, 52)
        # Midtone thread body (rich warm tan)
        c_mid = (182, 154, 118)
        # Specular / sunlit thread crest (warm cream/amber)
        c_crest = (222, 198, 162)
        
        val = max(0.0, min(1.0, h + micro))
        if val < 0.45:
            t = val / 0.45
            r = c_shadow[0] * (1.0 - t) + c_mid[0] * t
            g = c_shadow[1] * (1.0 - t) + c_mid[1] * t
            b = c_shadow[2] * (1.0 - t) + c_mid[2] * t
        else:
            t = (val - 0.45) / 0.55
            r = c_mid[0] * (1.0 - t) + c_crest[0] * t
            g = c_mid[1] * (1.0 - t) + c_crest[1] * t
            b = c_mid[2] * (1.0 - t) + c_crest[2] * t
            
        # Add subtle thread tint difference between warp and weft
        if is_warp:
            r *= 1.02
            g *= 0.99
            b *= 0.96
        else:
            r *= 0.98
            g *= 1.01
            b *= 1.02
            
        # Subtle weather vignette noise (tileable sinusoidal)
        weather = 1.0 + 0.06 * (math.sin(x * 2.0 * math.pi / W * 2) * math.cos(y * 2.0 * math.pi / H * 2))
        r = int(max(0, min(255, r * weather)))
        g = int(max(0, min(255, g * weather)))
        b = int(max(0, min(255, b * weather)))
        
        pixels[x, y] = (r, g, b)

out_path = 'blend_building_creator/textures/tarp_fabric_diffuse.png'
img.save(out_path, 'PNG')
print(f"Saved {out_path} ({W}x{H})")
