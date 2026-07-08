import base64
import json
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

def descargar_miniatura_competidor(video_id, ruta_salida):
    """
    Descarga la miniatura de YouTube de mayor calidad disponible para un video ID.
    """
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    ]
    for url in urls:
        try:
            res = requests.get(url, stream=True, timeout=10)
            if res.status_code == 200:
                with open(ruta_salida, "wb") as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Miniatura del competidor descargada de: {url}")
                return True
        except Exception as e:
            print(f"⚠️ Falló descarga desde {url}: {e}")
    return False

def analizar_miniatura_con_gemini(ruta_imagen, api_key):
    """
    Analiza una imagen de miniatura usando Gemini Vision y devuelve
    las directrices de diseño estructuradas en JSON.
    """
    try:
        with open(ruta_imagen, "rb") as image_file:
            img_data = base64.b64encode(image_file.read()).decode("utf-8")
            
        prompt = (
            "Analiza esta miniatura de YouTube y extrae su estructura de diseño visual en formato JSON. "
            "Necesito saber exactamente cómo se distribuyen los elementos para poder imitarla.\n\n"
            "ESTRUCTURA DEL JSON REQUERIDA:\n"
            "{\n"
            "  \"texto_posicion_x\": \"left\" o \"right\" o \"center\", \n"
            "  \"texto_alineacion\": \"left\" o \"right\" o \"center\", \n"
            "  \"color_primario\": \"yellow\" o \"red\" o \"white\" o \"green\", \n"
            "  \"color_secundario\": \"white\" o \"yellow\" o \"green\", \n"
            "  \"inclinacion_grados\": un número entero entre -10 y 10 (grados de rotación del texto), \n"
            "  \"sujeto_posicion_x\": \"left\" o \"right\" o \"center\", \n"
            "  \"tiene_banner\": true o false (¿el texto tiene un fondo o rectangulo solido detras?)\n"
            "}"
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": img_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        res = requests.post(url, json=payload, timeout=30).json()
        if 'candidates' in res and len(res['candidates']) > 0:
            res_text = res['candidates'][0]['content']['parts'][0]['text']
            return json.loads(res_text)
    except Exception as e:
        print(f"⚠️ Error al analizar miniatura con Gemini: {e}")
    return None

def aplicar_estilo_miniatura(ruta_fondo, ruta_salida, texto_clickbait, color_texto="yellow"):
    # Wrapper compatible con la API anterior que redirige al render avanzado
    aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_salida, texto_clickbait)

def aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_salida, texto_clickbait, layout_config=None):
    """
    Toma una imagen de fondo, le añade texto clickbait imitando diseños de alta conversión.
    Soporta banners, rotaciones, alineación dinámica y espejo de la imagen de fondo.
    """
    print(f"🎨 Componiendo miniatura clickbait avanzada...")
    
    # 1. Cargar fondo y asegurar resolución 1280x720
    if not os.path.exists(ruta_fondo):
        print(f"⚠️ Fondo {ruta_fondo} no encontrado. Creando un fondo oscuro...")
        img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
    else:
        img = Image.open(ruta_fondo).convert("RGB")
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        
    # Configuración de diseño por defecto si no viene del análisis de Gemini
    if not layout_config:
        layout_config = {
            "texto_posicion_x": "right",
            "texto_alineacion": "right",
            "color_primario": "yellow",
            "color_secundario": "white",
            "inclinacion_grados": -3,
            "sujeto_posicion_x": "left",
            "tiene_banner": False
        }
        
    # 2. Si el sujeto debe ir a la derecha y el texto a la izquierda, podemos hacer un espejo horizontal
    # del fondo para evitar que el texto tape la imagen principal generada.
    if layout_config.get("sujeto_posicion_x") == "right" and layout_config.get("texto_posicion_x") == "left":
        img = ImageOps.mirror(img)
        print("🔄 Volteando fondo horizontalmente para optimizar espacio del texto.")
        
    # 3. Dibujar degradado negro de contraste según la posición del texto
    overlay_degradado = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay_degradado)
    pos_x = layout_config.get("texto_posicion_x", "right")
    
    if pos_x == "right":
        for px in range(600, 1280):
            alpha = int(((px - 600) / 680) * 190)
            overlay_draw.line([(px, 0), (px, 720)], fill=(0, 0, 0, alpha))
    elif pos_x == "left":
        for px in range(0, 680):
            alpha = int(((680 - px) / 680) * 190)
            overlay_draw.line([(px, 0), (px, 720)], fill=(0, 0, 0, alpha))
    else: # Center / full screen vignette
        for py in range(720):
            for px in range(1280):
                # Distancia al centro para viñeta circular
                dist = ((px-640)**2 + (py-360)**2)**0.5
                alpha = min(int((dist / 730) * 160), 160)
                if alpha > 20:
                    overlay_degradado.putpixel((px, py), (0, 0, 0, alpha))
                    
    img = Image.alpha_composite(img.convert("RGBA"), overlay_degradado).convert("RGB")
    
    # 4. Configurar fuentes
    rutas_fuentes = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
    ]
    fuente_path = None
    for path in rutas_fuentes:
        if os.path.exists(path):
            fuente_path = path
            break
            
    font_size = 90
    if len(texto_clickbait) > 22:
        font_size = 75
        
    if fuente_path:
        font = ImageFont.truetype(fuente_path, font_size)
    else:
        font = ImageFont.load_default()
        
    # 5. Wrapping inteligente
    max_width = 520
    palabras = texto_clickbait.upper().split()
    lineas = []
    linea_actual = []
    test_draw = ImageDraw.Draw(img)
    
    for palabra in palabras:
        linea_actual.append(palabra)
        test_linea = " ".join(linea_actual)
        if test_draw.textlength(test_linea, font=font) <= max_width:
            pass
        else:
            if len(linea_actual) > 1:
                linea_actual.pop()
                lineas.append(" ".join(linea_actual))
                linea_actual = [palabra]
            else:
                lineas.append(palabra)
                linea_actual = []
    if linea_actual:
        lineas.append(" ".join(linea_actual))
        
    # 6. Crear un lienzo transparente separado para dibujar el texto con rotación/banner
    texto_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(texto_layer)
    
    # Coordenadas X iniciales según posición
    if pos_x == "right":
        txt_x = 730
    elif pos_x == "left":
        txt_x = 80
    else:
        txt_x = 380 # Centro aproximado
        
    line_height = font_size + 15
    total_height = len(lineas) * line_height
    txt_y_start = (720 - total_height) // 2
    
    color_map = {
        "yellow": (255, 235, 59, 255),
        "red": (244, 67, 54, 255),
        "white": (255, 255, 255, 255),
        "green": (76, 175, 80, 255)
    }
    
    c_primario = layout_config.get("color_primario", "yellow").lower()
    c_secundario = layout_config.get("color_secundario", "white").lower()
    col_p = color_map.get(c_primario, (255, 235, 59, 255))
    col_s = color_map.get(c_secundario, (255, 255, 255, 255))
    
    for i, linea in enumerate(lineas):
        txt_y = txt_y_start + (i * line_height)
        col_actual = col_p if i % 2 == 0 else col_s
        
        # Calcular el tamaño exacto de esta línea de texto
        bbox = t_draw.textbbox((txt_x, txt_y), linea, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        
        # Dibujar banner detrás de la línea
        if layout_config.get("tiene_banner"):
            # Rectángulo con un leve padding
            padding_w = 25
            padding_h = 10
            t_draw.rectangle(
                [txt_x - padding_w, txt_y - padding_h, txt_x + lw + padding_w, txt_y + lh + padding_h * 2],
                fill=(180, 0, 0, 230) if i % 2 == 0 else (0, 0, 0, 230)
            )
            
        # Dibujar contorno del texto (outline)
        grosor = 8
        for dx in range(-grosor, grosor + 1):
            for dy in range(-grosor, grosor + 1):
                if dx*dx + dy*dy <= grosor*grosor:
                    t_draw.text((txt_x + dx, txt_y + dy), linea, font=font, fill=(0, 0, 0, 255))
                    
        # Dibujar texto principal
        t_draw.text((txt_x, txt_y), linea, font=font, fill=col_actual)
        
    # 7. Aplicar rotación/inclinación al lienzo de texto si es requerido
    grados = layout_config.get("inclinacion_grados", 0)
    if grados != 0:
        # Rotar la capa transparente del texto usando interpolación bicúbica
        texto_layer = texto_layer.rotate(grados, resample=Image.Resampling.BICUBIC, center=(640, 360))
        
    # 8. Fusionar la capa de texto rotada sobre el fondo principal
    img_final = Image.alpha_composite(img.convert("RGBA"), texto_layer).convert("RGB")
    
    # 9. Guardar la imagen compuesta
    dir_salida = os.path.dirname(ruta_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    img_final.save(ruta_salida, "PNG")
    print(f"✅ Miniatura clickbait terminada y guardada en: {ruta_salida}")

if __name__ == "__main__":
    aplicar_estilo_miniatura_avanzado("fondo_prueba.png", "miniatura_prueba.png", "AJO EN AYUNAS: ¡EXPLOTA TU SALUD!")
