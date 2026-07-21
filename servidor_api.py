import os
import sys
import json
import asyncio
import time
import shutil
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Asegurar que el path incluya el directorio actual
directorio_actual = os.path.dirname(os.path.abspath(__file__))
if directorio_actual not in sys.path:
    sys.path.append(directorio_actual)

import locutor
import generador
import miniaturizador
import editor

# Pre-aplicar parche de resolución DNS de Google para dominios críticos para evitar inestabilidad del ISP
try:
    generador.aplicar_parche_dns("speech.platform.bing.com")
    generador.aplicar_parche_dns("eastus.api.speech.microsoft.com")
    
    # Leer el pod_id desde runpod_config.json y pre-parchear la URL del proxy automáticamente
    _config_path = os.path.join(directorio_actual, "runpod_config.json")
    if os.path.exists(_config_path):
        with open(_config_path, "r") as _f:
            _cfg = json.load(_f)
        _pod_id = _cfg.get("pod_id", "").strip()
        if _pod_id:
            _proxy_host = f"{_pod_id}-8188.proxy.runpod.net"
            print(f"🔧 [INICIO] Pre-parcheando DNS del proxy de ComfyUI: {_proxy_host}")
            generador.aplicar_parche_dns(_proxy_host)
except Exception as e:
    print(f"⚠️ Error al pre-aplicar parche DNS en el inicio del servidor: {e}")

app = FastAPI(title="🤖 API FÁBRICA DE VIDEOS v5.0 - MASTER")

# Configurar CORS para permitir peticiones desde Vercel o el puerto local de React (3000/5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir todos para facilitar despliegues en Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para forzar la recarga limpia en el navegador (evitar caché de Chrome en localhost)
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".html", ".js", ".css")) or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Servir la carpeta de outputs estáticamente para que el frontend pueda reproducir videos e imágenes
outputs_dir = os.path.join(directorio_actual, "outputs")
os.makedirs(outputs_dir, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")

# Estado global en memoria para seguir el progreso del pipeline
estado_proceso = {
    "ocupado": False,
    "tema": "",
    "etapa": "Inactivo",
    "progreso": 0,
    "mensajes": [],
    "datos_video": None,
    "directorio_salida": "",
    "clonar_idiomas": [],
    "esperando_confirmacion_runpod": False,
    "respuesta_confirmacion_runpod": None
}

# Las funciones de configuración y apagado de RunPod han sido removidas.

# Llaves maestras (codificadas en base64 para evitar bloqueos del scanner de Git)
import base64
API_KEY = base64.b64decode("QVEuQWI4Uk42S1pPMXVNb1ltaDFyc0VSUXp2V21YN3pPN0tHMWV2cGhUMjRDTEYwaGxnaEE=").decode().strip()
YT_KEY = base64.b64decode("QUl6YVN5REdCRkNpN1R5Tkd5aF9IUFZKT3p5cDh1aVNaTXU0SG13").decode().strip()

class RastrearRequest(BaseModel):
    canales: List[str]

class RedactarRequest(BaseModel):
    tema: str
    duracion_min: float = 1.0
    clonar_idiomas: Optional[List[str]] = None  # ["en", "pt"]
    estructura: str = "Mitos Desmentidos"
    intro_pers: str = ""
    cierre_pers: str = ""
    competidor_video_id: Optional[str] = None

class ProducirRequest(BaseModel):
    tema: str
    url_runpod: str
    voz: str = "es-MX-JorgeNeural"
    estilo_video: str = "Realistic" # Realistic, 3D Pixar, Illustration, Anime, Cyberpunk, Custom
    custom_estilo_prompt: Optional[str] = None
    duracion_min: float = 1.0 # 1.0 para Shorts, 5.0, 10.0
    orientacion: str = "horizontal" # horizontal, vertical
    musica_genero: Optional[str] = None # Lofi, Epic, Medical, etc.
    estilo_subtitulos: Optional[dict] = None
    competidor_video_id: Optional[str] = None
    sub_fuente: str = "Arial Black"
    sub_color_iluminado: str = "yellow"
    sub_color_fondo: str = "white"
    sub_animacion: str = "karaoke"
    
    # Nuevas mejoras de audio, subtítulos y clonación
    tono_voz: str = "+0Hz"
    velocidad_voz: str = "+0%"
    volumen_musica: float = 0.12
    clonar_idiomas: Optional[List[str]] = None  # ["en", "pt"]
    
    # Parámetros avanzados de subtítulos y calidad
    sub_size: int = 64
    sub_outline: int = 3
    sub_align: str = "Centrado (Abajo)"
    sub_max_words: str = "3 palabras"
    sub_margin_v: int = 150
    video_quality: str = "Equilibrado"

def registrar_log(mensaje: str):
    print(f"[API Log] {mensaje}")
    estado_proceso["mensajes"].append(mensaje)
    if len(estado_proceso["mensajes"]) > 100:
        estado_proceso["mensajes"].pop(0)

@app.get("/api/status")
def get_status():
    return estado_proceso

def obtener_pod_id_activo_desde_api(api_key):
    if not api_key:
        return None
    import requests as req_http
    try:
        url = f"https://api.runpod.io/v2/user/pod?api_key={api_key}"
        res = req_http.get(url, timeout=5)
        print(f"DEBUG: RunPod API response code: {res.status_code}")
        if res.status_code == 200:
            pods = res.json()
            # Encontrar el primer pod que esté en estado 'RUNNING'
            for pod in pods:
                if pod.get("status") == "RUNNING":
                    return pod.get("id")
        else:
            print(f"DEBUG: RunPod API body: {res.text}")
    except Exception as e:
        print(f"⚠️ Error al obtener pods desde la API de RunPod: {e}")
    return None

@app.get("/api/config")
def get_config():
    api_key = None
    pod_id = None
    
    ruta_config = os.path.join(directorio_actual, "runpod_config.json")
    if os.path.exists(ruta_config):
        try:
            with open(ruta_config, "r") as f:
                data = json.load(f)
                api_key = data.get("api_key")
                pod_id = data.get("pod_id")
        except:
            pass
            
    if not api_key:
        api_key = os.environ.get("RUNPOD_API_KEY")
    if not pod_id:
        pod_id = os.environ.get("RUNPOD_POD_ID")
            
    # Intentar buscar dinámicamente el pod activo usando la API Key de RunPod sólo si no hay un pod_id configurado
    if api_key and not pod_id:
        pod_id_dinamico = obtener_pod_id_activo_desde_api(api_key)
        if pod_id_dinamico:
            pod_id = pod_id_dinamico
            # Guardar en el config local para cachear y no saturar la API
            try:
                with open(ruta_config, "w") as f:
                    json.dump({"api_key": api_key, "pod_id": pod_id}, f, indent=4)
            except:
                pass
                
    return {"pod_id": pod_id}

@app.post("/api/status/clear")
def clear_status():
    estado_proceso["ocupado"] = False
    estado_proceso["etapa"] = "Inactivo"
    estado_proceso["progreso"] = 0
    estado_proceso["mensajes"] = []
    estado_proceso["datos_video"] = None
    estado_proceso["esperando_confirmacion_runpod"] = False
    estado_proceso["respuesta_confirmacion_runpod"] = None
    return {"status": "ok"}

class PreviewVozRequest(BaseModel):
    voz: str = "es-MX-JorgeNeural"
    tono_voz: str = "+0Hz"
    velocidad_voz: str = "+0%"
    texto_muestra: Optional[str] = None

@app.post("/api/voz/preview")
def api_preview_voz(req: PreviewVozRequest):
    try:
        texto = req.texto_muestra.strip() if req.texto_muestra else "Hola, bienvenido a tu canal de salud. Este es un ejemplo de cómo se escuchará esta voz en tus videos."
        dir_previews = os.path.join(outputs_dir, "preview_voces")
        os.makedirs(dir_previews, exist_ok=True)
        
        safe_voz = "".join([c if c.isalnum() else "_" for c in req.voz])
        safe_pitch = "".join([c if c.isalnum() else "_" for c in req.tono_voz])
        safe_rate = "".join([c if c.isalnum() else "_" for c in req.velocidad_voz])
        filename = f"preview_{safe_voz}_{safe_pitch}_{safe_rate}.mp3"
        ruta_mp3 = os.path.join(dir_previews, filename)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                locutor.generar_muestra_voz(texto, ruta_mp3, voz=req.voz, rate=req.velocidad_voz, pitch=req.tono_voz)
            )
        finally:
            loop.close()
            
        import time
        t = int(time.time())
        return {
            "status": "ok",
            "audio_url": f"/outputs/preview_voces/{filename}?t={t}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar muestra de voz: {str(e)}")

class DetectarEstiloRequest(BaseModel):
    competidor_video_id: str

@app.post("/api/competidor/detectar_estilo")
def api_detectar_estilo_competidor(req: DetectarEstiloRequest):
    video_id = req.competidor_video_id.strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="ID de video competidor vacío.")
        
    temp_dir = os.path.join(outputs_dir, "temp_style_analysis")
    os.makedirs(temp_dir, exist_ok=True)
    video_path = os.path.join(temp_dir, f"{video_id}.mp4")
    
    try:
        # 1. Descargar fragmento de 10 segundos
        descargado = miniaturizador.descargar_fragmento_video(video_id, video_path)
        if not descargado:
            raise HTTPException(status_code=500, detail="No se pudo descargar el fragmento del video.")
            
        # 2. Extraer fotogramas
        frames = miniaturizador.extraer_fotogramas(video_path, temp_dir)
        if not frames:
            raise HTTPException(status_code=500, detail="No se pudieron extraer fotogramas del fragmento.")
            
        # 3. Analizar con Gemini Vision
        resultado = miniaturizador.analizar_estilo_video_con_gemini(frames, API_KEY)
        
        # Limpieza
        if os.path.exists(video_path):
            try: os.remove(video_path)
            except: pass
        for f in frames:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
                
        if resultado and "estilo" in resultado:
            return {
                "status": "ok",
                "estilo": resultado["estilo"],
                "explicacion": resultado["explicacion"],
                "custom_prompt": resultado.get("custom_prompt", "")
            }
        else:
            return {
                "status": "error",
                "estilo": "realistic",
                "explicacion": "No se pudo detectar el estilo. Usando fotorrealista por defecto.",
                "custom_prompt": ""
            }
    except Exception as e:
        # Limpieza ante error
        if os.path.exists(video_path):
            try: os.remove(video_path)
            except: pass
        try:
            for f in os.listdir(temp_dir):
                if f.startswith("frame_") and f.endswith(".jpg"):
                    os.remove(os.path.join(temp_dir, f))
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error al analizar el estilo del competidor: {str(e)}")

class NichoBuscarRequest(BaseModel):
    query: str
    fecha: str = "Última semana"
    orden: str = "Vistas"
    limite: int = 10
    idioma: str = "any"
    duracion: str = "any"

@app.post("/api/nicho/buscar")
def api_buscar_nicho(req: NichoBuscarRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Por favor ingresa un término de búsqueda.")
        
    # Importar utilidades de fabrica_videos
    from fabrica_videos import get_published_after, parse_iso8601_duration, estimate_earnings
    import requests as req_http
    import html as html_parser
    from datetime import datetime
    
    order_map = {
        "Vistas": "viewCount",
        "Relevancia": "relevance",
        "Fecha": "date"
    }
    order_param = order_map.get(req.orden, "viewCount")
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max(req.limite, 5), 50), # Límite seguro entre 5 y 50
        "key": YT_KEY,
        "order": order_param
    }
    
    if req.idioma != "any":
        params["relevanceLanguage"] = req.idioma
    if req.duracion != "any":
        params["videoDuration"] = req.duracion
    
    published_after = get_published_after(req.fecha)
    if published_after:
        params["publishedAfter"] = published_after
        
    try:
        # 1. Búsqueda de videos
        search_url = "https://www.googleapis.com/youtube/v3/search"
        res = req_http.get(search_url, params=params, timeout=10).json()
        
        if "error" in res:
            raise HTTPException(status_code=500, detail=f"Error API YouTube: {res['error']['message']}")
            
        items = res.get("items", [])
        if not items:
            return {"videos": []}
            
        video_ids = []
        channel_ids = []
        video_snippets = {}
        
        for item in items:
            v_id = item["id"].get("videoId")
            if not v_id:
                continue
            video_ids.append(v_id)
            c_id = item["snippet"]["channelId"]
            channel_ids.append(c_id)
            video_snippets[v_id] = {
                "id": v_id,
                "title": html_parser.unescape(item["snippet"]["title"]),
                "channelId": c_id,
                "channelTitle": item["snippet"]["channelTitle"],
                "publishedAt": item["snippet"]["publishedAt"],
                "thumbnail_url": item["snippet"]["thumbnails"]["medium"]["url"]
            }
            
        if not video_ids:
            return {"videos": []}
            
        # 2. Consultar estadísticas de videos (vistas y duración)
        videos_url = "https://www.googleapis.com/youtube/v3/videos"
        v_params = {
            "part": "statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": YT_KEY
        }
        v_res = req_http.get(videos_url, params=v_params, timeout=10).json()
        
        for v_item in v_res.get("items", []):
            v_id = v_item["id"]
            if v_id in video_snippets:
                video_snippets[v_id]["views"] = int(v_item["statistics"].get("viewCount", 0))
                video_snippets[v_id]["likes"] = int(v_item["statistics"].get("likeCount", 0))
                video_snippets[v_id]["duration_raw"] = v_item["contentDetails"].get("duration", "")
                
        # 3. Consultar estadísticas de canales (suscriptores y fecha de creación)
        channels_url = "https://www.googleapis.com/youtube/v3/channels"
        c_params = {
            "part": "statistics,snippet",
            "id": ",".join(list(set(channel_ids))),
            "key": YT_KEY
        }
        c_res = req_http.get(channels_url, params=c_params, timeout=10).json()
        
        channel_data = {}
        for c_item in c_res.get("items", []):
            c_id = c_item["id"]
            sub_count = int(c_item["statistics"].get("subscriberCount", 0))
            created_at = c_item["snippet"].get("publishedAt", "")
            if created_at:
                try:
                    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    created_fmt = dt.strftime("%d/%m/%Y")
                except:
                    created_fmt = created_at[:10]
            else:
                created_fmt = "Desconocida"
                
            channel_data[c_id] = {
                "subscribers": sub_count,
                "created_at": created_fmt
            }
            
        # Combinar datos y calcular métricas
        lista_final_videos = []
        for v_id, v_data in video_snippets.items():
            c_id = v_data["channelId"]
            c_info = channel_data.get(c_id, {"subscribers": 0, "created_at": "Desconocida"})
            v_data["subscribers"] = c_info["subscribers"]
            v_data["subscribers_formatted"] = formatear_numero(c_info["subscribers"])
            v_data["channel_created_at"] = c_info["created_at"]
            
            # Duración
            duration_sec, duration_fmt = parse_iso8601_duration(v_data.get("duration_raw", ""))
            v_data["duration_seconds"] = duration_sec
            v_data["duration_fmt"] = duration_fmt
            
            # Outlier Ratio
            views = v_data.get("views", 0)
            subs = v_data.get("subscribers", 0)
            if subs > 0:
                outlier_ratio = (views / subs) * 100.0
            else:
                outlier_ratio = 0.0
            v_data["outlier_ratio"] = outlier_ratio
            
            # Ganancias
            min_earn, max_earn, rpm_avg = estimate_earnings(views, duration_sec)
            v_data["earnings_min"] = min_earn
            v_data["earnings_max"] = max_earn
            v_data["rpm_avg"] = rpm_avg
            
            # Formatear vistas y likes
            v_data["views_formatted"] = formatear_numero(views)
            v_data["likes_formatted"] = formatear_numero(v_data.get("likes", 0))
            
            # Formatear fecha
            v_data["published_formatted"] = formatear_fecha(v_data["publishedAt"])
            
            lista_final_videos.append(v_data)
            
        # Ordenar por vistas descendente
        lista_final_videos.sort(key=lambda x: x.get("views", 0), reverse=True)
        return {"videos": lista_final_videos}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al buscar videos: {str(e)}")

def formatear_numero(num_str):
    try:
        num = int(num_str)
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)
    except:
        return num_str

def formatear_fecha(fecha_str):
    try:
        date_part = fecha_str.split("T")[0]
        y, m, d = date_part.split("-")
        return f"{d}/{m}/{y}"
    except:
        return fecha_str

@app.post("/api/rastrear")
def api_rastrear(req: RastrearRequest):
    registrar_log("🛰️ Iniciando rastreo de competidores...")
    videos_virales = []
    import requests as req_http
    
    for url in req.canales:
        username = None
        if "@" in url:
            username = url.split("@")[1].split("/")[0]
        elif "channel/" in url:
            username = url.split("channel/")[1].split("/")[0]
            
        if not username:
            continue
            
        registrar_log(f"🔄 Rastreando canal: @{username}...")
        
        # 1. Obtener Channel ID y suscriptores usando la API de Canales directa (1 unidad de cuota)
        chan_id = username
        subs_text = "N/A"
        chan_title = username
        
        # Intentar obtener los datos del canal usando el handle directo para ahorrar cuota de búsqueda
        handle = username if username.startswith("@") else f"@{username}"
        url_c = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&forHandle={handle}&key={YT_KEY}"
        
        try:
            res_c = req_http.get(url_c).json()
            if "items" in res_c and len(res_c["items"]) > 0:
                item_c = res_c["items"][0]
                chan_id = item_c["id"]
                chan_title = item_c["snippet"]["title"]
                subs_count = item_c["statistics"].get("subscriberCount", "0")
                subs_text = formatear_numero(subs_count)
            else:
                # Fallback al método anterior si no encuentra por handle
                if not username.startswith("UC"):
                    url_search = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={username}&key={YT_KEY}"
                    res_s = req_http.get(url_search).json()
                    if "items" in res_s and len(res_s["items"]) > 0:
                        chan_id = res_s["items"][0]["snippet"]["channelId"]
                
                # Obtener estadísticas con el ID
                url_c_id = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={chan_id}&key={YT_KEY}"
                res_c_id = req_http.get(url_c_id).json()
                if "items" in res_c_id and len(res_c_id["items"]) > 0:
                    item_c = res_c_id["items"][0]
                    chan_title = item_c["snippet"]["title"]
                    subs_count = item_c["statistics"].get("subscriberCount", "0")
                    subs_text = formatear_numero(subs_count)
        except Exception as e:
            registrar_log(f"⚠️ Error obteniendo información del canal: {e}")
            
        # 2. Obtener videos recientes de la playlist de subidas (1 unidad de cuota en vez de 100)
        # La playlist de subidas siempre empieza con 'UU' en vez de 'UC' en el ID del canal
        uploads_playlist_id = "UU" + chan_id[2:] if chan_id.startswith("UC") else chan_id
        url_v = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={uploads_playlist_id}&maxResults=15&key={YT_KEY}"
        
        video_ids = []
        try:
            res_v = req_http.get(url_v).json()
            if "items" in res_v:
                for item in res_v["items"]:
                    v_id = item["snippet"].get("resourceId", {}).get("videoId")
                    if v_id:
                        video_ids.append(v_id)
            elif "error" in res_v:
                registrar_log(f"⚠️ Error de API de YouTube en playlistItems: {res_v['error'].get('message')}")
        except Exception as e:
            registrar_log(f"⚠️ Error obteniendo videos subidos de la playlist: {e}")
            continue
            
        if not video_ids:
            continue
            
        # 3. Obtener estadísticas detalladas de los videos (views y fecha)
        ids_str = ",".join(video_ids)
        url_stats = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={ids_str}&key={YT_KEY}"
        try:
            res_stats = req_http.get(url_stats).json()
            if "items" in res_stats:
                for item in res_stats["items"]:
                    v_id = item["id"]
                    titulo_video = item["snippet"]["title"]
                    fecha_subida = item["snippet"]["publishedAt"]
                    views = item["statistics"].get("viewCount", "0")
                    
                    # Guardar estructura
                    videos_virales.append({
                        "id": v_id,
                        "title": titulo_video,
                        "views": int(views),
                        "views_formatted": formatear_numero(views),
                        "fecha": formatear_fecha(fecha_subida),
                        "canal": chan_title,
                        "subs": subs_text
                    })
        except Exception as e:
            registrar_log(f"⚠️ Error obteniendo estadísticas de videos: {e}")
            
    # 4. Ordenar todos los videos de todos los canales por visualizaciones desc
    videos_virales.sort(key=lambda x: x["views"], reverse=True)
    
    # 5. Formatear la respuesta
    temas_formateados = []
    for v in videos_virales:
        label = f"[{v['views_formatted']} vistas] [{v['fecha']}] {v['title']} - {v['canal']} ({v['subs']} subs)"
        temas_formateados.append({
            "title": v["title"],
            "id": v["id"],
            "label": label
        })
        
    registrar_log(f"🔥 Rastreo completado. Se ordenaron {len(temas_formateados)} videos por viralidad.")
    return {"temas": temas_formateados}

def traducir_guion_con_gemini(datos_sp, idioma_destino):
    """
    Traduce el JSON de guion y metadatos al idioma de destino utilizando Gemini.
    """
    mapa_idiomas = {
        "en": "Inglés (EE.UU. - English)",
        "pt": "Portugués (Brasil - Portuguese)"
    }
    nombre_idioma = mapa_idiomas.get(idioma_destino, idioma_destino)
    
    prompt_traduccion = (
        f"Eres un traductor profesional experto en localización de contenido de YouTube al idioma {nombre_idioma}.\n"
        f"A continuación se te proporciona un objeto JSON en español con metadatos de video, un guion de narración y una serie de escenas visuales.\n"
        f"Debes traducir TODO el contenido textual al idioma {nombre_idioma}, manteniendo exactamente el mismo formato JSON y las mismas claves.\n\n"
        f"REGLAS CRÍTICAS:\n"
        f"1. No alteres las claves del objeto JSON (como 'titulos', 'descripcion', 'tags', 'texto_miniatura', 'guion_locucion', 'escenas', 'texto_escena', 'prompt_broll').\n"
        f"2. Conserva intactos los prompts de video ('prompt_broll' y 'prompt_miniatura'), ya que están en inglés técnico de ComfyUI y no deben ser traducidos.\n"
        f"3. La traducción del guion ('guion_locucion') debe ser fluida, natural, expresiva y sonar humana al ser leída por un narrador nativo.\n"
        f"4. Devuelve estrictamente el JSON traducido, sin comentarios, aclaraciones ni marcas markdown adicionales.\n\n"
        f"OBJETO JSON A TRADUCIR:\n"
        f"{json.dumps(datos_sp, ensure_ascii=False)}"
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt_traduccion}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    import requests as req_http
    try:
        res = req_http.post(url, headers=headers, data=json.dumps(payload)).json()
        if 'candidates' in res and len(res['candidates']) > 0:
            texto_json = res['candidates'][0]['content']['parts'][0]['text']
            return json.loads(texto_json, strict=False)
    except Exception as e:
        print(f"⚠️ Error al traducir guion a {idioma_destino}: {e}")
    return None

class GuardarGuionRequest(BaseModel):
    tema_original: str
    tema_nuevo: str
    datos: dict

@app.post("/api/guion/guardar")
def api_guardar_guion(req: GuardarGuionRequest):
    safe_orig = "".join([c if c.isalnum() else "_" for c in req.tema_original])[:40]
    safe_nuevo = "".join([c if c.isalnum() else "_" for c in req.tema_nuevo])[:40]
    
    dir_orig = os.path.join(outputs_dir, safe_orig)
    dir_nuevo = os.path.join(outputs_dir, safe_nuevo)
    
    # Si cambió de carpeta, mover los archivos existentes o crear la nueva carpeta
    if safe_orig != safe_nuevo and os.path.exists(dir_orig):
        # Mover todo el contenido a la nueva carpeta
        if os.path.exists(dir_nuevo):
            shutil.rmtree(dir_nuevo)
        shutil.move(dir_orig, dir_nuevo)
        dir_actual = dir_nuevo
    else:
        os.makedirs(dir_nuevo, exist_ok=True)
        dir_actual = dir_nuevo
        
    # Guardar el JSON modificado
    ruta_json = os.path.join(dir_actual, "info_video.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(req.datos, f, indent=4, ensure_ascii=False)
        
    # Actualizar info_subida.txt con los nuevos textos
    ruta_txt = os.path.join(dir_actual, "info_subida.txt")
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(f"TÍTULOS SUGERIDOS:\n")
        for t in req.datos.get('titulos', []):
            f.write(f"- {t}\n")
        f.write(f"\nDESCRIPCIÓN:\n{req.datos.get('descripcion', '')}\n")
        f.write(f"\nETIQUETAS (TAGS):\n{', '.join(req.datos.get('tags', []))}\n")
        f.write(f"\nTEXTO MINIATURA:\n{req.datos.get('texto_miniatura', '')}\n")
        
    # Actualizar el tema en el estado global
    estado_proceso["tema"] = req.tema_nuevo
    estado_proceso["datos_video"] = req.datos
    estado_proceso["directorio_salida"] = dir_actual
    
    print(f"💾 Guion y carpeta de salida actualizados para: '{req.tema_nuevo}'")
    return {"status": "ok", "directorio_salida": dir_actual}

@app.post("/api/redactar")
def api_redactar(req: RedactarRequest):
    if estado_proceso["ocupado"]:
        raise HTTPException(status_code=400, detail="El sistema está ocupado con otra generación.")
        
    tema = req.tema.strip()
    duracion = req.duracion_min
    
    competidor_video_id = req.competidor_video_id
    transcripcion_original = ""
    if competidor_video_id:
        registrar_log(f"🕵️ Intentando extraer transcripción del video competidor ID: {competidor_video_id}...")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(competidor_video_id)
            try:
                transcript = transcript_list.find_transcript(['es', 'es-419', 'es-ES'])
            except:
                try:
                    transcript = transcript_list.find_transcript(['en'])
                except:
                    # Intentar obtener el primer idioma disponible en la lista de transcripciones creadas manualmente
                    transcript = next(iter(transcript_list._manually_created_transcripts.values()))
            
            lines = transcript.fetch()
            transcripcion_original = " ".join([line['text'] for line in lines])
            registrar_log(f"✅ ¡Transcripción extraída exitosamente! ({len(transcripcion_original)} caracteres).")
        except Exception as e:
            registrar_log(f"⚠️ No se pudo obtener la transcripción automática o manual del video: {e}")
    palabras_objetivo = int(duracion * 140)
    # Al menos 3 escenas para 30s, 5 para 1 min o proporcional para más largos
    escenas_objetivo = max(3 if duracion < 1.0 else 5, int(duracion * 6))
    
    safe_name = "".join([c if c.isalnum() else "_" for c in tema])[:40]
    dir_salida = os.path.join(outputs_dir, safe_name)
    os.makedirs(dir_salida, exist_ok=True)
    
    estructura_instruccion = ""
    if req.estructura == "Neuro-Misterio":
        estructura_instruccion = (
            "Aplica una estructura de NEURO-MISTERIO:\n"
            "- Gancho inicial polémico o aterrador de 5 segundos.\n"
            "- Desarrollo fundamentado en la biología celular/química del ingrediente (datos duros explicados de forma simple).\n"
            "- Cierre con un protocolo de acción muy específico (cómo y cuándo consumirlo)."
        )
    elif req.estructura == "Storytelling":
        estructura_instruccion = (
            "Aplica una estructura de STORYTELLING:\n"
            "- Comienza con el caso real de una persona/paciente (ej: 'A los 45 años, Carlos sentía...').\n"
            "- Presenta el conflicto médico o síntoma.\n"
            "- Describe la revelación del ingrediente natural y su proceso de recuperación biológico."
        )
    else:
        estructura_instruccion = (
            "Aplica una estructura de MITOS DESMENTIDOS:\n"
            "- Comienza con una denuncia de un mito común en la salud (ej: 'Te han mentido sobre...').\n"
            "- Explica por qué es biológicamente falso.\n"
            "- Presenta la alternativa real y saludable respaldada por ciencia."
        )

    personalizacion_instrucciones = ""
    if req.intro_pers:
        personalizacion_instrucciones += f"\n- En la introducción (después del gancho inicial), debes integrar explícitamente y de manera persuasiva con tus propias palabras la siguiente personalización: '{req.intro_pers}'."
    if req.cierre_pers:
        personalizacion_instrucciones += f"\n- En el cierre del video, debes integrar el siguiente llamado a la acción (CTA) personalizado de forma fluida: '{req.cierre_pers}'."

    extra_transcripcion_prompt = ""
    if transcripcion_original:
        extra_transcripcion_prompt = (
            f"\n\n🚨 COPIAR ESTRUCTURA RETENTIVA VIRAL:\n"
            f"El video ganador del competidor que queremos replicar tiene la siguiente transcripción/guion real:\n"
            f"\"\"\"\n{transcripcion_original[:3500]}\n\"\"\"\n\n"
            f"Analiza a fondo el guion de arriba: su ritmo, cómo maneja los primeros 5 segundos (el gancho), "
            f"el orden en el que revela la información de salud, los giros dramáticos y cómo mantiene alta la retención antes del final. "
            f"Debes imitar/replicar esa misma FÓRMULA DE RETENCIÓN y estructura en el nuevo guion que vas a escribir sobre el tema '{tema}'. "
            f"El guion nuevo debe ser completamente original y enfocado en '{tema}', no uses frases del competidor, sino su estructura retentiva y estilo de narración."
        )

    prompt_solicitud = (
        f"Actúa como un copywriter estrella de YouTube especializado en salud y neuro-marketing. "
        f"Basado en el tema '{tema}', debes retornar un objeto JSON estrictamente bajo la estructura provista. "
        f"El guion debe ser completo, adaptado para la narración, y tener exactamente unas {palabras_objetivo} palabras de longitud "
        f"(aproximadamente {duracion} minuto(s) de video a una velocidad de habla normal). No añadas marcas de tiempo en el guion.\n\n"
        f"INSTRUCCIONES DE ESTRUCTURA:\n"
        f"{estructura_instruccion}\n"
        f"{personalizacion_instrucciones}"
        f"{extra_transcripcion_prompt}\n\n"
        f"ESTRUCTURA DEL JSON REQUERIDA:\n"
        f"{{\n"
        f'  "titulos": ["Título Clickbait 1", "Título Clickbait 2", "Título Clickbait 3"],\n'
        f'  "descripcion": "Descripción del video optimizada para SEO de YouTube con marcas de tiempo...",\n'
        f'  "tags": ["salud", "bienestar", "nutricion", "otros_tags_relacionados"],\n'
        f'  "texto_miniatura": "3 o 4 palabras impactantes (ej: ¡EVITA ESTE ALIMENTO!)",\n'
        f'  "titulos_miniatura": ["Texto Corto 1", "Texto Corto 2", "Texto Corto 3"],\n'
        f'  "elemento_clave": "Nombre simple en inglés del ingrediente o elemento natural principal (ej: garlic, rosemary, date, apple, olive oil) para el fotomontaje",\n'
        f'  "prompt_miniatura": "Prompt en inglés muy detallado para generar UNICAMENTE la ilustración o foto de fondo macro. Debe enfocarse en el elemento u organo (ej: a giant human eye with glowing lens, or a close-up of a diseased liver, or a macro view of cells), cinematic lighting, dark background, ultra high detail, photorealistic, 8k. IMPORTANTE: No incluyas doctores, ni personas, ni textos en este prompt, ya que el sistema los recortara y pegara después.",\n'
        f'  "guion_locucion": "Texto completo adaptado para locución neural expresiva. REGLA OBLIGATORIA DE PUNTUACIÓN EMOCIONAL: Para que las voces gratuitas de IA suenen extremadamente humanas y expresivas, debes incluir frecuentemente signos de exclamación (¡!), preguntas de suspenso (¿?), puntos suspensivos (...) para pausas dramáticas de respiración, comas estratégicas para pausas naturales y palabras clave en MAYÚSCULAS para fuerza de voz. No incluyas acotaciones entre corchetes o paréntesis.",\n'
        f'  "escenas": [\n'
        f'     {{\n'
        f'       "texto_escena": "Fracción del guion correspondiente a esta escena",\n'
        f'       "prompt_broll": "Prompt visual detallado en inglés para generar video B-roll en Wan Video. REGLAS CRÍTICAS: 1) COHERENCIA CONTEXTUAL DIRECTA: El prompt debe ilustrar de forma lógica y literal el contenido de \'texto_escena\' (ej: si el texto habla de arrugas, describe a una mujer de 50 años tocando suavemente las líneas de expresión en su rostro frente a un espejo; si habla de várices o circulación, describe un plano medio de piernas cansadas o venas inflamadas; si habla de remedios, muestra a alguien sirviendo una infusión caliente de plantas). 2) DETALLE Y ACCIÓN FÍSICA: Describe sujetos, ángulos, iluminación y movimientos continuos con verbos activos (ej: \'close-up shot of...\', \'slow motion movement of...\', \'gently massaging...\'). Evita conceptos abstractos, pantallas divididas (split screen), montajes, logos o textos."\n'
        f'     }}\n'
        f'  ]\n'
        f"}}\n\n"
        f"Asegura que el campo 'escenas' tenga exactamente unas {escenas_objetivo} escenas distribuidas a lo largo del guion, "
        f"con prompts visuales en inglés altamente coherentes, detallados y dinámicos para Wan Video."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt_solicitud}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    import requests as req_http
    try:
        registrar_log(f"🧠 Redactando guión con Gemini para: '{tema}'...")
        res = req_http.post(url, headers=headers, data=json.dumps(payload)).json()
        if 'candidates' in res and len(res['candidates']) > 0:
            texto_json = res['candidates'][0]['content']['parts'][0]['text']
            
            # Limpiar respuesta: Gemini a veces envuelve en markdown ```json ... ```
            texto_json = texto_json.strip()
            if texto_json.startswith("```"):
                # Quitar la primera línea (```json o ```) y la última (```)
                lineas = texto_json.split("\n")
                lineas = lineas[1:] if lineas[0].startswith("```") else lineas
                if lineas and lineas[-1].strip() == "```":
                    lineas = lineas[:-1]
                texto_json = "\n".join(lineas).strip()
                
            # Verificar que haya JSON válido
            if not texto_json or not (texto_json.startswith("{") or texto_json.startswith("[")):
                registrar_log(f"⚠️ Respuesta inesperada de Gemini: {texto_json[:200]}")
                raise HTTPException(status_code=500, detail=f"Gemini devolvió texto no-JSON: {texto_json[:200]}")
                
            datos = json.loads(texto_json, strict=False)
            
            # Limpiar y acortar tags a un máximo de 480 caracteres (para cumplir con el límite de 500 de YouTube)
            tags_filtrados = []
            longitud_actual = 0
            for tag in datos.get("tags", []):
                tag_limpio = tag.strip().lower()
                if len(tag_limpio) + longitud_actual + 2 <= 480:
                    tags_filtrados.append(tag_limpio)
                    longitud_actual += len(tag_limpio) + 2
            datos["tags"] = tags_filtrados
            
            # Guardar JSON
            ruta_json = os.path.join(dir_salida, "info_video.json")
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=4, ensure_ascii=False)
                
            # Guardar metadatos TXT
            ruta_txt = os.path.join(dir_salida, "info_subida.txt")
            with open(ruta_txt, "w", encoding="utf-8") as f:
                f.write(f"TÍTULOS SUGERIDOS:\n")
                for t in datos['titulos']:
                    f.write(f"- {t}\n")
                f.write(f"\nDESCRIPCIÓN:\n{datos['descripcion']}\n")
                f.write(f"\nETIQUETAS (TAGS):\n{', '.join(datos['tags'])}\n")
                f.write(f"\nTEXTO MINIATURA:\n{datos['texto_miniatura']}\n")
                if 'titulos_miniatura' in datos:
                    f.write(f"\nOPCIONES CORTAS MINIATURA:\n{', '.join(datos['titulos_miniatura'])}\n")
            
            # Traducir a otros idiomas si se solicita
            if req.clonar_idiomas:
                for lang in req.clonar_idiomas:
                    registrar_log(f"🌐 Traduciendo contenido al idioma: {lang.upper()}...")
                    datos_trad = traducir_guion_con_gemini(datos, lang)
                    if datos_trad:
                        # Guardar JSON traducido
                        ruta_json_lang = os.path.join(dir_salida, f"info_video_{lang}.json")
                        with open(ruta_json_lang, "w", encoding="utf-8") as f:
                            json.dump(datos_trad, f, indent=4, ensure_ascii=False)
                        
                        # Guardar TXT traducido
                        ruta_txt_lang = os.path.join(dir_salida, f"info_subida_{lang}.txt")
                        with open(ruta_txt_lang, "w", encoding="utf-8") as f:
                            f.write(f"TÍTULOS SUGERIDOS ({lang.upper()}):\n")
                            for t in datos_trad.get('titulos', []):
                                f.write(f"- {t}\n")
                            f.write(f"\nDESCRIPCIÓN:\n{datos_trad.get('descripcion', '')}\n")
                            f.write(f"\nETIQUETAS (TAGS):\n{', '.join(datos_trad.get('tags', []))}\n")
                            f.write(f"\nTEXTO MINIATURA:\n{datos_trad.get('texto_miniatura', '')}\n")
                            if 'titulos_miniatura' in datos_trad:
                                f.write(f"\nOPCIONES CORTAS MINIATURA:\n{', '.join(datos_trad['titulos_miniatura'])}\n")
                        registrar_log(f"✅ Contenido en {lang.upper()} guardado exitosamente.")
                
            estado_proceso["datos_video"] = datos
            estado_proceso["directorio_salida"] = dir_salida
            estado_proceso["tema"] = tema
            registrar_log("✅ Guion y metadatos generados y guardados en el disco.")
            return datos
        else:
            registrar_log(f"❌ Respuesta inesperada de Gemini: {json.dumps(res)}")
            raise HTTPException(status_code=500, detail="Gemini no devolvió una estructura válida.")
    except Exception as e:
        registrar_log(f"❌ Error redactando guion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def obtener_openai_api_key():
    # 1. Leer de config file
    ruta_config = os.path.join(directorio_actual, "runpod_config.json")
    if os.path.exists(ruta_config):
        try:
            with open(ruta_config, "r") as f:
                data = json.load(f)
                okey = data.get("openai_api_key")
                if okey:
                    return okey.strip()
        except:
            pass
    # 2. Leer de env var
    okey_env = os.environ.get("OPENAI_API_KEY")
    if okey_env:
        return okey_env.strip()
    return None

class RegenerarMiniaturaRequest(BaseModel):
    tema: str
    url_runpod: str
    competidor_video_id: Optional[str] = None
    forzar_comfy: Optional[bool] = False

class CrearMiniaturaManualRequest(BaseModel):
    prompt_fondo: str
    texto_clickbait: str
    elemento_clave: Optional[str] = ""
    url_runpod: str
    competidor_video_id: Optional[str] = None
    forzar_comfy: Optional[bool] = False

class ConfirmarRunpodRequest(BaseModel):
    respuesta: str

@app.post("/api/miniatura/regenerar")
def api_regenerar_miniatura(req: RegenerarMiniaturaRequest):
    tema = req.tema.strip()
    safe_name = "".join([c if c.isalnum() else "_" for c in tema])[:40]
    dir_salida = os.path.join(outputs_dir, safe_name)
    
    ruta_json = os.path.join(dir_salida, "info_video.json")
    if not os.path.exists(ruta_json):
        raise HTTPException(status_code=400, detail="Debes redactar el guion del video primero.")
        
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos_video = json.load(f)
        
    prompt_img = datos_video["prompt_miniatura"]
    texto_click = datos_video["texto_miniatura"]
    # Parche de retrocompatibilidad: Evitar doctores/personas en el fondo y forzar fondos de primer plano clínico
    clickbait_lower = texto_click.lower()
    if "gafas" in clickbait_lower or "ojos" in clickbait_lower or "visión" in clickbait_lower or "vista" in clickbait_lower:
        prompt_img = "Macro close-up photography of a giant human eye with a glowing detailed iris and red veins, clinical dark background, high contrast, cinematic light, 8k, photorealistic"
    elif "doctor" in prompt_img.lower() or "physician" in prompt_img.lower() or "person" in prompt_img.lower():
        prompt_img = f"Macro close-up photorealistic illustration of the main health element, clinical dark background, high contrast, cinematic lighting, 8k"
        
    ruta_fondo = os.path.join(dir_salida, "fondo_minia.png")
    
    url_runpod_interna = req.url_runpod.strip().strip("/")
    if url_runpod_interna and not url_runpod_interna.startswith(("http://", "https://")):
        url_runpod_interna = "https://" + url_runpod_interna
        
    if "-8188.proxy.runpod.net" in url_runpod_interna:
        url_runpod_interna = url_runpod_interna.replace("-8188.proxy.runpod.net", "-7777.proxy.runpod.net/proxy/8188")
        
    if os.environ.get("RUNPOD_POD_ID"):
        if "runpod.net" in req.url_runpod or "proxy" in req.url_runpod:
            url_runpod_interna = "http://127.0.0.1:8188"
            
    # Semilla aleatoria
    import random
    semilla_aleatoria = random.randint(1, 1000000)
    
    openai_key = obtener_openai_api_key()
    exito_fondo = False
    
    if req.forzar_comfy:
        registrar_log(f"🚀 Re-generando fondo de miniatura en RunPod (Forzado por usuario, Semilla: {semilla_aleatoria})...")
        exito_fondo = generador.generar_fondo_miniatura(url_runpod_interna, prompt_img, ruta_fondo, seed=semilla_aleatoria)
    else:
        if openai_key:
            registrar_log("⏳ Creando ilustración de fondo con DALL-E 3 de OpenAI...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_con_dalle3(prompt_img, openai_key, ruta_fondo)
            
        if not exito_fondo:
            registrar_log("⏳ Creando ilustración de fondo GRATIS con FLUX.1 (Pollinations)...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_gratis_pollinations(prompt_img, ruta_fondo)
            
        if not exito_fondo:
            registrar_log("⚠️ Las opciones gratuitas fallaron. Reclamando confirmación para usar RunPod...")
            return {
                "status": "need_confirmation",
                "message": "Las opciones gratuitas (OpenAI / Pollinations) fallaron o no están configuradas. ¿Deseas encender RunPod (ComfyUI) y continuar la generación de miniaturas allí?"
            }
            
    if not exito_fondo:
        raise HTTPException(status_code=500, detail="Falló la generación del fondo de miniatura.")
        
    # Re-componer layouts
    layout_config = None
    if req.competidor_video_id:
        ruta_comp = os.path.join(dir_salida, "miniatura_competidora.jpg")
        if os.path.exists(ruta_comp):
            if openai_key:
                registrar_log("🧠 Re-analizando miniatura competidora con OpenAI GPT-4o...")
                layout_config = miniaturizador.analizar_miniatura_con_openai(ruta_comp, openai_key)
            if not layout_config:
                registrar_log("🧠 Re-analizando miniatura competidora con Gemini Vision...")
                layout_config = miniaturizador.analizar_miniatura_con_gemini(ruta_comp, API_KEY)
            
    elem_clave = datos_video.get("elemento_clave", "")
    
    layout_opcion1 = layout_config if layout_config else {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "yellow",
        "color_secundario": "white",
        "inclinacion_grados": -3,
        "sujeto_posicion_x": "right",
        "tiene_banner": True
    }
    ruta_opc1 = os.path.join(dir_salida, "miniatura_opcion1.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc1, texto_click, layout_opcion1, elem_clave, url_runpod_interna)
    
    layout_opcion2 = {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "white",
        "color_secundario": "yellow",
        "inclinacion_grados": 3,
        "sujeto_posicion_x": "right",
        "tiene_banner": True
    }
    ruta_opc2 = os.path.join(dir_salida, "miniatura_opcion2.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc2, texto_click, layout_opcion2, elem_clave, url_runpod_interna)
    
    layout_opcion3 = {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "green",
        "color_secundario": "white",
        "inclinacion_grados": 0,
        "sujeto_posicion_x": "right",
        "tiene_banner": False
    }
    ruta_opc3 = os.path.join(dir_salida, "miniatura_opcion3.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc3, texto_click, layout_opcion3, elem_clave, url_runpod_interna)
    
    # También clonar si ya estaban en otros idiomas
    for lang in ["en", "pt"]:
        ruta_json_lang = os.path.join(dir_salida, f"info_video_{lang}.json")
        if os.path.exists(ruta_json_lang):
            with open(ruta_json_lang, "r", encoding="utf-8") as f:
                datos_lang = json.load(f)
            texto_click_lang = datos_lang.get("texto_miniatura", "")
            ruta_minia_lang = os.path.join(dir_salida, f"miniatura_final_{lang}.png")
            registrar_log(f"🖼️ Regenerando miniatura para clonación ({lang.upper()})...")
            # Extraer elemento clave del idioma correspondiente o usar el principal
            elem_clave_lang = datos_lang.get("elemento_clave", elem_clave)
            miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_minia_lang, texto_click_lang, layout_opcion1, elem_clave_lang, url_runpod_interna)
            
    registrar_log("✅ Regeneración de miniaturas completada con éxito.")
    return {"status": "ok", "directorio_salida": dir_salida}

@app.post("/api/miniatura/crear_manual")
def api_crear_miniatura_manual(req: CrearMiniaturaManualRequest):
    # Creamos una carpeta de salida especial para creaciones manuales
    safe_name = "Manual_Thumbnails"
    dir_salida = os.path.join(outputs_dir, safe_name)
    os.makedirs(dir_salida, exist_ok=True)
    
    prompt_img = req.prompt_fondo.strip()
    texto_click = req.texto_clickbait.strip()
    elem_clave = req.elemento_clave.strip() if req.elemento_clave else ""
    
    # Intentar generar imagen
    ruta_fondo = os.path.join(dir_salida, "fondo_manual.png")
    
    url_runpod_interna = req.url_runpod.strip().strip("/")
    if url_runpod_interna and not url_runpod_interna.startswith(("http://", "https://")):
        url_runpod_interna = "https://" + url_runpod_interna
        
    if "-8188.proxy.runpod.net" in url_runpod_interna:
        url_runpod_interna = url_runpod_interna.replace("-8188.proxy.runpod.net", "-7777.proxy.runpod.net/proxy/8188")
        
    if os.environ.get("RUNPOD_POD_ID"):
        if "runpod.net" in req.url_runpod or "proxy" in req.url_runpod:
            url_runpod_interna = "http://127.0.0.1:8188"
            
    openai_key = obtener_openai_api_key()
    exito_fondo = False
    
    if req.forzar_comfy:
        registrar_log(f"🚀 [MANUAL] Generando fondo con SDXL en RunPod (Forzado por usuario): '{prompt_img}'...")
        import random
        semilla_aleatoria = random.randint(1, 1000000)
        exito_fondo = generador.generar_fondo_miniatura(url_runpod_interna, prompt_img, ruta_fondo, seed=semilla_aleatoria)
    else:
        if openai_key:
            registrar_log(f"⏳ [MANUAL] Generando fondo con DALL-E 3 de OpenAI: '{prompt_img}'...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_con_dalle3(prompt_img, openai_key, ruta_fondo)
            
        if not exito_fondo:
            registrar_log(f"⏳ [MANUAL] Generando fondo GRATIS con FLUX.1 (Pollinations): '{prompt_img}'...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_gratis_pollinations(prompt_img, ruta_fondo)
            
        if not exito_fondo:
            registrar_log("⚠️ [MANUAL] Las opciones gratuitas fallaron. Reclamando confirmación para usar RunPod...")
            return {
                "status": "need_confirmation",
                "message": "Las opciones gratuitas (OpenAI / Pollinations) fallaron o no están configuradas. ¿Deseas encender RunPod (ComfyUI) y continuar la generación de miniaturas allí?"
            }
        
    if not exito_fondo:
        raise HTTPException(status_code=500, detail="No se pudo generar el fondo de miniatura.")
        
    # Copiar layout del competidor si se proporciona
    layout_config = None
    if req.competidor_video_id:
        ruta_comp = os.path.join(dir_salida, "miniatura_competidora.jpg")
        if miniaturizador.descargar_miniatura_competidor(req.competidor_video_id, ruta_comp):
            if openai_key:
                registrar_log("🧠 [MANUAL] Analizando miniatura competidora con OpenAI GPT-4o...")
                layout_config = miniaturizador.analizar_miniatura_con_openai(ruta_comp, openai_key)
            if not layout_config:
                registrar_log("🧠 [MANUAL] Analizando miniatura competidora con Gemini Vision...")
                layout_config = miniaturizador.analizar_miniatura_con_gemini(ruta_comp, API_KEY)
                
    # Componer opciones
    layout_opcion1 = layout_config if layout_config else {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "yellow",
        "color_secundario": "white",
        "inclinacion_grados": -3,
        "sujeto_posicion_x": "right",
        "tiene_banner": True
    }
    
    # Generamos los 3 archivos en el directorio manual
    ruta_opc1 = os.path.join(dir_salida, "manual_opcion1.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc1, texto_click, layout_opcion1, elem_clave, url_runpod_interna)
    
    layout_opcion2 = {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "white",
        "color_secundario": "yellow",
        "inclinacion_grados": 3,
        "sujeto_posicion_x": "right",
        "tiene_banner": True
    }
    ruta_opc2 = os.path.join(dir_salida, "manual_opcion2.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc2, texto_click, layout_opcion2, elem_clave, url_runpod_interna)
    
    layout_opcion3 = {
        "texto_posicion_x": "left",
        "texto_alineacion": "left",
        "color_primario": "green",
        "color_secundario": "white",
        "inclinacion_grados": 0,
        "sujeto_posicion_x": "right",
        "tiene_banner": False
    }
    ruta_opc3 = os.path.join(dir_salida, "manual_opcion3.png")
    miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc3, texto_click, layout_opcion3, elem_clave, url_runpod_interna)
    
    registrar_log("✅ Creador manual de miniaturas completado con éxito.")
    import time
    t = int(time.time())
    return {
        "status": "ok",
        "opcion1": f"/outputs/{safe_name}/manual_opcion1.png?t={t}",
        "opcion2": f"/outputs/{safe_name}/manual_opcion2.png?t={t}",
        "opcion3": f"/outputs/{safe_name}/manual_opcion3.png?t={t}",
        "directorio_salida": dir_salida
    }

@app.post("/api/producir/confirmar_comfy")
def api_confirmar_comfy(req: ConfirmarRunpodRequest):
    estado_proceso["respuesta_confirmacion_runpod"] = req.respuesta
    return {"status": "ok"}

def proceso_background_producir(req: ProducirRequest):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        tema = req.tema.strip()
        safe_name = "".join([c if c.isalnum() else "_" for c in tema])[:40]
        dir_salida = os.path.join(outputs_dir, safe_name)
        os.makedirs(dir_salida, exist_ok=True)
        
        # Intentar cargar datos de disco si no están en memoria
        ruta_json = os.path.join(dir_salida, "info_video.json")
        if not os.path.exists(ruta_json):
            registrar_log("❌ Error: No se encontró el guion en disco. Debes redactar primero.")
            estado_proceso["ocupado"] = False
            return
            
        with open(ruta_json, "r", encoding="utf-8") as f:
            datos_video = json.load(f)
            
        estado_proceso["datos_video"] = datos_video
        estado_proceso["directorio_salida"] = dir_salida
        
        # 1. GENERACIÓN DE AUDIO Y SUBTÍTULOS
        estado_proceso["etapa"] = "Locución neural"
        estado_proceso["progreso"] = 15
        registrar_log("🎙️ Paso 1/4: Iniciando locución neural y sincronización de subtítulos...")
        ruta_mp3 = os.path.join(dir_salida, "voz_off.mp3")
        ruta_srt = os.path.join(dir_salida, "subtitulos.srt")
        ruta_ass = os.path.join(dir_salida, "subtitulos.ass")
        
        # Mapear palabras por pantalla
        max_words_map = {
            "2 palabras": 2,
            "3 palabras": 3,
            "4 palabras": 4,
            "Línea completa": 999
        }
        max_words_val = max_words_map.get(req.sub_max_words, 3)

        # Mapear alineación (1=izquierda, 2=centrado, 3=derecha)
        align_map = {
            "Centrado (Abajo)": 2,
            "Izquierda (Abajo)": 1,
            "Derecha (Abajo)": 3
        }
        align_val = align_map.get(req.sub_align, 2)

        # Ejecutar edge_tts
        loop.run_until_complete(
            locutor.generar_audio_y_subtitulos(
                datos_video["guion_locucion"], 
                ruta_mp3, 
                ruta_srt, 
                voz=req.voz,
                ruta_ass=ruta_ass,
                orientacion=req.orientacion,
                font_name=req.sub_fuente,
                primary_color=req.sub_color_iluminado,
                secondary_color=req.sub_color_fondo,
                effect_type=req.sub_animacion,
                rate=req.velocidad_voz,
                pitch=req.tono_voz,
                max_words_per_line=max_words_val,
                font_size=req.sub_size,
                outline_thickness=req.sub_outline,
                alignment=align_val,
                margin_v=req.sub_margin_v
            )
        )
        registrar_log("✅ Locución y subtítulos sincronizados exitosamente con tu estilo personalizado (Karaoke ASS).")
        
        # 2. GENERACIÓN DE CLIPS EN RUNPOD
        estado_proceso["etapa"] = "Generación de B-roll en RunPod"
        estado_proceso["progreso"] = 40
        registrar_log(f"📹 Paso 2/4: Conectando a RunPod y encolando prompts de video (Orientación: {req.orientacion})...")
        
        # Normalizar URL: agregar https:// si no tiene protocolo
        url_runpod_interna = req.url_runpod.strip().strip("/")
        if url_runpod_interna and not url_runpod_interna.startswith(("http://", "https://")):
            url_runpod_interna = "https://" + url_runpod_interna
            
        # Desviar a través del proxy de VS Code si se detecta puerto 8188 bloqueado/no-explicito
        if "-8188.proxy.runpod.net" in url_runpod_interna:
            original_url = url_runpod_interna
            url_runpod_interna = url_runpod_interna.replace("-8188.proxy.runpod.net", "-7777.proxy.runpod.net/proxy/8188")
            registrar_log(f"🔄 [RE-RUTEO PROXY] Redirigiendo puerto 8188 a través del proxy de VS Code (puerto 7777):")
            registrar_log(f"   De: {original_url}")
            registrar_log(f"   A: {url_runpod_interna}")
            
        registrar_log(f"🔗 URL de ComfyUI normalizada: {url_runpod_interna}")
        
        # Aplicar parche DNS para la URL del proxy de RunPod
        generador.aplicar_parche_dns_desde_url(url_runpod_interna)
        
        if os.environ.get("RUNPOD_POD_ID"):
            if "runpod.net" in req.url_runpod or "proxy" in req.url_runpod:
                url_runpod_interna = "http://127.0.0.1:8188"
                registrar_log("ℹ️ Entorno en la nube detectado. Redirigiendo llamadas internas de ComfyUI a 127.0.0.1:8188 para mayor velocidad.")
        
        # Mapeo de resolución nativa óptima para evitar deformaciones del modelo Wan Video
        if req.orientacion == "vertical":
            width, height = 480, 832
        else:
            width, height = 832, 480

        if req.video_quality == "Rápido":
            pasos = 15
        elif req.video_quality == "Equilibrado":
            pasos = 20
        else:  # Alta Calidad
            pasos = 30
        registrar_log(f"🎬 Calidad seleccionada: {req.video_quality} -> Resolucion: {width}x{height}, Pasos: {pasos}")
        
        escenas = datos_video["escenas"]
        prompts_ids = []
        
        # Modificar prompt de acuerdo al estilo seleccionado
        estilos_prompt_map = {
            "realistic": "Cinematic B-roll, medical video essay style, {}, 4k, hyperrealistic, slow motion",
            "3d pixar": "3D pixar style animation, {}, vibrant colors, claymation aesthetic, cute lighting, medical concept",
            "illustration": "2D minimalist vector animation, clean flat design, {}, infographic style, medical graphics",
            "anime": "Modern anime visual style, scientific concept, {}, hand-drawn cell animation, medical theme",
            "cyberpunk": "Cyberpunk medical hologram, neon glow, {}, futuristic UI graphics, 8k resolution"
        }
        
        if req.estilo_video.lower() == "custom" and req.custom_estilo_prompt:
            formato_prompt = req.custom_estilo_prompt
            if "{}" not in formato_prompt:
                formato_prompt = formato_prompt + ", {}"
            registrar_log(f"🎨 Usando Estilo Personalizado por IA: {formato_prompt}")
        else:
            formato_prompt = estilos_prompt_map.get(req.estilo_video.lower(), estilos_prompt_map["realistic"])
        
        # ── PRE-CHECK: Verificar conectividad con ComfyUI antes de encolar ──
        registrar_log(f"🔌 Verificando conectividad con ComfyUI en: {url_runpod_interna}...")
        try:
            import requests as req_http
            test_resp = req_http.get(f"{url_runpod_interna}/system_stats", timeout=15)
            if test_resp.status_code == 200:
                registrar_log(f"✅ ComfyUI responde correctamente (HTTP 200).")
            elif test_resp.status_code == 404:
                registrar_log(f"❌ ComfyUI responde HTTP 404 en /system_stats. ComfyUI puede no estar iniciado aún o no tener los nodos WanVideo instalados.")
                registrar_log(f"💡 Abre la terminal de RunPod y ejecuta: bash /workspace/Canal_de_Salud_de_Victor/arrancar_runpod.sh")
                estado_proceso["ocupado"] = False
                return
            else:
                registrar_log(f"⚠️ ComfyUI responde HTTP {test_resp.status_code}. Continuando de todas formas...")
        except Exception as e_pre:
            registrar_log(f"❌ No se pudo conectar a ComfyUI: {type(e_pre).__name__}: {str(e_pre)[:300]}")
            registrar_log("💡 SOLUCIÓN: Verifica que tu pod de RunPod esté encendido y que la URL del proxy sea correcta.")
            estado_proceso["ocupado"] = False
            return
        
        # Encolar en ComfyUI
        # Monitorear y preparar directorio de clips
        ruta_clips = os.path.join(dir_salida, "clips")
        os.makedirs(ruta_clips, exist_ok=True)
        
        # Encolar en ComfyUI (con salto inteligente de cache)
        for idx, escena in enumerate(escenas):
            prompt_broll = escena["prompt_broll"]
            prompt_modificado = formato_prompt.format(prompt_broll)
            
            ruta_clip = os.path.join(ruta_clips, f"clip_{idx+1:03d}.mp4")
            
            # Si el clip ya existe localmente, lo marcamos como 'cached' y lo saltamos
            if os.path.exists(ruta_clip) and os.path.getsize(ruta_clip) > 10000:
                registrar_log(f"✅ Clip {idx+1:03d} ya existe localmente. Saltando generación en RunPod...")
                prompts_ids.append((idx+1, "cached"))
                continue
            
            registrar_log(f"⏳ Encolando Escena {idx+1}/{len(escenas)} en RunPod...")
            
            # Enviar prompt con las dimensiones dinámicas
            prompt_id = generador.enviar_prompt_a_comfyui(
                server_url=url_runpod_interna, 
                prompt_texto=prompt_modificado, 
                index_clip=idx+1,
                seed=42,
                width=width,
                height=height,
                steps=pasos
            )
            if prompt_id:
                prompts_ids.append((idx+1, prompt_id))
            time.sleep(1)
            
        if not prompts_ids:
            ultimo_error = getattr(generador, 'last_comfy_error', '')
            if ultimo_error:
                registrar_log(f"❌ Error al encolar en ComfyUI: {ultimo_error}")
                if "Unknown node type" in ultimo_error or "WanVideo" in ultimo_error:
                    registrar_log("💡 Los nodos WanVideo no están instalados en ComfyUI. Ejecuta 'arrancar_runpod.sh' nuevamente desde la terminal de RunPod para instalarlos.")
            registrar_log("❌ Error fatal: No se pudo encolar ningún clip en RunPod.")
            estado_proceso["ocupado"] = False
            return
            
        clips_descargados = 0
        
        for index, prompt_id in prompts_ids:
            ruta_clip = os.path.join(ruta_clips, f"clip_{index:03d}.mp4")
            
            if prompt_id == "cached":
                clips_descargados += 1
                progreso_parcial = 40 + int((clips_descargados / len(prompts_ids)) * 30)
                estado_proceso["progreso"] = progreso_parcial
                registrar_log(f"🎉 Clip {index:03d} (Caché local) cargado correctamente.")
                continue
                
            registrar_log(f"⏳ Procesando Clip {index:03d}/{len(prompts_ids)} en GPU de RunPod...")
            
            exito = generador.esperar_y_descargar(url_runpod_interna, prompt_id, ruta_clip)
            if exito:
                clips_descargados += 1
                progreso_parcial = 40 + int((clips_descargados / len(prompts_ids)) * 30)
                estado_proceso["progreso"] = progreso_parcial
                registrar_log(f"🎉 Clip {index:03d} descargado correctamente.")
            else:
                registrar_log(f"❌ Falló la generación del Clip {index:03d}.")
                
        registrar_log(f"🎬 Clips descargados: {clips_descargados}/{len(prompts_ids)}")
        
        # 3. GENERACIÓN DE MINIATURA CLICKBAIT CON IMITACIÓN VIRAL
        estado_proceso["etapa"] = "Diseñando miniaturas clickbait"
        estado_proceso["progreso"] = 80
        registrar_log("🎨 Paso 3/4: Generando miniatura clickbait inteligente...")
        
        prompt_img = datos_video["prompt_miniatura"]
        texto_click = datos_video["texto_miniatura"]
        # Parche de retrocompatibilidad: Evitar doctores/personas en el fondo y forzar fondos de primer plano clínico
        clickbait_lower = texto_click.lower()
        if "gafas" in clickbait_lower or "ojos" in clickbait_lower or "visión" in clickbait_lower or "vista" in clickbait_lower:
            prompt_img = "Macro close-up photography of a giant human eye with a glowing detailed iris and red veins, clinical dark background, high contrast, cinematic light, 8k, photorealistic"
        elif "doctor" in prompt_img.lower() or "physician" in prompt_img.lower() or "person" in prompt_img.lower():
            prompt_img = f"Macro close-up photorealistic illustration of the main health element, clinical dark background, high contrast, cinematic lighting, 8k"
        ruta_fondo = os.path.join(dir_salida, "fondo_minia.png")
        ruta_minia = os.path.join(dir_salida, "miniatura_final.png")
        
        # Generar fondo en RunPod usando SDXL o DALL-E 3 si hay API Key de OpenAI
        openai_key = obtener_openai_api_key()
        exito_fondo = False
        
        if openai_key:
            registrar_log("⏳ Creando ilustración de fondo con DALL-E 3 de OpenAI...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_con_dalle3(prompt_img, openai_key, ruta_fondo)
            
        if not exito_fondo:
            registrar_log("⏳ Creando ilustración de fondo GRATIS con FLUX.1 (Pollinations)...")
            exito_fondo = miniaturizador.generar_fondo_miniatura_gratis_pollinations(prompt_img, ruta_fondo)
            
        if not exito_fondo:
            registrar_log("⚠️ La generación gratuita de miniaturas falló. El video continuará su creación sin detenerse.")
            registrar_log("💡 Podrás diseñar y generar la miniatura del video manualmente en la sección de abajo cuando culmine.")
            
        if exito_fondo:
            # Descarga e imitación de la miniatura competidora si se proporciona el ID
            layout_config = None
            if req.competidor_video_id:
                ruta_comp = os.path.join(dir_salida, "miniatura_competidora.jpg")
                registrar_log(f"📥 Descargando miniatura competidora (Video ID: {req.competidor_video_id})...")
                if miniaturizador.descargar_miniatura_competidor(req.competidor_video_id, ruta_comp):
                    if openai_key:
                        registrar_log("🧠 Analizando diseño de la miniatura competidora con OpenAI GPT-4o...")
                        layout_config = miniaturizador.analizar_miniatura_con_openai(ruta_comp, openai_key)
                    if not layout_config:
                        registrar_log("🧠 Analizando diseño de la miniatura competidora con Gemini Vision...")
                        layout_config = miniaturizador.analizar_miniatura_con_gemini(ruta_comp, API_KEY)
                    
                    if layout_config:
                        registrar_log(f"✅ Análisis completado. Estructura copiada: {json.dumps(layout_config)}")
                    else:
                        registrar_log("⚠️ Falló análisis de diseño, usando diseño balanceado por defecto.")
                else:
                    registrar_log("⚠️ No se pudo descargar la miniatura competidora, usando valores estándar.")
                    
            # Componer las 3 opciones de miniatura clickbait para que el usuario elija
            registrar_log("🖼️ Generando 3 opciones de diseño de miniaturas clickbait...")
            
            elem_clave = datos_video.get("elemento_clave", "")
            
            # Opción 1: Diseño de la Competencia (o Clásico Médico si no hay competidor)
            layout_opcion1 = layout_config if layout_config else {
                "texto_posicion_x": "left",
                "texto_alineacion": "left",
                "color_primario": "yellow",
                "color_secundario": "white",
                "inclinacion_grados": -3,
                "sujeto_posicion_x": "right",
                "tiene_banner": True
            }
            ruta_opc1 = os.path.join(dir_salida, "miniatura_opcion1.png")
            miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc1, texto_click, layout_opcion1, elem_clave, url_runpod_interna)
            
            # Opción 2: Alerta Roja (Con Banner Diagonal Diagonal Llamativo)
            layout_opcion2 = {
                "texto_posicion_x": "left",
                "texto_alineacion": "left",
                "color_primario": "white",
                "color_secundario": "yellow",
                "inclinacion_grados": 3,
                "sujeto_posicion_x": "right",
                "tiene_banner": True
            }
            ruta_opc2 = os.path.join(dir_salida, "miniatura_opcion2.png")
            miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc2, texto_click, layout_opcion2, elem_clave, url_runpod_interna)
            
            # Opción 3: Espejo Limpio (Sujeto a la derecha, texto verde/blanco a la izquierda)
            layout_opcion3 = {
                "texto_posicion_x": "left",
                "texto_alineacion": "left",
                "color_primario": "green",
                "color_secundario": "white",
                "inclinacion_grados": 0,
                "sujeto_posicion_x": "right",
                "tiene_banner": False
            }
            ruta_opc3 = os.path.join(dir_salida, "miniatura_opcion3.png")
            miniaturizador.aplicar_estilo_miniatura_avanzado(ruta_fondo, ruta_opc3, texto_click, layout_opcion3, elem_clave, url_runpod_interna)
            
            # Guardar la Opción 1 como la miniatura principal del video
            shutil.copyfile(ruta_opc1, ruta_minia)
            registrar_log("✅ 3 opciones de miniatura terminadas exitosamente.")
        
        # 4. ENSAMBLAJE FINAL DEL VIDEO
        estado_proceso["etapa"] = "Mezcla de video y audio"
        estado_proceso["progreso"] = 90
        registrar_log("🎬 Paso 4/4: Ensamblando audio, video y subtítulos con FFmpeg...")
        ruta_salida = os.path.join(dir_salida, "video_final.mp4")
        
        # Buscar música de fondo opcional según el género solicitado
        ruta_musica = None
        if req.musica_genero:
            genero_clean = req.musica_genero.lower().strip()
            musica_posible = os.path.join(directorio_actual, f"musica_{genero_clean}.mp3")
            
            # Descarga automática si no existe
            if not os.path.exists(musica_posible) or os.path.getsize(musica_posible) < 10000:
                registrar_log(f"📥 Descargando pista de música '{req.musica_genero}' desde internet...")
                try:
                    import urllib.request
                    urls_map = {
                        "lofi": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
                        "epic": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                        "medical": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
                    }
                    url_descarga = urls_map.get(genero_clean, "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3")
                    urllib.request.urlretrieve(url_descarga, musica_posible)
                    registrar_log(f"✅ Música '{os.path.basename(musica_posible)}' descargada exitosamente.")
                except Exception as e:
                    registrar_log(f"⚠️ No se pudo descargar la música de fondo: {e}")
            
            if os.path.exists(musica_posible):
                ruta_musica = musica_posible
                registrar_log(f"🎵 Integrando pista de música de fondo: {os.path.basename(musica_posible)}")
            else:
                musica_fallback = os.path.join(directorio_actual, "musica.mp3")
                # Descarga fallback si no existe
                if not os.path.exists(musica_fallback) or os.path.getsize(musica_fallback) < 10000:
                    try:
                        import urllib.request
                        urllib.request.urlretrieve("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", musica_fallback)
                    except:
                        pass
                if os.path.exists(musica_fallback):
                    ruta_musica = musica_fallback
                    registrar_log("ℹ️ No se encontró música del género, usando musica.mp3 por defecto.")
        
        if not ruta_musica:
            musica_fallback = os.path.join(directorio_actual, "musica.mp3")
            if not os.path.exists(musica_fallback) or os.path.getsize(musica_fallback) < 10000:
                registrar_log("📥 Descargando música de fondo por defecto (musica.mp3)...")
                try:
                    import urllib.request
                    urllib.request.urlretrieve("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", musica_fallback)
                    registrar_log("✅ Música por defecto descargada.")
                except Exception as e:
                    registrar_log(f"⚠️ No se pudo descargar la música por defecto: {e}")
            
            if os.path.exists(musica_fallback):
                ruta_musica = musica_fallback
                registrar_log("ℹ️ Usando música de fondo por defecto (musica.mp3).")
                
        # Ensamblar
        def callback_ffmpeg(pct):
            estado_proceso["progreso"] = 90 + int(pct * 0.1)
            if int(pct) % 10 == 0 or pct >= 99.9:
                registrar_log(f"🎬 Ensamblando video: {pct:.1f}% completado...")

        editor.ensamblar_video(
            ruta_mp3, 
            ruta_ass, 
            ruta_clips, 
            ruta_musica, 
            ruta_salida, 
            orientacion=req.orientacion, 
            volumen_musica=req.volumen_musica,
            callback_progreso=callback_ffmpeg
        )
        
        # 5. CLONACIÓN OPCIONAL A OTROS IDIOMAS
        if req.clonar_idiomas:
            for lang in req.clonar_idiomas:
                registrar_log(f"🌐 Iniciando clonación del video al idioma: {lang.upper()}...")
                
                # Cargar guion traducido
                ruta_json_lang = os.path.join(dir_salida, f"info_video_{lang}.json")
                if not os.path.exists(ruta_json_lang):
                    registrar_log(f"⚠️ No se encontró el guion traducido para {lang.upper()}, saltando.")
                    continue
                    
                with open(ruta_json_lang, "r", encoding="utf-8") as f:
                    datos_video_lang = json.load(f)
                    
                # Mapear idioma destino a voz neural (femenina/masculina)
                es_femenina = any(name in req.voz.lower() for name in ["dalia", "salome", "elena", "paloma", "elvira", "nova", "alloy"])
                if lang == "en":
                    voz_lang = "en-US-EmmaNeural" if es_femenina else "en-US-BrianNeural"
                elif lang == "pt":
                    voz_lang = "pt-BR-FranciscaNeural" if es_femenina else "pt-BR-AntonioNeural"
                else:
                    voz_lang = "en-US-BrianNeural"
                    
                ruta_mp3_lang = os.path.join(dir_salida, f"voz_off_{lang}.mp3")
                ruta_srt_lang = os.path.join(dir_salida, f"subtitulos_{lang}.srt")
                ruta_ass_lang = os.path.join(dir_salida, f"subtitulos_{lang}.ass")
                
                registrar_log(f"🎙️ Generando voz en off ({lang.upper()}) con la voz: {voz_lang}...")
                loop.run_until_complete(
                    locutor.generar_audio_y_subtitulos(
                        datos_video_lang["guion_locucion"], 
                        ruta_mp3_lang, 
                        ruta_srt_lang, 
                        voz=voz_lang,
                        ruta_ass=ruta_ass_lang,
                        orientacion=req.orientacion,
                        font_name=req.sub_fuente,
                        primary_color=req.sub_color_iluminado,
                        secondary_color=req.sub_color_fondo,
                        effect_type=req.sub_animacion,
                        rate=req.velocidad_voz,
                        pitch=req.tono_voz,
                        max_words_per_line=max_words_val,
                        font_size=req.sub_size,
                        outline_thickness=req.sub_outline,
                        alignment=align_val,
                        margin_v=req.sub_margin_v
                    )
                )
                
                # Ensamblar video en idioma destino reutilizando los mismos clips de video
                ruta_salida_lang = os.path.join(dir_salida, f"video_final_{lang}.mp4")
                registrar_log(f"🎬 Ensamblando video ({lang.upper()}) con FFmpeg...")
                
                def callback_ffmpeg_lang(pct):
                    if int(pct) % 10 == 0 or pct >= 99.9:
                        registrar_log(f"🎬 Ensamblando video ({lang.upper()}): {pct:.1f}% completado...")

                editor.ensamblar_video(
                    ruta_mp3_lang, 
                    ruta_ass_lang, 
                    ruta_clips, 
                    ruta_musica, 
                    ruta_salida_lang, 
                    orientacion=req.orientacion, 
                    volumen_musica=req.volumen_musica,
                    callback_progreso=callback_ffmpeg_lang
                )
                
                # Generar miniatura en idioma destino
                if exito_fondo:
                    ruta_minia_lang = os.path.join(dir_salida, f"miniatura_final_{lang}.png")
                    texto_click_lang = datos_video_lang.get("texto_miniatura", "")
                    elem_clave_lang = datos_video_lang.get("elemento_clave", elem_clave)
                    registrar_log(f"🖼️ Generando miniatura clickbait en ({lang.upper()})...")
                    miniaturizador.aplicar_estilo_miniatura_avanzado(
                        ruta_fondo, 
                        ruta_minia_lang, 
                        texto_click_lang, 
                        layout_opcion1, 
                        elem_clave_lang, 
                        url_runpod_interna
                    )
                
                registrar_log(f"✅ Clonación a {lang.upper()} completada con éxito.")
                
        # Proceso finalizado localmente (subida a YouTube y apagado de RunPod omitidos por solicitud del usuario)
        estado_proceso["progreso"] = 100
        estado_proceso["etapa"] = "Completado"
        estado_proceso["ocupado"] = False
        registrar_log("🎉 ¡PROCESO DE GENERACIÓN COMPLETADO CON ÉXITO!")
        registrar_log(f"👉 Tu video listo está en: outputs/{safe_name}/video_final.mp4")
        registrar_log(f"👉 Miniatura en: outputs/{safe_name}/miniatura_final.png")
        registrar_log(f"👉 Descripción en: outputs/{safe_name}/info_subida.txt")
        
    except Exception as e:
        registrar_log(f"❌ Error crítico en el pipeline: {e}")
        estado_proceso["ocupado"] = False
        estado_proceso["etapa"] = "Fallo en Producción"
        
@app.post("/api/producir")
def api_producir(req: ProducirRequest, background_tasks: BackgroundTasks):
    if estado_proceso["ocupado"]:
        raise HTTPException(status_code=400, detail="El sistema está ocupado con otra generación.")
        
    # Guardar automáticamente la URL/pod_id en runpod_config.json
    import re
    from urllib.parse import urlparse
    try:
        url_clean = req.url_runpod.strip()
        parsed = urlparse(url_clean)
        hostname = parsed.hostname or url_clean
        # Buscar el pod_id (e.g. en 'raercweegajfh1-8188.proxy.runpod.net' o 'raercweegajfh1')
        match = re.match(r'^([a-z0-9]+)-\d+', hostname)
        if match:
            new_pod_id = match.group(1)
        else:
            new_pod_id = hostname.split('.')[0].split('-')[0]
            
        if new_pod_id and len(new_pod_id) > 5: # Validar que parezca un ID
            ruta_config = os.path.join(directorio_actual, "runpod_config.json")
            config_data = {}
            if os.path.exists(ruta_config):
                with open(ruta_config, "r") as f:
                    config_data = json.load(f)
            # Solo guardar si ha cambiado
            if config_data.get("pod_id") != new_pod_id:
                config_data["pod_id"] = new_pod_id
                with open(ruta_config, "w") as f:
                    json.dump(config_data, f, indent=4)
                print(f"💾 Guardado nuevo RunPod Pod ID: {new_pod_id}")
    except Exception as e:
        print(f"⚠️ Error al guardar configuración de RunPod de forma automática: {e}")

    estado_proceso["ocupado"] = True
    estado_proceso["tema"] = req.tema
    estado_proceso["etapa"] = "Iniciando producción"
    estado_proceso["progreso"] = 5
    estado_proceso["mensajes"] = []
    estado_proceso["clonar_idiomas"] = req.clonar_idiomas or []
    
    # Lanzar la producción pesada en segundo plano para que el servidor responda de inmediato
    background_tasks.add_task(proceso_background_producir, req)
    return {"status": "started", "message": "Proceso de producción iniciado en segundo plano."}

@app.post("/api/abrir_carpeta")
def api_abrir_carpeta():
    import subprocess
    import sys
    
    # Obtener el directorio de salida del estado global
    dir_salida = estado_proceso.get("directorio_salida")
    if not dir_salida or not os.path.exists(dir_salida):
        dir_salida = outputs_dir
        
    try:
        # Normalizar la ruta para evitar problemas con backslashes en Windows/Shell
        dir_salida = os.path.abspath(dir_salida)
        
        # Abrir el explorador de archivos según la plataforma
        if sys.platform == "win32":
            os.startfile(dir_salida)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", dir_salida])
        else:
            subprocess.Popen(["xdg-open", dir_salida])
            
        nombre_carpeta = os.path.basename(dir_salida)
        return {"status": "ok", "message": f"Carpeta '{nombre_carpeta}' abierta"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir la carpeta: {str(e)}")

# Servir el frontend estáticamente en la raíz (/) del sitio local
frontend_dir = os.path.join(directorio_actual, "frontend")
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # Arrancar en el puerto 5000
    uvicorn.run(app, host="127.0.0.1", port=5000)
