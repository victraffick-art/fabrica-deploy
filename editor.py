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
def obtener_duracion_audio(ruta_audio):
    """
    Obtiene la duración exacta en segundos del archivo de audio usando ffprobe.
    """
    cmd = [
        "ffprobe", "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        ruta_audio
    ]
    try:
        resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(resultado.stdout.strip())
    except Exception as e:
        print(f"⚠️ No se pudo obtener la duración de la voz en off, usando 60.0s por defecto. Error: {e}")
        return 60.0

def ensamblar_video(ruta_audio, ruta_srt, ruta_clips, ruta_musica, ruta_salida, orientacion="horizontal", volumen_musica=0.12):
    """
    Ensambla el video final quemando subtítulos, mezclando audio, aplicando zoom y transiciones xfade dinámicas.
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
    clips = []
    if os.path.exists(ruta_clips_abs) and os.path.isdir(ruta_clips_abs):
        clips = glob.glob(os.path.join(ruta_clips_abs, "*.mp4"))
        clips.sort()
        
    # Quirk de FFmpeg en Windows para libass
    if ":" in ruta_srt_abs:
        drive, path = ruta_srt_abs.split(":", 1)
        srt_escapado = f"{drive}\\:{path}"
    else:
        srt_escapado = ruta_srt_abs
    srt_escapado = srt_escapado.replace(" ", "\\ ")
        
    # Si es formato ASS, usar los estilos del propio archivo
    if ruta_srt_abs.endswith(".ass"):
        subtitles_filter = f"subtitles='{srt_escapado}'"
    else:
        # Estilo de subtítulos SRT
        fontsize = 28 if orientacion == "vertical" else 22
        margin_v = 150 if orientacion == "vertical" else 30
        subtitles_filter = f"subtitles='{srt_escapado}':force_style='Fontname=Arial,Fontsize={fontsize},PrimaryColour=&H00E5FF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV={margin_v}'"
    
    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    
    tiene_clips = len(clips) > 0
    tiene_musica = ruta_musica_abs and os.path.exists(ruta_musica_abs)
    
    if tiene_clips:
        # Calcular duración de la voz para saber cuántos clips necesitamos
        dur_audio = obtener_duracion_audio(ruta_audio_abs)
        print(f"🎙️ Duración detectada de voz en off: {dur_audio:.2f} segundos.")
        
        # Con clips de 5s y traslape de 0.5s, cada uno aporta 4.5s (excepto el último que aporta 5s)
        # Asegurar suficientes clips para cubrir el audio con margen
        clips_necesarios = int((dur_audio + 4.5) / 4.5) + 1
        clips_necesarios = max(2, clips_necesarios)
        
        # Repetir la lista en ciclo para rellenar
        clips_repetidos = (clips * (int(clips_necesarios / len(clips)) + 1))[:clips_necesarios]
        print(f"📹 Se usarán {len(clips_repetidos)} clips (duración estimada del carrusel: {len(clips_repetidos)*4.5 + 0.5:.2f}s).")
        
        # Agregar entradas de video
        for clip_path in clips_repetidos:
            cmd.extend(["-i", os.path.abspath(clip_path).replace("\\", "/")])
            
        # El audio y la música van después de los videos
        idx_audio = len(clips_repetidos)
        cmd.extend(["-i", ruta_audio_abs])
        
        if tiene_musica:
            idx_musica = idx_audio + 1
            cmd.extend(["-stream_loop", "-1", "-i", ruta_musica_abs])
            
        # Preprocesar cada clip (fps, zoom, escala, duracion 5s)
        for i in range(len(clips_repetidos)):
            res = "720x1280" if orientacion == "vertical" else "1280x720"
            w, h = (720, 1280) if orientacion == "vertical" else (1280, 720)
            
            zoom_filter = f"zoompan=z='min(zoom+0.0015,1.3)':d=150:s={res}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            
            if i == 0:
                # Transición inicial de fade-in para la retención del principio del video
                filter_parts.append(f"[{i}:v]fps=30,scale={w}:{h}:flags=lanczos,{zoom_filter},trim=0:5,setpts=PTS-STARTPTS[v0_pre]; [v0_pre]fade=t=in:st=0:d=1.0[v_trans0]")
            else:
                filter_parts.append(f"[{i}:v]fps=30,scale={w}:{h}:flags=lanczos,{zoom_filter},trim=0:5,setpts=PTS-STARTPTS[v_trans{i}]")
                
        # Encadenar transiciones xfade
        last_label = "[v_trans0]"
        trans_list = ["slideleft", "slideright", "fade", "slideup", "slidedown", "wipeleft", "wiperight"]
        
        for i in range(1, len(clips_repetidos)):
            trans = trans_list[(i-1) % len(trans_list)]
            offset = i * 4.5
            next_label = f"[v_link{i}]"
            filter_parts.append(f"{last_label}[v_trans{i}]xfade=transition={trans}:duration=0.5:offset={offset:.2f}{next_label}")
            last_label = next_label
            
        # Aplicar filtro de subtítulos al video combinado
        filter_parts.append(f"{last_label}{subtitles_filter}[v_final]")
        
        # Audio
        if tiene_musica:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[voz]; [{idx_musica}:a]volume={volumen_musica}[musica]; [voz][musica]amix=inputs=2:duration=first[a]")
        else:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[a]")
            
    else:
        # Fallback sin clips
        print("⚠️ No se encontraron clips. Creando video de prueba con fondo sólido...")
        res_solid = "720x1280" if orientacion == "vertical" else "1280x720"
        cmd.extend(["-f", "lavfi", "-i", f"color=c=0x1e293b:s={res_solid}:rate=30"])
        cmd.extend(["-i", ruta_audio_abs])
        
        idx_audio = 1
        if tiene_musica:
            idx_musica = 2
            cmd.extend(["-stream_loop", "-1", "-i", ruta_musica_abs])
            
        filter_parts.append(f"[0:v]{subtitles_filter}[v_final]")
        
        if tiene_musica:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[voz]; [{idx_musica}:a]volume={volumen_musica}[musica]; [voz][musica]amix=inputs=2:duration=first[a]")
        else:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[a]")
            
    # Asignar filtros y mapas
    cmd.extend(["-filter_complex", "; ".join(filter_parts)])
    cmd.extend(["-map", "[v_final]", "-map", "[a]"])
            
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
