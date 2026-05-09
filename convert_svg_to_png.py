import sys
from pathlib import Path

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtWidgets import QApplication


# =========================
# CONFIG
# =========================

INPUT_FOLDER = r"C:\Users\norma\Desktop\Cineblast VFE\icons"
OUTPUT_FOLDER = r"C:\Users\norma\Desktop\Cineblast VFE\icons_png"

SIZE = 88  # 88x88 px


# =========================
# APP QT
# =========================

app = QApplication(sys.argv)

input_path = Path(INPUT_FOLDER)
output_path = Path(OUTPUT_FOLDER)

output_path.mkdir(parents=True, exist_ok=True)

svg_files = list(input_path.glob("*.svg"))

if not svg_files:
    print("Aucun fichier SVG trouvé.")
    sys.exit()

print(f"{len(svg_files)} fichiers trouvés.\n")

for svg_file in svg_files:

    png_file = output_path / f"{svg_file.stem}.png"

    renderer = QSvgRenderer(str(svg_file))

    if not renderer.isValid():
        print(f"[ERREUR] SVG invalide : {svg_file.name}")
        continue

    # Image transparente
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)

    # rendu haute qualité
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    renderer.render(
        painter,
        QRectF(0, 0, SIZE, SIZE)
    )

    painter.end()

    success = image.save(str(png_file), "PNG")

    if success:
        print(f"[OK] {svg_file.name} -> {png_file.name}")
    else:
        print(f"[ECHEC] {svg_file.name}")

print("\nConversion terminée.")