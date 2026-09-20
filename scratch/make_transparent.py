import os
from PIL import Image

def process_icon(input_path, output_path):
    img = Image.open(input_path).convert('RGBA')
    # If the user wants black lines with transparency:
    # Convert white background to transparent.
    # For anti-aliased black lines on white:
    # Gray value determines opacity of black.
    # e.g. R=G=B=255 -> Alpha=0
    #      R=G=B=0   -> Alpha=255, Color=(0,0,0)
    #      R=G=B=128 -> Alpha=127, Color=(0,0,0)
    
    r, g, b, a = img.split()
    gray = img.convert('L')
    
    # Invert grayscale for alpha (white=0, black=255)
    # With a small threshold curve for clean cutoffs
    alpha = gray.point(lambda p: 0 if p > 240 else (255 if p < 40 else int((255 - p) * (255 / 200))))
    
    # Pure black image with calculated alpha
    black_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
    black_img.putalpha(alpha)
    
    black_img.save(output_path, 'PNG')
    print(f"Saved {output_path}")

if __name__ == '__main__':
    brain_dir = r'C:\Users\Sebastian\.gemini\antigravity-ide\brain\d65db0a1-27f4-4c8f-91af-1558fa71f637'
    out_dir = r'd:\BlendBuildingCreator\blend_building_creator\textures'
    
    mapping = {
        'bakery_icon_1789841239565.jpg': 'bakery_sign.png',
        'tailor_icon_1789841272214.jpg': 'tailor_sign.png',
        'toolsmith_icon_1789841285259.jpg': 'toolsmith_sign.png',
        'jeweler_icon_1789841298055.jpg': 'jeweler_sign.png',
        'brewery_icon_1789841311413.jpg': 'brewery_sign.png',
        'fisher_icon_1789841325748.jpg': 'fisher_sign.png',
        'furniture_icon_1789841339618.jpg': 'furniture_maker_sign.png',
        'butcher_icon_1789914127527.jpg': 'butcher_sign.png',
        'weaponsmith_icon_1789914145870.jpg': 'weaponsmith_sign.png',
        'armorsmith_icon_1789914165761.jpg': 'armorsmith_sign.png',
        'weaver_icon_1789914183207.jpg': 'weaver_sign.png',
        'tannery_icon_1789914196882.jpg': 'tannery_sign.png',
        'mill_icon_1789914216021.jpg': 'mill_sign.png',
        'market_icon_1789914232940.jpg': 'market_sign.png',
        'general_store_icon_1789914248933.jpg': 'general_store_sign.png',
    }
    
    for src_name, dst_name in mapping.items():
        src_path = os.path.join(brain_dir, src_name)
        dst_path = os.path.join(out_dir, dst_name)
        if os.path.exists(src_path):
            process_icon(src_path, dst_path)
        else:
            print(f"Missing {src_path}")
