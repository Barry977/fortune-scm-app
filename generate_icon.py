#!/usr/bin/env python3
"""生成命运 (DESTINY) 应用图标"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size=1024):
    """创建应用图标"""
    # 创建透明背景
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 背景 - 白色圆角矩形
    margin = int(size * 0.05)
    radius = int(size * 0.15)
    
    # 绘制白色背景
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(255, 255, 255, 255)
    )
    
    # 绘制飞机线条 - 抽象飞机 (方案二)
    cx, cy = size // 2, size // 2 - int(size * 0.05)
    scale = size / 1024
    
    # 飞机主体 - 向上的箭头
    plane_color = (26, 26, 26)  # #1a1a1a
    
    # 主线条 - V 形飞机
    line_width = int(8 * scale)
    
    # 左翼
    draw.line(
        [(cx - int(200*scale), cy + int(100*scale)), (cx, cy - int(200*scale))],
        fill=plane_color, width=line_width
    )
    
    # 右翼
    draw.line(
        [(cx + int(200*scale), cy + int(100*scale)), (cx, cy - int(200*scale))],
        fill=plane_color, width=line_width
    )
    
    # 内部线条 - 左
    draw.line(
        [(cx - int(120*scale), cy + int(60*scale)), (cx, cy - int(140*scale))],
        fill=plane_color, width=int(5 * scale)
    )
    
    # 内部线条 - 右
    draw.line(
        [(cx + int(120*scale), cy + int(60*scale)), (cx, cy - int(140*scale))],
        fill=plane_color, width=int(5 * scale)
    )
    
    # 曙光黄圆点
    yellow = (251, 191, 36)  # #fbbf24
    dot_radius = int(30 * scale)
    dot_y = cy + int(150 * scale)
    draw.ellipse(
        [cx - dot_radius, dot_y - dot_radius, cx + dot_radius, dot_y + dot_radius],
        fill=yellow
    )
    
    # 曙光黄光晕
    glow_radius = int(80 * scale)
    for i in range(3):
        r = glow_radius + i * int(20 * scale)
        alpha = 40 - i * 10
        glow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse(
            [cx - r, dot_y - r, cx + r, dot_y + r],
            fill=(251, 191, 36, alpha)
        )
        img = Image.alpha_composite(img, glow)
    
    # 曙光黄底部箭头
    arrow_y = dot_y + int(40 * scale)
    draw.line(
        [(cx - int(60*scale), arrow_y), (cx, dot_y), (cx + int(60*scale), arrow_y)],
        fill=yellow, width=int(6 * scale)
    )
    
    return img

def save_ico(img, path):
    """保存为 .ico 格式"""
    sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    for s in sizes:
        icons.append(img.resize((s, s), Image.Resampling.LANCZOS))
    icons[0].save(path, format='ICO', sizes=[(s, s) for s in sizes], append_images=icons[1:])

def save_icns(img, path):
    """保存为 .icns 格式 (macOS)"""
    # macOS icns 需要 1024x1024
    img.save(path, format='ICNS')

def main():
    print("生成命运 (DESTINY) 应用图标...")
    
    # 创建 1024x1024 图标
    icon = create_icon(1024)
    
    # 保存目录
    assets_dir = "/Users/mima1111/projects/fortune-scm-app/frontend/assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    # 保存 PNG
    png_path = os.path.join(assets_dir, "icon.png")
    icon.save(png_path, format='PNG')
    print(f"  ✅ PNG: {png_path}")
    
    # 保存 ICO (Windows)
    ico_path = os.path.join(assets_dir, "icon.ico")
    save_ico(icon, ico_path)
    print(f"  ✅ ICO: {ico_path}")
    
    # 保存 ICNS (macOS)
    icns_path = os.path.join(assets_dir, "icon.icns")
    save_icns(icon, icns_path)
    print(f"  ✅ ICNS: {icns_path}")
    
    # 保存各尺寸
    for size in [16, 32, 64, 128, 256, 512]:
        resized = icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(assets_dir, f"icon_{size}x{size}.png"))
    
    print(f"\n图标生成完成！")

if __name__ == "__main__":
    main()
