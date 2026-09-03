# -*- coding: utf-8 -*-
"""Génère app_icon.png (256x256) — charte darkroom ambre."""
import os

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# fond carte sombre arrondi
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill=(30, 26, 22, 255))
# cadre de frame ambre
d.rounded_rectangle([52, 64, S - 52, S - 64], radius=20,
                    outline=(224, 151, 90, 255), width=14)
# point central ambre
d.ellipse([S // 2 - 22, S // 2 - 22, S // 2 + 22, S // 2 + 22],
          fill=(224, 151, 90, 255))
img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.png"))
print("app_icon.png généré.")