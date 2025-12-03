from io import BytesIO
import pandas as pd
import requests
import re
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import tempfile
import glob 
import os
from flask import Flask, Response


def parse_qr_svg(svg_content):
    pixels = []
    svg_match = re.findall(r' x="(\d+)" y="(\d+)" xlink:href="#r0"', svg_content)
    for x, y in svg_match:
        pixels.append((int(x)//8, int(y)//8))
    return pixels


def handler(request):
    """ recibe el excel, genera el PDF y lo devuelve """
    file = request.files.get("file")
    if file is None:
        return Response("No se envió archivo", status=400)

    df = pd.read_excel(file)

    TMP = tempfile.mkdtemp()
    jpg_dir = os.path.join(TMP, "jpgs")
    os.makedirs(jpg_dir, exist_ok=True)

    IMG_WIDTH = 216
    IMG_HEIGHT = 216
    CELL_SIZE = 5

    # generar JPGs
    for index, row in df.iterrows():
        link = row["link"]
        product_name = str(row["nombre_producto"])

        response = requests.get(link)
        html = response.text

        itau_match = re.search(r'<tr>\s*<td[^>]*>([^<]+?)</td>', html)
        itau_code = itau_match.group(1).strip() if itau_match else "ITAU"

        svg_match = re.search(r'<svg.*?</svg>', html, re.DOTALL)
        svg_content = svg_match.group(0) if svg_match else ""

        img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), "white")
        draw = ImageDraw.Draw(img)

        draw.text((10, 20), itau_code, fill="black")

        if svg_content:
            pixels = parse_qr_svg(svg_content)
            qr_start_x = 30
            qr_start_y = 30
            for px, py in pixels:
                x = qr_start_x + px * CELL_SIZE
                y = qr_start_y + py * CELL_SIZE
                draw.rectangle([x, y, x+CELL_SIZE, y+CELL_SIZE], fill="black")

        draw.text((10, 180), product_name, fill="black")

        img.save(os.path.join(jpg_dir, f"{index}.jpg"), "JPEG", quality=95)

    # crear PDF en memoria
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    img_size_pt = 6 * cm
    cols, rows = 3, 4

    margin_x = (page_width - cols * img_size_pt) / 2
    margin_y = (page_height - rows * img_size_pt) / 2

    images = sorted(glob.glob(os.path.join(jpg_dir, "*.jpg")))

    i = 0
    while i < len(images):
        for row in range(4):
            for col in range(3):
                if i >= len(images):
                    break
                x = margin_x + col * img_size_pt
                y = page_height - margin_y - (row+1) * img_size_pt
                pdf.drawImage(images[i], x, y,
                              width=img_size_pt, height=img_size_pt)
                i += 1
        pdf.showPage()

    pdf.save()
    buffer.seek(0)

    return Response(buffer, mimetype="application/pdf")
