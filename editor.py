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

def ensamblar_video(ruta_audio, ruta_srt, ruta_clips, ruta_musica, ruta_salida, orientacion="horizontal", volumen_musica=0.12, callback_progreso=None, usar_transiciones=False):
    """
    Ensambla el video final quemando subtítulos, mezclando audio, aplicando zoom y transiciones xfade dinámicas.
    Evita el error WinError 206 en Windows usando nombres de archivo cortos en un directorio temporal 
    y pasando el filtro complejo a través de un archivo de texto con -filter_complex_script.
    Informa del progreso en tiempo real a través de callback_progreso.
    """
    import shutil
    import re
    print(f"🎬 Iniciando ensamblado de video ({orientacion}) con FFmpeg (volumen música: {volumen_musica})...")
    
    # 0. Resolver rutas absolutas
    ruta_audio_abs = os.path.abspath(ruta_audio)
    ruta_srt_abs = os.path.abspath(ruta_srt)
    ruta_clips_abs = os.path.abspath(ruta_clips)
    ruta_musica_abs = os.path.abspath(ruta_musica) if ruta_musica else None
    ruta_salida_abs = os.path.abspath(ruta_salida)
    
    dir_salida = os.path.dirname(ruta_salida_abs)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
        
    # Crear directorio temporal para enlaces cortos
    temp_dir = os.path.join(dir_salida, "temp_ffmpeg")
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    # 1. Verificar si hay clips de video disponibles
    clips = []
    if os.path.exists(ruta_clips_abs) and os.path.isdir(ruta_clips_abs):
        clips = glob.glob(os.path.join(ruta_clips_abs, "*.mp4"))
        clips.sort()
        
    tiene_clips = len(clips) > 0
    tiene_musica = ruta_musica_abs and os.path.exists(ruta_musica_abs)
    
    # Obtener duración del audio
    dur_audio = obtener_duracion_audio(ruta_audio_abs)
    print(f"🎙️ Duración detectada de voz en off: {dur_audio:.2f} segundos.")
    
    # Función auxiliar para enlazar o copiar archivos
    def enlazar_o_copiar(src, dest):
        try:
            # Crear enlace duro (rápido, 0 bytes)
            os.link(src, dest)
        except Exception:
            # Fallback a copia convencional
            shutil.copyfile(src, dest)
            
    # Enlazar archivos comunes
    audio_temp = os.path.join(temp_dir, "audio.mp3")
    enlazar_o_copiar(ruta_audio_abs, audio_temp)
    
    ext_srt = os.path.splitext(ruta_srt_abs)[1]
    srt_temp = os.path.join(temp_dir, f"subs{ext_srt}")
    enlazar_o_copiar(ruta_srt_abs, srt_temp)
    
    if tiene_musica:
        musica_temp = os.path.join(temp_dir, "music.mp3")
        enlazar_o_copiar(ruta_musica_abs, musica_temp)
        
    # Usaremos nombres relativos dentro del directorio de trabajo de FFmpeg (dir_salida)
    # Por lo tanto, el path de subtítulos es relativo y no requiere escapes complejos de Windows ni letras de unidad
    srt_rel = f"temp_ffmpeg/subs{ext_srt}"
    
    if ruta_srt_abs.endswith(".ass"):
        subtitles_filter = f"subtitles='{srt_rel}'"
    else:
        fontsize = 28 if orientacion == "vertical" else 22
        margin_v = 150 if orientacion == "vertical" else 30
        subtitles_filter = f"subtitles='{srt_rel}':force_style='Fontname=Arial,Fontsize={fontsize},PrimaryColour=&H00E5FF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV={margin_v}'"
    
    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    
    if tiene_clips:
        if usar_transiciones:
            # Con clips de 5s y traslape de 0.5s, cada uno aporta 4.5s
            clips_necesarios = int((dur_audio + 4.5) / 4.5) + 1
            clips_necesarios = max(2, clips_necesarios)
            
            # Repetir la lista en ciclo para rellenar
            clips_repetidos = (clips * (int(clips_necesarios / len(clips)) + 1))[:clips_necesarios]
            print(f"📹 Se usarán {len(clips_repetidos)} clips con transiciones (duración carrusel: {len(clips_repetidos)*4.5 + 0.5:.2f}s).")
            
            # Enlazar todos los clips de video requeridos
            for idx, clip_path in enumerate(clips_repetidos):
                clip_temp = os.path.join(temp_dir, f"{idx}.mp4")
                enlazar_o_copiar(os.path.abspath(clip_path), clip_temp)
                cmd.extend(["-i", f"temp_ffmpeg/{idx}.mp4"])
                
            # El audio y la música van después de los videos
            idx_audio = len(clips_repetidos)
            cmd.extend(["-i", "temp_ffmpeg/audio.mp3"])
            
            if tiene_musica:
                idx_musica = idx_audio + 1
                cmd.extend(["-stream_loop", "-1", "-i", "temp_ffmpeg/music.mp3"])
                
            # Preprocesar cada clip (fps, zoom, escala, duracion 5s)
            for i in range(len(clips_repetidos)):
                res = "720x1280" if orientacion == "vertical" else "1280x720"
                w, h = (720, 1280) if orientacion == "vertical" else (1280, 720)
                zoom_filter = f"zoompan=z='min(zoom+0.0015,1.3)':d=150:s={res}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                
                if i == 0:
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
        else:
            # Unir clips DIRECTAMENTE (Hard cuts, 10x más rápido)
            clips_necesarios = int(dur_audio / 5.0) + 1
            clips_necesarios = max(2, clips_necesarios)
            
            clips_repetidos = (clips * (int(clips_necesarios / len(clips)) + 1))[:clips_necesarios]
            print(f"📹 Se uniran {len(clips_repetidos)} clips directamente sin transiciones (duracion carrusel: {len(clips_repetidos)*5.0:.2f}s).")
            
            for idx, clip_path in enumerate(clips_repetidos):
                clip_temp = os.path.join(temp_dir, f"{idx}.mp4")
                enlazar_o_copiar(os.path.abspath(clip_path), clip_temp)
                cmd.extend(["-i", f"temp_ffmpeg/{idx}.mp4"])
                
            idx_audio = len(clips_repetidos)
            cmd.extend(["-i", "temp_ffmpeg/audio.mp3"])
            
            if tiene_musica:
                idx_musica = idx_audio + 1
                cmd.extend(["-stream_loop", "-1", "-i", "temp_ffmpeg/music.mp3"])
                
            for i in range(len(clips_repetidos)):
                w, h = (720, 1280) if orientacion == "vertical" else (1280, 720)
                filter_parts.append(f"[{i}:v]fps=30,scale={w}:{h}:flags=lanczos,trim=0:5,setpts=PTS-STARTPTS[v_scaled{i}]")
                
            concat_inputs = "".join(f"[v_scaled{i}]" for i in range(len(clips_repetidos)))
            filter_parts.append(f"{concat_inputs}concat=n={len(clips_repetidos)}:v=1:a=0[v_concatenated]")
            filter_parts.append(f"[v_concatenated]{subtitles_filter}[v_final]")
        
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
        cmd.extend(["-i", "temp_ffmpeg/audio.mp3"])
        
        idx_audio = 1
        if tiene_musica:
            idx_musica = 2
            cmd.extend(["-stream_loop", "-1", "-i", "temp_ffmpeg/music.mp3"])
            
        filter_parts.append(f"[0:v]{subtitles_filter}[v_final]")
        
        if tiene_musica:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[voz]; [{idx_musica}:a]volume={volumen_musica}[musica]; [voz][musica]amix=inputs=2:duration=first[a]")
        else:
            filter_parts.append(f"[{idx_audio}:a]volume=1.0[a]")
            
    # Escribir el script de filtros complejos en un archivo de texto para evitar exceder el límite de argumentos de Windows
    filter_script_path = os.path.join(temp_dir, "filter_complex.txt")
    with open(filter_script_path, "w", encoding="utf-8") as f:
        f.write("; \n".join(filter_parts))
        
    cmd.extend(["-filter_complex_script", "temp_ffmpeg/filter_complex.txt"])
    cmd.extend(["-map", "[v_final]", "-map", "[a]"])
            
    # Códecs de compresión compatibles con YouTube
    cmd.extend([
        "-c:v", "libx264", 
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", 
        "-b:a", "192k",
        "-shortest", # Detener el video cuando el audio (voz en off) termine
        "video_final.mp4"
    ])
    
    # Ejecución de FFmpeg dentro del directorio de salida para usar rutas relativas cortas
    print(f"🚀 Ejecutando comando FFmpeg con script de filtros...")
    try:
        proc = subprocess.Popen(
            cmd, 
            cwd=dir_salida, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.PIPE, 
            text=True, 
            bufsize=1, 
            encoding='utf-8'
        )
        
        patron_tiempo = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
        
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                match = patron_tiempo.search(line)
                if match and dur_audio > 0:
                    h, m, s, ms = map(int, match.groups())
                    segundos_procesados = h * 3600 + m * 60 + s + ms / 100.0
                    porcentaje = min(99.9, (segundos_procesados / dur_audio) * 100)
                    if callback_progreso:
                        callback_progreso(porcentaje)
                    print(f"⏳ Ensamblando: {porcentaje:.1f}% ({segundos_procesados:.1f}s / {dur_audio:.1f}s)", flush=True)
                    
        # Esperar a que termine y obtener errores de compilación si los hay
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            print(f"❌ Error en la compilación de FFmpeg:\n{stderr}")
            raise subprocess.CalledProcessError(proc.returncode, cmd, stderr=stderr)
            
        if callback_progreso:
            callback_progreso(100.0)
        print("🎉 ¡Video compilado con éxito!")
    finally:
        # Limpiar el directorio temporal
        shutil.rmtree(temp_dir, ignore_errors=True)

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
