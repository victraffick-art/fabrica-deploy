import os
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

def remove_black_background(img_pil, threshold=40):
    """
    Algoritmo Luma-Keying en Python. Convierte el fondo negro o casi negro
    en canal alfa transparente, suavizando los bordes (anti-aliasing).
    """
    rgba = img_pil.convert("RGBA")
    datas = rgba.getdata()
    newData = []
    for item in datas:
        # Calcular luminosidad aproximada
        luma = 0.299 * item[0] + 0.587 * item[1] + 0.114 * item[2]
        if luma < threshold:
            # Transparencia total
            newData.append((0, 0, 0, 0))
        elif luma < threshold + 40:
            # Transición suave
            factor = (luma - threshold) / 40.0
            alpha = int(255 * factor)
            newData.append((item[0], item[1], item[2], alpha))
        else:
            newData.append(item)
    rgba.putdata(newData)
    return rgba

def dibujar_flecha_curva(draw_ctx, p_inicio, p_control, p_fin, color=(220, 0, 0, 255), grosor=20):
    """
    Dibuja una flecha curvada (Curva Bézier cuadrática) en PIL con contorno negro.
    """
    # Contorno negro grueso
    grosor_contorno = grosor + 12
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            if dx*dx + dy*dy <= 49:
                dibujar_arco_bezier(draw_ctx, p_inicio, p_control, p_fin, color=(0, 0, 0, 255), grosor=grosor_contorno)
                
    # Flecha roja interna
    dibujar_arco_bezier(draw_ctx, p_inicio, p_control, p_fin, color=color, grosor=grosor)
    
    # Dibujar la punta de la flecha
    # Calcular ángulo al final de la curva
    import math
    dx = p_fin[0] - p_control[0]
    dy = p_fin[1] - p_control[1]
    angulo = math.atan2(dy, dx)
    
    # Puntos de la cabeza de la flecha
    largo_cabeza = 45
    ancho_cabeza = 25
    
    p1 = (p_fin[0] - largo_cabeza * math.cos(angulo - 0.4), p_fin[1] - largo_cabeza * math.sin(angulo - 0.4))
    p2 = (p_fin[0] - largo_cabeza * math.cos(angulo + 0.4), p_fin[1] - largo_cabeza * math.sin(angulo + 0.4))
    
    # Dibujar cabeza de flecha (contorno y relleno)
    for dx_c in range(-6, 7):
        for dy_c in range(-6, 7):
            if dx_c*dx_c + dy_c*dy_c <= 49:
                draw_ctx.polygon([p_fin, (p1[0]+dx_c, p1[1]+dy_c), (p2[0]+dx_c, p2[1]+dy_c)], fill=(0, 0, 0, 255))
                
    draw_ctx.polygon([p_fin, p1, p2], fill=color)

def dibujar_arco_bezier(draw_ctx, p0, p1, p2, color, grosor, pasos=40):
    """
    Dibuja segmentos continuos simulando una curva Bézier cuadrática.
    """
    puntos = []
    for t_step in range(pasos + 1):
        t = t_step / pasos
        # Fórmulas de Bézier cuadrática
        x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        puntos.append((x, y))
        
    for i in range(len(puntos) - 1):
        draw_ctx.line([puntos[i], puntos[i+1]], fill=color, width=grosor)

def descargar_doctor_real(ruta_salida):
    """
    Descarga una imagen de stock de doctor masculino profesional recortado en PNG transparente nativo
    para garantizar bordes y colores impecables sin fallas de luma-keying de IA.
    """
    urls = [
        "https://www.pngmart.com/files/22/Male-Doctor-PNG-HD.png",
        "https://www.pngmart.com/files/22/Doctor-PNG-Transparent.png",
        "https://www.pngall.com/wp-content/uploads/2018/04/Doctor-PNG-File.png"
    ]
    for url in urls:
        try:
            print(f"⬇️ Descargando doctor masculino profesional PNG transparente desde: {url}...")
            res = requests.get(url, timeout=25)
            if res.status_code == 200 and len(res.content) > 50000:
                with open(ruta_salida, "wb") as f:
                    f.write(res.content)
                print("✅ Doctor masculino profesional descargado y guardado con éxito.")
                return True
        except Exception as e:
            print(f"⚠️ Error descargando doctor desde {url}: {e}")
    return False

def aplicar_estilo_miniatura(ruta_fondo, ruta_salida, texto_clickbait, color_texto="yellow"):
    # Wrapper compatible con la API anterior
    aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_salida, texto_clickbait)

def aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_salida, texto_clickbait, layout_config=None, elemento_clave="", url_runpod=""):
    """
    Toma una imagen de fondo (ej. el ojo), superpone al doctor constante,
    el elemento clave brillante (glow), la flecha roja curvada, y dibuja
    los títulos en el lado izquierdo con banners 3D redondeados.
    """
    print(f"🎨 Componiendo miniatura clickbait avanzada (Fotomontaje)...")
    
    # 1. Cargar fondo y asegurar resolución 1280x720
    if not os.path.exists(ruta_fondo):
        print(f"⚠️ Fondo {ruta_fondo} no encontrado. Creando un fondo oscuro...")
        img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
    else:
        img = Image.open(ruta_fondo).convert("RGB")
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        
    # Configuración de diseño por defecto si no viene del análisis de Gemini (Sujeto derecha, Texto izquierda)
    if not layout_config:
        layout_config = {
            "texto_posicion_x": "left",
            "texto_alineacion": "left",
            "color_primario": "yellow",
            "color_secundario": "white",
            "inclinacion_grados": -3,
            "sujeto_posicion_x": "right",
            "tiene_banner": True
        }
        
    # Asegurar que el sujeto vaya a la derecha y el texto a la izquierda como la competencia
    pos_x = layout_config.get("texto_posicion_x", "left")
    sujeto_pos_x = layout_config.get("sujeto_posicion_x", "right")
    
    # Auto-completar elemento_clave de forma inteligente si viene vacío por metadatos antiguos
    if not elemento_clave:
        clickbait_lower = texto_clickbait.lower()
        if "gafas" in clickbait_lower or "ojos" in clickbait_lower or "visión" in clickbait_lower or "vista" in clickbait_lower or "fruta" in clickbait_lower:
            elemento_clave = "dried date fruit"
        elif "ajo" in clickbait_lower:
            elemento_clave = "garlic bulb"
        elif "romero" in clickbait_lower:
            elemento_clave = "rosemary branch"
        else:
            elemento_clave = "healthy capsule"

    # 2. RESOLVER Y CARGAR PERSONAJE DOCTOR CONSTANTE (DOCTOR MASCULINO)
    # Ubicación del archivo de doctor constante
    ruta_doctor_constante = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doctor_masculino.png")
    
    if not os.path.exists(ruta_doctor_constante):
        print("👤 doctor_masculino.png no existe. Descargando personaje clínico fotorrealista transparente...")
        # Descargar directamente un doctor fotorrealista real con fondo transparente de stock
        descargar_doctor_real(ruta_doctor_constante)
            
    # Cargar doctor PNG recortado si existe
    img_doctor = None
    if os.path.exists(ruta_doctor_constante):
        try:
            img_doctor = Image.open(ruta_doctor_constante).convert("RGBA")
            print("👤 Cargado doctor constante del canal.")
        except Exception as e:
            print(f"⚠️ Error al abrir doctor_masculino.png: {e}")
            
    # 3. GENERAR Y CARGAR ELEMENTO CLAVE (EJ: DÁTIL, AJO, ROMERO) CON GLOW
    img_elemento = None
    if elemento_clave and url_runpod:
        print(f"🍏 Generando elemento clave '{elemento_clave}' en RunPod...")
        prompt_elem = f"A single detailed fresh {elemento_clave} fruit, isolated, macro photography, sharp focus, solid pitch black background, photorealistic, 8k"
        ruta_elem_temp = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"elem_{elemento_clave}.png")
        
        import generador
        exito_elem = generador.generar_fondo_miniatura(url_runpod, prompt_elem, ruta_elem_temp, seed=777)
        if exito_elem and os.path.exists(ruta_elem_temp):
            # Recortar fondo del elemento
            elem_raw = Image.open(ruta_elem_temp)
            img_elemento = remove_black_background(elem_raw, threshold=40)
            try:
                os.remove(ruta_elem_temp)
            except:
                pass
            print(f"🍏 Elemento clave '{elemento_clave}' listo.")
            
    # 4. COMPOSICIÓN DE CAPAS (FONDO + DOCTOR + ELEMENTO + GLOW)
    canvas = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    canvas.paste(img.convert("RGBA"), (0, 0))
    
    # Dibujar aura brillante (Glow) detrás del elemento
    if img_doctor and sujeto_pos_x == "right":
        # Posicionar doctor a la derecha (redimensionado proporcional a 720px de alto)
        # Ancho estimado proporcional: aprox 500-600px
        orig_w, orig_h = img_doctor.size
        new_h = 720
        new_w = int(orig_w * (new_h / orig_h))
        img_doctor_res = img_doctor.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Coordenada del doctor a la derecha
        doc_x = 1280 - new_w + 100 # Leve offset hacia afuera
        doc_y = 0
        
        # Si hay dátil/elemento, colocarlo flotando en frente o en la mano
        if img_elemento:
            # Redimensionar elemento clave a aprox 200x200px
            img_elemento_res = img_elemento.resize((190, 190), Image.Resampling.LANCZOS)
            
            # Posicionamiento del dátil delante del doctor (mano estimada)
            elem_x = doc_x + 100
            elem_y = 300
            
            # Dibujar el aura brillante (Glow radial dorado) en el canvas transparente
            glow_radius = 240
            glow_layer = Image.new("RGBA", (glow_radius, glow_radius), (0, 0, 0, 0))
            g_draw = ImageDraw.Draw(glow_layer)
            for r in range(glow_radius, 0, -6):
                # Degradado de amarillo a transparente
                alpha = int(((glow_radius - r) / glow_radius) * 110)
                g_draw.ellipse(
                    [(glow_radius//2 - r//2, glow_radius//2 - r//2), (glow_radius//2 + r//2, glow_radius//2 + r//2)],
                    fill=(255, 170, 0, alpha)
                )
            # Pegar el glow centrado en el elemento
            canvas.paste(glow_layer, (elem_x + 95 - glow_radius//2, elem_y + 95 - glow_radius//2), glow_layer)
            
            # Pegar el doctor en el canvas
            canvas.paste(img_doctor_res, (doc_x, doc_y), img_doctor_res)
            # Pegar el dátil encima del doctor
            canvas.paste(img_elemento_res, (elem_x, elem_y), img_elemento_res)
        else:
            # Solo pegar al doctor si no hay elemento clave
            canvas.paste(img_doctor_res, (doc_x, doc_y), img_doctor_res)
    else:
        # Fallback si no hay doctor: pegar elemento grande en el centro derecho
        if img_elemento:
            img_elemento_res = img_elemento.resize((350, 350), Image.Resampling.LANCZOS)
            elem_x = 800
            elem_y = 180
            
            glow_radius = 450
            glow_layer = Image.new("RGBA", (glow_radius, glow_radius), (0, 0, 0, 0))
            g_draw = ImageDraw.Draw(glow_layer)
            for r in range(glow_radius, 0, -8):
                alpha = int(((glow_radius - r) / glow_radius) * 120)
                g_draw.ellipse(
                    [(glow_radius//2 - r//2, glow_radius//2 - r//2), (glow_radius//2 + r//2, glow_radius//2 + r//2)],
                    fill=(255, 170, 0, alpha)
                )
            canvas.paste(glow_layer, (elem_x + 175 - glow_radius//2, elem_y + 175 - glow_radius//2), glow_layer)
            canvas.paste(img_elemento_res, (elem_x, elem_y), img_elemento_res)
            
    # 5. DIBUJAR LA FLECHA ROJA CURVA CONECTORA
    # La flecha apunta de la zona del texto (izquierda: x=500, y=180) hacia el elemento brillante (derecha: x=880, y=360)
    canvas_draw = ImageDraw.Draw(canvas)
    if img_doctor and img_elemento and sujeto_pos_x == "right":
        p_ini = (490, 180)
        p_ctrl = (690, 210)
        p_fn = (doc_x + 120, 310)
        dibujar_flecha_curva(canvas_draw, p_ini, p_ctrl, p_fn, color=(230, 0, 0, 255), grosor=16)
        
    # 6. CONFIGURAR FUENTES IMPACT
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
            
    font_size = 105
    if len(texto_clickbait) > 20:
        font_size = 88
    if len(texto_clickbait) > 30:
        font_size = 76
        
    if fuente_path:
        font = ImageFont.truetype(fuente_path, font_size)
    else:
        font = ImageFont.load_default()
        
    # 7. WRAPPING INTELIGENTE DEL TEXTO
    # Max width de 550px para texto en la izquierda
    max_width = 580
    palabras = texto_clickbait.upper().split()
    lineas = []
    linea_actual = []
    
    for palabra in palabras:
        linea_actual.append(palabra)
        test_linea = " ".join(linea_actual)
        if canvas_draw.textlength(test_linea, font=font) <= max_width:
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
        
    # 8. DIBUJAR BANNERS 3D REDONDEADOS Y TEXTOS GIGANTES EN LIENZO TRANSAPRENTE
    texto_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(texto_layer)
    
    # Posicionar texto a la izquierda
    if pos_x == "left":
        txt_x = 55
    elif pos_x == "right":
        txt_x = 680
    else:
        txt_x = 350
        
    line_height = font_size + 24
    total_height = len(lineas) * line_height
    txt_y_start = (720 - total_height) // 2
    
    color_map = {
        "yellow": (255, 235, 59, 255),
        "red": (244, 67, 54, 255),
        "white": (255, 255, 255, 255),
        "green": (57, 255, 20, 255) # Verde neón brillante
    }
    
    c_primario = layout_config.get("color_primario", "yellow").lower()
    c_secundario = layout_config.get("color_secundario", "white").lower()
    col_p = color_map.get(c_primario, (255, 235, 59, 255))
    col_s = color_map.get(c_secundario, (255, 255, 255, 255))
    
    for i, linea in enumerate(lineas):
        txt_y = txt_y_start + (i * line_height)
        col_actual = col_p if i % 2 == 0 else col_s
        
        bbox = t_draw.textbbox((txt_x, txt_y), linea, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        
        # Dibujar Banner 3D con bordes redondeados
        if layout_config.get("tiene_banner"):
            pad_w = 32
            pad_h = 16
            rx = 15 # Radio de redondeado
            
            # Capa 1: Sombra negra desplazada
            offset = 8
            t_draw.rounded_rectangle(
                [txt_x - pad_w + offset, txt_y - pad_h + offset, txt_x + lw + pad_w + offset, txt_y + lh + pad_h * 2 + offset],
                radius=rx,
                fill=(0, 0, 0, 180)
            )
            
            # Capa 2: Banner principal rojo o negro con degradado
            banner_color = (200, 0, 0, 255) if i % 2 == 0 else (15, 23, 42, 255)
            t_draw.rounded_rectangle(
                [txt_x - pad_w, txt_y - pad_h, txt_x + lw + pad_w, txt_y + lh + pad_h * 2],
                radius=rx,
                fill=banner_color
            )
            
            # Capa 3: Brillo de contorno superior fino (efecto relieve)
            contorno_color = (255, 100, 100, 255) if i % 2 == 0 else (70, 85, 105, 255)
            t_draw.rounded_rectangle(
                [txt_x - pad_w, txt_y - pad_h, txt_x + lw + pad_w, txt_y + lh + pad_h * 2],
                radius=rx,
                outline=contorno_color,
                width=3
            )
            
        # Capa 4: Soft Neon Glow / Halo (Desenfocado para dar luz neón)
        try:
            from PIL import ImageFilter
            glow_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow_layer)
            glow_color = (col_actual[0], col_actual[1], col_actual[2], 200)
            gd.text((txt_x, txt_y), linea, font=font, fill=glow_color, stroke_width=22)
            glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=10))
            texto_layer = Image.alpha_composite(texto_layer, glow_blurred)
            t_draw = ImageDraw.Draw(texto_layer)
        except Exception as e:
            print(f"⚠️ No se pudo aplicar efecto de neón: {e}")
            
        # Capa 5: Sombra negra proyectada profunda (Drop shadow de 7px en diagonal)
        sh_offset_x = 7
        sh_offset_y = 7
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                t_draw.text((txt_x + sh_offset_x + dx, txt_y + sh_offset_y + dy), linea, font=font, fill=(0, 0, 0, 220))
                
        # Capa 6: Contorno negro nítido clásico (stroke outline para máxima visibilidad en móviles)
        grosor = 8
        for dx in range(-grosor, grosor + 1):
            for dy in range(-grosor, grosor + 1):
                if dx*dx + dy*dy <= grosor*grosor:
                    t_draw.text((txt_x + dx, txt_y + dy), linea, font=font, fill=(0, 0, 0, 255))
                    
        # Capa 7: Texto principal (en primer plano con el color asignado)
        t_draw.text((txt_x, txt_y), linea, font=font, fill=col_actual)
        
    # 9. Aplicar rotación/inclinación al lienzo de texto si es requerido
    grados = layout_config.get("inclinacion_grados", 0)
    if grados != 0:
        texto_layer = texto_layer.rotate(grados, resample=Image.Resampling.BICUBIC, center=(640, 360))
        
    # 10. FUSIONAR Y GUARDAR
    img_final = Image.alpha_composite(canvas, texto_layer).convert("RGB")
    
    dir_salida = os.path.dirname(ruta_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    img_final.save(ruta_salida, "PNG")
    print(f"✅ Fotomontaje de miniatura clickbait terminado en: {ruta_salida}")

def analizar_miniatura_con_openai(ruta_imagen, api_key):
    """
    Analiza la miniatura del competidor usando GPT-4o Vision de OpenAI.
    """
    try:
        with open(ruta_imagen, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
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
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        res = requests.post(url, json=payload, headers=headers, timeout=30).json()
        if "choices" in res and len(res["choices"]) > 0:
            res_text = res["choices"][0]["message"]["content"]
            return json.loads(res_text)
    except Exception as e:
        print(f"⚠️ Error al analizar miniatura con OpenAI: {e}")
    return None

def generar_fondo_miniatura_con_dalle3(prompt, api_key, ruta_salida):
    """
    Genera un fondo de miniatura clickbait ultra realista con DALL-E 3.
    """
    try:
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=60).json()
        if "data" in res and len(res["data"]) > 0:
            img_url = res["data"][0]["url"]
            img_res = requests.get(img_url, stream=True, timeout=20)
            if img_res.status_code == 200:
                with open(ruta_salida, "wb") as f:
                    for chunk in img_res.iter_content(8192):
                        f.write(chunk)
                
                # Redimensionar la imagen de 1024x1024 de DALL-E 3 a 1280x720 (proporción YouTube)
                # Para evitar distorsión, hacemos un recortado (crop) o redimensionamiento inteligente
                from PIL import Image
                img_pil = Image.open(ruta_salida)
                # Recortar verticalmente para quedar en 16:9
                ancho, alto = img_pil.size
                nuevo_alto = int(ancho * 9 / 16)
                offset = (alto - nuevo_alto) // 2
                img_recortada = img_pil.crop((0, offset, ancho, offset + nuevo_alto))
                img_final = img_recortada.resize((1280, 720), Image.Resampling.LANCZOS)
                img_final.save(ruta_salida, "PNG")
                
                print(f"✅ Fondo de miniatura DALL-E 3 guardado y redimensionado a 1280x720 en {ruta_salida}")
                return True
        else:
            print(f"❌ Error de respuesta de DALL-E 3: {res}")
    except Exception as e:
        print(f"⚠️ Error general al llamar a DALL-E 3: {e}")
    return False

def generar_fondo_miniatura_gratis_pollinations(prompt, ruta_salida):
    """
    Genera un fondo de miniatura gratis usando FLUX.1 de Pollinations.ai (1280x720).
    """
    try:
        import urllib.parse
        prompt_encoded = urllib.parse.quote(prompt.strip())
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1280&height=720&model=flux&nologo=true"
        
        print(f"📡 Solicitando imagen gratis a Pollinations (FLUX)... URL: {url}")
        res = requests.get(url, stream=True, timeout=40)
        if res.status_code == 200:
            with open(ruta_salida, "wb") as f:
                for chunk in res.iter_content(8192):
                    f.write(chunk)
            print(f"✅ Miniatura gratis generada y guardada en: {ruta_salida}")
            return True
        else:
            print(f"❌ Error de Pollinations: Código HTTP {res.status_code}")
    except Exception as e:
        print(f"⚠️ Error al conectar con Pollinations: {e}")
    return False

def descargar_fragmento_video(video_id, ruta_salida_mp4):
    """
    Descarga únicamente los primeros 10 segundos del video de YouTube en baja calidad.
    """
    import subprocess
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"📡 Descargando fragmento de 10s del video competidor {video_id}...")
    
    # yt-dlp comando para descargar los primeros 10 segundos en la peor calidad (pequeño y rápido)
    cmd = [
        "yt-dlp",
        "--download-sections", "*0-10",
        "-f", "worst",
        "-o", ruta_salida_mp4,
        url
    ]
    try:
        # Ejecutar de forma síncrona
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if resultado.returncode == 0 and os.path.exists(ruta_salida_mp4):
            print(f"✅ Fragmento de video descargado exitosamente en: {ruta_salida_mp4}")
            return True
        else:
            print(f"❌ Falló la descarga del fragmento con yt-dlp (Código {resultado.returncode}): {resultado.stderr}")
    except Exception as e:
        print(f"⚠️ Error al ejecutar yt-dlp: {e}")
    return False

def extraer_fotogramas(ruta_video, directorio_salida):
    """
    Extrae fotogramas fijos del video usando FFmpeg.
    """
    import subprocess
    print(f"🎞️ Extrayendo fotogramas de {ruta_video}...")
    
    # Extraer una captura cada 4 segundos (a 15fps, select='not(mod(n,60))')
    # Guardar en directorio_salida como frame_001.jpg, frame_002.jpg
    patron_salida = os.path.join(directorio_salida, "frame_%03d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", ruta_video,
        "-vf", "select=not(mod(n,60))",
        "-vsync", "vfr",
        "-q:v", "2",
        patron_salida
    ]
    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if resultado.returncode == 0:
            # Buscar archivos creados
            archivos = [os.path.join(directorio_salida, f) for f in os.listdir(directorio_salida) if f.startswith("frame_") and f.endswith(".jpg")]
            archivos.sort()
            print(f"✅ Fotogramas extraídos: {archivos}")
            return archivos
        else:
            print(f"❌ FFmpeg falló (Código {resultado.returncode}): {resultado.stderr}")
    except Exception as e:
        print(f"⚠️ Error al ejecutar FFmpeg para extraer fotogramas: {e}")
    return []

def analizar_estilo_video_con_gemini(rutas_imagenes, api_key):
    """
    Envía los fotogramas a Gemini Vision para clasificar el estilo del video.
    """
    try:
        parts = []
        prompt = (
            "Analiza las siguientes capturas reales del contenido de un video de YouTube e identifica cuál de los siguientes estilos visuales/artísticos de video representa mejor el estilo visual general de la producción:\n"
            "1. 'realistic' (si parece metraje real, de stock, documental, clínico o fotorrealista)\n"
            "2. '3d pixar' (si parece animación 3D digital, estilo Pixar/Disney, modelado 3D cute/arcilla)\n"
            "3. 'illustration' (si parece ilustración vectorial 2D, diseño plano minimalista, gráficos/infografías)\n"
            "4. 'anime' (si parece estilo de dibujo anime/manga o cell shading)\n"
            "5. 'cyberpunk' (si es futurista, con hologramas, luces de neón y gráficos de interfaz de usuario de alta tecnología)\n"
            "6. 'custom' (si es un estilo completamente diferente como dibujo a lápiz, acuarelas pintadas, cómic retro, stop-motion, etc.)\n\n"
            "Responde estrictamente en formato JSON con la siguiente estructura:\n"
            "{\n"
            "  \"estilo\": \"realistic\" o \"3d pixar\" o \"illustration\" o \"anime\" o \"cyberpunk\" o \"custom\",\n"
            "  \"explicacion\": \"Breve frase en español explicando el porqué de la detección (máximo 15 palabras)\",\n"
            "  \"custom_prompt\": \"Si clasificaste como 'custom', escribe un prompt en inglés muy detallado y conciso de 1 línea para recrear este estilo en un modelo de video (ej. 'Retro vintage comic book illustration, hand-drawn sketch, detailed ink lines, {}'). Si no es custom, este campo debe ser una cadena vacía.\"\n"
            "}"
        )
        parts.append({"text": prompt})
        
        for ruta in rutas_imagenes:
            if os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                parts.append({
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": img_data
                    }
                })
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                texto_json = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if texto_json.startswith("```"):
                    texto_json = texto_json.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
                return json.loads(texto_json)
            else:
                print(f"❌ Respuesta vacía de Gemini: {data}")
        else:
            print(f"❌ Error HTTP de Gemini {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ Error general al analizar estilo de video con Gemini: {e}")
    return None

if __name__ == "__main__":
    aplicar_estilo_miniatura_avanzado("fondo_prueba.png", "miniatura_prueba.png", "AJO EN AYUNAS: ¡EXPLOTA TU SALUD!")
