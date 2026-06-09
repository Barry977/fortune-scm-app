#!/usr/bin/env python3
"""生成 macOS DMG 安装界面背景"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_dmg_background(width=660, height=400):
    """创建 DMG 安装背景"""
    # 创建渐变背景
    img = Image.new('RGB', (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    
    # 绘制渐变背景
    for y in range(height):
        r = int(245 - (y / height) * 10)
        g = int(245 - (y / height) * 10)
        b = int(245 - (y / height) * 10)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 绘制品牌标识
    # 飞机图标
    cx, cy = width // 2, 80
    
    # 飞机线条
    plane_color = (26, 26, 26)
    line_width = 3
    
    # 左翼
    draw.line([(cx - 30, cy + 15), (cx, cy - 25)], fill=plane_color, width=line_width)
    # 右翼
    draw.line([(cx + 30, cy + 15), (cx, cy - 25)], fill=plane_color, width=line_width)
    # 内左
    draw.line([(cx - 18, cy + 8), (cx, cy - 18)], fill=plane_color, width=2)
    # 内右
    draw.line([(cx + 18, cy + 8), (cx, cy - 18)], fill=plane_color, width=2)
    
    # 黄色圆点
    yellow = (251, 191, 36)
    draw.ellipse([cx - 5, cy + 20, cx + 5, cy + 30], fill=yellow)
    # 黄色箭头
    draw.line([(cx - 8, cy + 35), (cx, cy + 25), (cx + 8, cy + 35)], fill=yellow, width=2)
    
    # 品牌文字
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 12)
        font_en = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_en = ImageFont.load_default()
    
    # 命运
    draw.text((cx - 20, cy + 45), "命运", fill=plane_color, font=font_large)
    # DESTINY
    draw.text((cx - 30, cy + 75), "DESTINY", fill=(102, 102, 102), font=font_en)
    
    # 安装提示
    draw.text((width // 2 - 80, height - 60), "拖动图标到 Applications 文件夹安装", fill=(153, 153, 153), font=font_small)
    
    # Applications 文件夹图标位置
    app_x = width - 150
    app_y = height // 2 - 20
    
    # 绘制 Applications 文件夹图标
    folder_color = (100, 150, 255)
    draw.rounded_rectangle(
        [app_x, app_y, app_x + 80, app_y + 60],
        radius=5,
        fill=folder_color,
        outline=(80, 130, 235)
    )
    draw.rectangle([app_x + 10, app_y - 10, app_x + 40, app_y + 5], fill=folder_color)
    
    # 应用图标位置 (左侧)
    icon_x = 100
    icon_y = height // 2 - 20
    
    # 绘制应用图标占位符
    draw.rounded_rectangle(
        [icon_x, icon_y, icon_x + 80, icon_y + 80],
        radius=15,
        fill=(255, 255, 255),
        outline=(200, 200, 200)
    )
    
    # 箭头指示
    arrow_y = height // 2
    for i in range(3):
        x = 200 + i * 20
        draw.line([(x, arrow_y), (x + 15, arrow_y)], fill=(180, 180, 180), width=2)
        draw.line([(x + 12, arrow_y - 3), (x + 15, arrow_y), (x + 12, arrow_y + 3)], fill=(180, 180, 180), width=2)
    
    return img

def main():
    print("生成 macOS DMG 安装背景...")
    
    bg = create_dmg_background()
    
    # 保存
    assets_dir = "/Users/mima1111/projects/fortune-scm-app/frontend/assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    bg_path = os.path.join(assets_dir, "dmg_background.png")
    bg.save(bg_path, format='PNG')
    print(f"  ✅ 背景图: {bg_path}")
    
    print("\nDMG 背景生成完成！")

if __name__ == "__main__":
    main()
