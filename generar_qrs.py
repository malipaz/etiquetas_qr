import pandas as pd
import requests
import re
import os
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import glob 

def create_catalog_pdf_with_blanks(jpg_dir, output_pdf):
    """Genera un PDF con imágenes 6x6cm en layout 3x4, espacios en blanco si faltan"""
    images_per_page = 12
    cols = 3
    rows = 4
    img_size_cm = 6
    img_size_pt = img_size_cm * cm  
    
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    page_width, page_height = A4
    
    margin_x = (page_width - (cols * img_size_pt)) / 2
    margin_y = (page_height - (rows * img_size_pt)) / 2
    
    jpg_files = sorted(glob.glob(os.path.join(jpg_dir, '*.jpg')))
    
    total_images = len(jpg_files)
    pages = (total_images + images_per_page - 1) // images_per_page
    
    print(f"📁 {total_images} imágenes encontradas → {pages} páginas PDF")
    
    for page_num in range(pages):
        start_index = page_num * images_per_page
        end_index = start_index + images_per_page
        page_imgs = jpg_files[start_index:end_index]
        
        for i in range(images_per_page):
            col = i % cols
            row = i // cols
            x = margin_x + col * img_size_pt
            y = page_height - margin_y - (row + 1) * img_size_pt
            
            if i < len(page_imgs):
                pdf.drawImage(page_imgs[i], x, y, width=img_size_pt, height=img_size_pt)
        
        pdf.showPage()
    
    pdf.save()
    print(f"✅ PDF catálogo creado: {output_pdf}")

def parse_qr_svg(svg_content):
    """Extrae píxeles negros del SVG QR"""
    pixels = []
    svg_match = re.findall(r' x="(\d+)" y="(\d+)" xlink:href="#r0"', svg_content)
    for x, y in svg_match:
        pixels.append((int(x)//8, int(y)//8))
    return pixels

# ===== INICIO PROCESO =====
excel_file = 'datos_celmedia.xlsx'
df = pd.read_excel(excel_file)

jpg_dir = 'jpgs_6x6cm'
os.makedirs(jpg_dir, exist_ok=True)

IMG_WIDTH = 216
IMG_HEIGHT = 216
CELL_SIZE = 5

# LIMPIAR JPGs anteriores
for old_jpg in glob.glob(os.path.join(jpg_dir, "*.jpg")):
    os.remove(old_jpg)
print("🗑️ Carpeta jpgs_6x6cm limpiada")

for index, row in df.iterrows():
    link = row['link']
    product_name = str(row['nombre_producto']).strip()
    
    try:
        print(f"🔄 Procesando [{index+1}/{len(df)}]: {product_name}")
        
        response = requests.get(link, timeout=15)
        response.raise_for_status()
        html_content = response.text
        
        itau_match = re.search(r'<tr>\s*<td[^>]*>([^<]+?)</td>', html_content)
        itau_code = itau_match.group(1).strip() if itau_match else "ITAU-CODIGO"
        
        svg_match = re.search(r'<svg[^>]*>.*?</svg>', html_content, re.DOTALL)
        svg_content = svg_match.group(0) if svg_match else ""
        
        # NOMBRE ARCHIVO ÚNICO
        safe_name = re.sub(r'[^\w\s-]', '_', product_name).strip().replace(' ', '_')[:40]
        unique_name = f"{safe_name}_{index+1:03d}.jpg"
        jpg_path = os.path.join(jpg_dir, unique_name)
        
        img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), 'white')
        draw = ImageDraw.Draw(img)
        
        # 1. CÓDIGO ITAU (ARRIBA)
        try:
            font_itau = ImageFont.truetype("arial.ttf", 14)
        except:
            font_itau = ImageFont.load_default()
        draw.text((10, 20), itau_code, fill='black', font=font_itau)
        
        # 2. QR/SVG (CENTRO)
        if svg_content:
            pixels = parse_qr_svg(svg_content)
            qr_start_x = 30
            qr_start_y = 30
            for px, py in pixels:
                x = qr_start_x + px * CELL_SIZE
                y = qr_start_y + py * CELL_SIZE
                draw.rectangle([x, y, x+CELL_SIZE, y+CELL_SIZE], fill='black')
        
        # ✅ 3. NOMBRE PRODUCTO (ABAJO) - NUEVA LÓGICA 2 LÍNEAS
        try:
            font_prod = ImageFont.truetype("arial.ttf", 12)
        except:
            font_prod = ImageFont.load_default()
        
        if len(product_name) > 30:
            # ✅ PRIMERA LÍNEA: EXACTAMENTE 30 caracteres
            line1 = product_name[:30].rstrip()  # Primeros 30 chars
            line2 = product_name[30:].lstrip()  # TODO lo que SOBRA
            
            # Calcular posición centrada para cada línea
            bbox1 = draw.textbbox((0, 0), line1, font=font_prod)
            bbox2 = draw.textbbox((0, 0), line2, font=font_prod)
            text_width1 = bbox1[2] - bbox1[0]
            text_width2 = bbox2[2] - bbox2[0]
            
            center_x1 = (IMG_WIDTH - text_width1) / 2
            center_x2 = (IMG_WIDTH - text_width2) / 2
            
            draw.text((center_x1, 175), line1, fill='black', font=font_prod)
            draw.text((center_x2, 190), line2, fill='black', font=font_prod)
            
        else:
            # 1 línea centrada
            bbox = draw.textbbox((0, 0), product_name, font=font_prod)
            center_x = (IMG_WIDTH - (bbox[2] - bbox[0])) / 2
            draw.text((center_x, 178), product_name, fill='black', font=font_prod)
        
        img.save(jpg_path, 'JPEG', quality=95, dpi=(72,72))
        
        
    except Exception as e:
        print(f"❌ Error en {product_name}: {e}")


create_catalog_pdf_with_blanks(jpg_dir, 'catalogo_3x4.pdf')
print("✅✅✅ PROCESO COMPLETADO ✅✅✅")











