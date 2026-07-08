import os
import subprocess
import sys
import glob

# Configurar encoding UTF-8 para evitar errores de consola en Windows con emojis
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def crear_archivo_concat(ruta_clips, archivo_txt):
    """
    Crea el archivo de texto que FFmpeg necesita para concatenar los clips de video.
    """
    # Buscar todos los archivos mp4 en la carpeta de clips
    clips = glob.glob(os.path.join(ruta_clips, "*.mp4"))
    clips.sort() # Ordenarlos alfabéticamente
    
    if not clips:
        return False
        
    with open(archivo_txt, "w", encoding="utf-8") as f:
        for clip in clips:
            # Reemplazar diagonales inversas para evitar problemas en Windows
            path_limpio = os.path.abspath(clip).replace("\\", "/")
            f.write(f"file '{path_limpio}'\n")
    return True
def ensamblar_video(ruta_audio, ruta_srt, ruta_clips, ruta_musica, ruta_salida, orientacion="horizontal", volumen_musica=0.12):
    """
    Ensambla el video final quemando subtítulos, mezclando audio y aplicando zoom a los clips.
    Soporta orientación horizontal y vertical.
    """
    print(f"🎬 Iniciando ensamblado de video ({orientacion}) con FFmpeg (volumen música: {volumen_musica})...")
    
    # 0. Resolver rutas absolutas
    ruta_audio_abs = os.path.abspath(ruta_audio).replace("\\", "/")
    ruta_srt_abs = os.path.abspath(ruta_srt).replace("\\", "/")
    ruta_clips_abs = os.path.abspath(ruta_clips).replace("\\", "/")
    ruta_musica_abs = os.path.abspath(ruta_musica).replace("\\", "/") if ruta_musica else None
    ruta_salida_abs = os.path.abspath(ruta_salida).replace("\\", "/")
    
    dir_salida = os.path.dirname(ruta_salida_abs)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
        
    # 1. Verificar si hay clips de video disponibles
    archivo_concat = "concat_list.txt"
    tiene_clips = False
    
    if os.path.exists(ruta_clips_abs) and os.path.isdir(ruta_clips_abs):
        tiene_clips = crear_archivo_concat(ruta_clips_abs, archivo_concat)
        
    # Quirk de FFmpeg en Windows para libass: escapar el caracter de dos puntos de la unidad (ej: C\:/)
    # y los espacios para que no rompa el filtro de subtítulos.
    if ":" in ruta_srt_abs:
        drive, path = ruta_srt_abs.split(":", 1)
        srt_escapado = f"{drive}\\:{path}"
    else:
        srt_escapado = ruta_srt_abs
        
    srt_escapado = srt_escapado.replace(" ", "\\ ")
        
    # Si es formato ASS, usar los estilos del propio archivo (como el karaoke por palabra)
    if ruta_srt_abs.endswith(".ass"):
        subtitles_filter = f"subtitles='{srt_escapado}'"
    else:
        # Estilo de subtítulos SRT (Montserrat/Impact, amarillo con borde negro grueso)
        fontsize = 28 if orientacion == "vertical" else 22
        margin_v = 150 if orientacion == "vertical" else 30 # Levantar subtítulos en Reels para que no los tape la interfaz
        subtitles_filter = f"subtitles='{srt_escapado}':force_style='Fontname=Arial,Fontsize={fontsize},PrimaryColour=&H00E5FF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV={margin_v}'"
    
    # Filtro de Zoom Dinámico (Ken Burns)
    # Aplica un sutil zoom progresivo en cada clip
    zoom_filter = "zoompan=z='min(zoom+0.0015,1.3)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

    # Combinación de filtros
    video_filter = f"{zoom_filter},{subtitles_filter}"

    # 2. Construir comando de FFmpeg
    cmd = ["ffmpeg", "-y"]
    
    if tiene_clips:
        print("📹 Clips detectados. Generando video con bucle de clips...")
        # Entradas: 0 = Video en bucle, 1 = Voz en off
        cmd.extend(["-stream_loop", "-1", "-f", "concat", "-safe", "0", "-i", archivo_concat])
    else:
        print("⚠️ No se encontraron clips. Creando video de prueba con fondo sólido...")
        # Entradas: 0 = Color de fondo azul, 1 = Voz en off
        res_solid = "720x1280" if orientacion == "vertical" else "1280x720"
        cmd.extend(["-f", "lavfi", "-i", f"color=c=0x1e293b:s={res_solid}:rate=30"])
        
    cmd.extend(["-i", ruta_audio_abs])
    
    # Agregar música de fondo si existe
    tiene_musica = False
    if ruta_musica_abs and os.path.exists(ruta_musica_abs):
        tiene_musica = True
        cmd.extend(["-stream_loop", "-1", "-i", ruta_musica_abs])
        
    # Filtro de video (Zoom + Subtítulos)
    cmd.extend(["-vf", video_filter])
    
    # Configuración de Audio (Mezcla de voz en off + música)
    if tiene_musica:
        # Mezclar pistas: Voz (index 1) al 100%, Música (index 2) al volumen deseado
        cmd.extend([
            "-filter_complex", 
            f"[1:a]volume=1.0[voz];[2:a]volume={volumen_musica}[musica];[voz][musica]amix=inputs=2:duration=first[a]"
        ])
        cmd.extend(["-map", "0:v", "-map", "[a]"])
    else:
        # Solo mapear el video y el audio de la voz en off
        if tiene_clips:
            cmd.extend(["-map", "0:v", "-map", "1:a"])
        else:
            cmd.extend(["-map", "0:v", "-map", "1:a"])
            
    # Códecs de compresión compatibles con YouTube
    cmd.extend([
        "-c:v", "libx264", 
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", 
        "-b:a", "192k",
        "-shortest", # Detener el video cuando el audio (voz en off) termine
        ruta_salida_abs
    ])
    
    # Ejecución
    print(f"🚀 Ejecutando comando FFmpeg...")
    try:
        resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        print("🎉 ¡Video compilado con éxito!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en la compilación de FFmpeg:\n{e.stderr}")
        raise e
    finally:
        # Limpiar archivo temporal de lista
        if os.path.exists(archivo_concat):
            os.remove(archivo_concat)

if __name__ == "__main__":
    # Prueba local
    try:
        ensamblar_video(
            ruta_audio="prueba_voz.mp3",
            ruta_srt="prueba_subtitulos.srt",
            ruta_clips="clips",
            ruta_musica=None,
            ruta_salida="video_prueba_final.mp4"
        )
    except Exception as e:
        print(f"Prueba fallida: {e}")
