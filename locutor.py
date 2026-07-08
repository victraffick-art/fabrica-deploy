import asyncio
import edge_tts
import sys
import os
import argparse

# Configurar encoding UTF-8 para evitar errores de consola en Windows con emojis
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def guardar_ass_karaoke(submaker, ruta_ass, orientacion="horizontal", font_name="Arial Black", primary_color="yellow", secondary_color="white", effect_type="karaoke", max_words_per_line=3, font_size=None, outline_thickness=3, alignment=2, margin_v=None):
    """
    Convierte las marcas de tiempo por palabra de edge_tts en un archivo .ass con estilos dinámicos.
    Soporta tipografías, colores primarios/secundarios personalizados y efectos (barrido karaoke o palabra por palabra).
    """
    # Si no se define el tamaño, usar valores por defecto dependientes de la orientación
    if font_size is None or font_size == 0:
        fontsize = 84 if orientacion == "vertical" else 64
    else:
        fontsize = font_size
        
    if margin_v is None or margin_v == 0:
        margin_vertical = 360 if orientacion == "vertical" else 150
    else:
        margin_vertical = margin_v
    
    color_map = {
        "white": "&H00FFFFFF",
        "yellow": "&H0000FFFF",
        "red": "&H000000FF",
        "green": "&H0000FF00",
        "cyan": "&H00FFFF00",
        "blue": "&H00FF0000",
        "gray": "&H00A0A0A0",
        "magenta": "&H00FF00FF",
        "orange": "&H0000A5FF",
        "purple": "&H00800080"
    }
    
    col_prim = color_map.get(primary_color.lower(), "&H0000FFFF") # Color al hablar
    col_sec = color_map.get(secondary_color.lower(), "&H00FFFFFF")  # Color inactivo
    
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fontsize},{col_prim},{col_sec},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline_thickness},1,{alignment},10,10,{margin_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    lineas = []
    linea_actual = []
    
    max_caracteres = 25 if orientacion == "vertical" else 38
    max_silencio_100ns = 6000000 # 0.6 segundos
    
    ult_fin = 0
    
    for cue in submaker.cues:
        inicio = int(cue.start.total_seconds() * 10000000)
        fin = int(cue.end.total_seconds() * 10000000)
        texto = cue.content
        
        if linea_actual:
            if max_words_per_line > 0:
                # Partir por cantidad de palabras
                debe_partir = len(linea_actual) >= max_words_per_line or (inicio - ult_fin > max_silencio_100ns)
            else:
                # Partir por cantidad de caracteres (original)
                largo_actual = sum(len(w[2]) for w in linea_actual) + len(linea_actual)
                debe_partir = (inicio - ult_fin > max_silencio_100ns) or (largo_actual + len(texto) > max_caracteres)
                
            if debe_partir:
                lineas.append(linea_actual)
                linea_actual = []
        
        linea_actual.append((inicio, fin, texto))
        ult_fin = fin
        
    if linea_actual:
        lineas.append(linea_actual)
        
    dialogos = []
    for line in lineas:
        start_time_100ns = line[0][0]
        end_time_100ns = line[-1][1]
        
        def fmt_time(t_100ns):
            total_sec = t_100ns / 10000000
            hrs = int(total_sec // 3600)
            mins = int((total_sec % 3600) // 60)
            secs = int(total_sec % 60)
            cs = int((t_100ns % 10000000) / 100000)
            return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"
            
        start_str = fmt_time(start_time_100ns)
        end_str = fmt_time(end_time_100ns)
        
        texto_karaoke = ""
        ult_w_fin = start_time_100ns
        
        if effect_type == "static":
            for start_w, end_w, word in line:
                texto_karaoke += f"{word} "
        else:
            for start_w, end_w, word in line:
                silence_duration_cs = int((start_w - ult_w_fin) / 100000)
                if silence_duration_cs > 0:
                    texto_karaoke += f"{{\\k{silence_duration_cs}}}"
                    
                word_duration_cs = int((end_w - start_w) / 100000)
                if word_duration_cs <= 0:
                    word_duration_cs = 1
                    
                # Seleccionar animación/efecto: kf es barrido suave (karaoke), k es aparición inmediata (pop)
                tag_efecto = "kf" if effect_type == "karaoke" else "k"
                texto_karaoke += f"{{\\{tag_efecto}{word_duration_cs}}}{word} "
                ult_w_fin = end_w
            
        dialogos.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{texto_karaoke.strip()}")
        
    with open(ruta_ass, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(dialogos))
    print(f"✅ Subtítulos de Karaoke ASS guardados con estilo personalizado en: {ruta_ass}")

async def generar_audio_y_subtitulos(texto, ruta_mp3, ruta_srt, voz="es-MX-JorgeNeural", ruta_ass=None, orientacion="horizontal", font_name="Arial Black", primary_color="yellow", secondary_color="white", effect_type="karaoke", rate="+0%", pitch="+0Hz", max_words_per_line=3, font_size=None, outline_thickness=3, alignment=2, margin_v=None):
    """
    Genera el archivo de voz en off (mp3) y los subtítulos sincronizados (srt e ass para karaoke).
    """
    print(f"🎙️ Iniciando síntesis de voz usando la voz: {voz} (velocidad: {rate}, tono: {pitch})...")
    communicate = edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch)
    submaker = edge_tts.SubMaker()
    
    # Crear carpetas si no existen
    dir_mp3 = os.path.dirname(ruta_mp3)
    if dir_mp3:
        os.makedirs(dir_mp3, exist_ok=True)
    dir_srt = os.path.dirname(ruta_srt)
    if dir_srt:
        os.makedirs(dir_srt, exist_ok=True)
        
    with open(ruta_mp3, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] in ["WordBoundary", "SentenceBoundary"]:
                submaker.feed(chunk)
                
    # Guardar subtítulos en formato SRT
    with open(ruta_srt, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
    print(f"✅ Subtítulos SRT guardados en: {ruta_srt}")
    
    # Si se pide ASS, generarlo con sus estilos
    if ruta_ass:
        guardar_ass_karaoke(submaker, ruta_ass, orientacion, font_name, primary_color, secondary_color, effect_type, max_words_per_line, font_size, outline_thickness, alignment, margin_v)
        
    print(f"✅ Voz guardada en: {ruta_mp3}")

def main():
    parser = argparse.ArgumentParser(description="Generador de Voz en Off y Subtítulos Gratis")
    parser.add_argument("--texto", required=True, help="Texto del guión a narrar")
    parser.add_argument("--mp3", required=True, help="Ruta de salida para el archivo MP3")
    parser.add_argument("--srt", required=True, help="Ruta de salida para el archivo SRT")
    parser.add_argument("--ass", default=None, help="Ruta de salida para los subtítulos ASS de Karaoke")
    parser.add_argument("--orientacion", default="horizontal", help="Orientación del video (horizontal/vertical)")
    parser.add_argument("--voz", default="es-MX-JorgeNeural", help="Voz neural a utilizar (ej. es-MX-JorgeNeural, es-ES-AlvaroNeural)")
    
    args = parser.parse_args()
    
    asyncio.run(generar_audio_y_subtitulos(args.texto, args.mp3, args.srt, args.voz, args.ass, args.orientacion))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        texto_prueba = "Hola Victor, este es el motor de voz neural gratuito funcionando perfectamente en tu computadora local."
        asyncio.run(generar_audio_y_subtitulos(texto_prueba, "prueba_voz.mp3", "prueba_subtitulos.srt", ruta_ass="prueba_karaoke.ass"))
