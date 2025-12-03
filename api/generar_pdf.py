import io
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import re
import os
import glob
import requests
from http.server import BaseHTTPRequestHandler
import base64

# ------------------------------------------------------------
# Función generadora del PDF
# ------------------------------------------------------------
def generar_pdf_desde_excel(excel_file):
    df = pd.read_excel(excel_file)

    # Carpeta temporal en Vercel
    jpg_dir = "/tmp/jpgs_6x6cm"
    os.makedirs(jpg_dir, exist_ok=True)

    IMG_WIDTH = 216
    IMG_HEIGHT = 216
    CELL_SIZE = 5

    # Limpia JPG antiguos
    for old in glob.glob(os.path.join(jpg_dir, "*.jpg")):
        os.remove(old)

    # --------- Función para convertir SVG QR ---------
    def parse_qr_svg(svg_content):
        pixels = []
        svg_match = re.findall(r' x="(\d+)" y="(\d+)" xlink:href="#r0"', svg_content)
        for x, y in svg_match:
            pixels.append((int(x)//8, int(y)//8))
        return pixels

    # ------------ GENERAR UNA IMAGEN POR FILA ------------
    for index, row in df.iterrows():
        link = row["link"]
        product_name = str(row["nombre_producto"]).strip()

        resp = requests.get(link, timeout=15)
        html = resp.text

        itau_match = re.search(r'<tr>\s*<td[^>]*>([^<]+?)</td>', html)
        itau_code = itau_match.group(1).strip() if itau_match else "ITAU"

        svg_match = re.search(r'<svg[^>]*>.*?</svg>', html, re.DOTALL)
        svg_content = svg_match.group(0) if svg_match else ""

        safe_name = re.sub(r"[^\w\s-]", "_", product_name).replace(" ", "_")[:40]
        filename = f"{safe_name}_{index+1:03d}.jpg"
        jpg_path = os.path.join(jpg_dir, filename)

        img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), "white")
        draw = ImageDraw.Draw(img)

        try:
            font1 = ImageFont.truetype("arial.ttf", 14)
        except:
            font1 = ImageFont.load_default()

        draw.text((10, 20), itau_code, fill="black", font=font1)

        if svg_content:
            pixels = parse_qr_svg(svg_content)
            for px, py in pixels:
                x = 30 + px * CELL_SIZE
                y = 30 + py * CELL_SIZE
                draw.rectangle([x, y, x+CELL_SIZE, y+CELL_SIZE], fill="black")

        try:
            font2 = ImageFont.truetype("arial.ttf", 12)
        except:
            font2 = ImageFont.load_default()

        if len(product_name) > 30:
            line1 = product_name[:30]
            line2 = product_name[30:]
            draw.text((10, 175), line1, fill="black", font=font2)
            draw.text((10, 190), line2, fill="black", font=font2)
        else:
            draw.text((10, 180), product_name, fill="black", font=font2)

        img.save(jpg_path, "JPEG", quality=95, dpi=(72,72))

    # ------------ CREAR PDF EN MEMORIA ------------
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    images_per_page = 12
    cols = 3
    rows = 4
    img_size_cm = 6
    img_size_pt = img_size_cm * cm
    page_width, page_height = A4

    margin_x = (page_width - (cols * img_size_pt)) / 2
    margin_y = (page_height - (rows * img_size_pt)) / 2

    jpg_files = sorted(glob.glob(os.path.join(jpg_dir, "*.jpg")))

    for i, jpg in enumerate(jpg_files):
        if i % images_per_page == 0 and i != 0:
            pdf.showPage()

        col = (i % images_per_page) % cols
        row = (i % images_per_page) // cols

        x = margin_x + col * img_size_pt
        y = page_height - margin_y - (row + 1) * img_size_pt

        pdf.drawImage(jpg, x, y, width=img_size_pt, height=img_size_pt)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


# ------------------------------------------------------------
# Handler PARA VERCEL (obligatorio)
# ------------------------------------------------------------
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Debes enviar multipart/form-data con un archivo Excel")
            return

        boundary = content_type.split("boundary=")[-1].encode()
        body = self.rfile.read(content_length)

        # Extraer el archivo Excel dentro del multipart
        parts = body.split(boundary)
        excel_bytes = None

        for part in parts:
            if b"filename=" in part:
                header, filedata = part.split(b"\r\n\r\n", 1)
                excel_bytes = filedata.rstrip(b"--\r\n")

        if not excel_bytes:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No se recibió archivo")
            return

        # Generar PDF
        pdf_bytes = generar_pdf_desde_excel(io.BytesIO(excel_bytes))

        # Responder el PDF
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", "attachment; filename=etiquetas.pdf")
        self.end_headers()
        self.wfile.write(pdf_bytes)

