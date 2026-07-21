import os
import sys
import requests
import json
import time
import socket
import subprocess
from urllib.parse import urlparse

import socket

_dns_parcheados = {}
_original_getaddrinfo = None
last_comfy_error = ""  # Almacena el último error de conexión para mostrar en la UI

def aplicar_parche_dns(hostname_target):
    global _original_getaddrinfo
    if sys.platform != "win32":
        return
        
    hostname_target = hostname_target.lower()
    if hostname_target in _dns_parcheados:
        return
        
    try:
        # Intentar resolver usando el DNS público de Google (8.8.8.8) para evitar bloqueos/fallos de ISPs locales
        cmd = ["powershell", "-Command", f"(Resolve-DnsName -Name '{hostname_target}' -Server 8.8.8.8 -Type A -ErrorAction SilentlyContinue).IPAddress"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        ips = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        
        # Fallback al DNS normal del sistema si falla el de Google
        if not ips:
            cmd_fallback = ["powershell", "-Command", f"[System.Net.Dns]::GetHostAddresses('{hostname_target}') | Select-Object -ExpandProperty IPAddressToString"]
            result_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=8)
            ips = [line.strip() for line in result_fallback.stdout.splitlines() if line.strip()]
            
        # Fallback inteligente para subdominios proxy de RunPod usando el puerto activo 7777
        if not ips and "-8188.proxy.runpod.net" in hostname_target:
            fallback_hostname = hostname_target.replace("-8188.proxy.runpod.net", "-7777.proxy.runpod.net")
            print(f"🔄 [DNS FALLBACK] Re-intentando resolver usando puerto VS Code: '{fallback_hostname}'")
            cmd_fb = ["powershell", "-Command", f"(Resolve-DnsName -Name '{fallback_hostname}' -Server 8.8.8.8 -Type A -ErrorAction SilentlyContinue).IPAddress"]
            result_fb = subprocess.run(cmd_fb, capture_output=True, text=True, timeout=8)
            ips = [line.strip() for line in result_fb.stdout.splitlines() if line.strip()]
            if not ips:
                cmd_fb2 = ["powershell", "-Command", f"[System.Net.Dns]::GetHostAddresses('{fallback_hostname}') | Select-Object -ExpandProperty IPAddressToString"]
                result_fb2 = subprocess.run(cmd_fb2, capture_output=True, text=True, timeout=8)
                ips = [line.strip() for line in result_fb2.stdout.splitlines() if line.strip()]
                
        if ips:
            ip_resuelta = ips[0]
            _dns_parcheados[hostname_target] = ip_resuelta
            
            # Registrar el hook de getaddrinfo original sólo una vez
            if _original_getaddrinfo is None:
                _original_getaddrinfo = socket.getaddrinfo
                
                def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
                    h_lower = host.lower()
                    if h_lower in _dns_parcheados:
                        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_dns_parcheados[h_lower], port))]
                    return _original_getaddrinfo(host, port, family, type, proto, flags)
                
                socket.getaddrinfo = patched_getaddrinfo
                
            print(f"🔧 [PARCHE DNS] Mapeando '{hostname_target}' -> '{ip_resuelta}'")
    except Exception as e:
        print(f"⚠️ No se pudo aplicar el parche DNS para '{hostname_target}': {e}")

def aplicar_parche_dns_desde_url(url):
    try:
        url_clean = url.strip()
        if not url_clean.startswith(("http://", "https://")):
            url_clean = "https://" + url_clean
        hostname = urlparse(url_clean).hostname
        if hostname:
            aplicar_parche_dns(hostname)
    except Exception as e:
        print(f"⚠️ Error al extraer hostname de la URL: {e}")

def enviar_prompt_a_comfyui(server_url, prompt_texto, index_clip, seed=42, width=832, height=480, steps=30):
    """
    Construye y envía el JSON del workflow de ComfyUI para generar un clip de video.
    """
    aplicar_parche_dns_desde_url(server_url)
    if not server_url.startswith(("http://", "https://")):
        server_url = "https://" + server_url
    server_url = server_url.strip("/")
    
    # Workflow API adaptado para Wan 2.1 (Text to Video)
    workflow_api = {
        "1": {
            "inputs": {
                "model": "Wan2.1/wan2.1_t2v_1.3B_bf16.safetensors",
                "base_precision": "bf16",
                "quantization": "disabled",
                "load_device": "gpu",
                "block_swap_args": ["10", 0]
            }, 
            "class_type": "WanVideoModelLoader"
        },
        "2": {
            "inputs": {
                "positive_prompt": f"Cinematic B-roll, medical video essay style, {prompt_texto}, 4k, hyperrealistic, slow motion.", 
                "negative_prompt": "blurry, low quality, distorted, bad anatomy, text, watermark, vertical, static, ugly",
                "device": "gpu",
                "t5": ["3", 0]
            }, 
            "class_type": "WanVideoTextEncode"
        },
        "3": {
            "inputs": {
                "model_name": "umt5-xxl-enc-bf16.safetensors",
                "precision": "bf16",
                "quantization": "fp8_e4m3fn"
            }, 
            "class_type": "LoadWanVideoT5TextEncoder"
        },
        "4": {
            "inputs": {
                "model_name": "Wan2_1_VAE_bf16.safetensors",
                "precision": "bf16"
            }, 
            "class_type": "WanVideoVAELoader"
        },
        "5": {
            "inputs": {
                "model": ["1", 0], 
                "image_embeds": ["7", 0], 
                "text_embeds": ["2", 0], 
                "steps": steps, 
                "cfg": 6.0, 
                "shift": 5.0,
                "seed": seed + index_clip, 
                "force_offload": False,
                "scheduler": "unipc",
                "riflex_freq_index": 0
            }, 
            "class_type": "WanVideoSampler"
        },
        "7": {
            "inputs": {
                "width": width, 
                "height": height, 
                "num_frames": 81
            }, 
            "class_type": "WanVideoEmptyEmbeds"
        },
        "8": {
            "inputs": {
                "vae": ["4", 0],
                "samples": ["5", 0],
                "enable_vae_tiling": False,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128
            }, 
            "class_type": "WanVideoDecode"
        },
        "9": {
            "inputs": {
                "frame_rate": 15, 
                "loop_count": 0, 
                "filename_prefix": f"Clip_{index_clip:03d}", 
                "format": "video/h264-mp4", 
                "images": ["8", 0],
                "pingpong": False,
                "save_output": True
            }, 
            "class_type": "VHS_VideoCombine"
        },
        "10": {
            "inputs": {
                "blocks_to_swap": 40,
                "offload_img_emb": True,
                "offload_txt_emb": True,
                "use_non_blocking": False,
                "vace_blocks_to_swap": 15,
                "prefetch_blocks": 0,
                "block_swap_debug": False
            },
            "class_type": "WanVideoBlockSwap"
        }
    }
    
    try:
        response = requests.post(f"{server_url}/prompt", json={"prompt": workflow_api}, timeout=30)
        if response.status_code == 200:
            prompt_id = response.json()["prompt_id"]
            print(f"🚀 Clip {index_clip:03d} encolado en RunPod. Prompt ID: {prompt_id}")
            return prompt_id
        else:
            import generador as _self
            _self.last_comfy_error = f"HTTP {response.status_code}: {response.text[:400]}"
            print(f"❌ Error HTTP {response.status_code} al encolar Clip {index_clip:03d}: {response.text[:500]}")
    except Exception as e:
        import generador as _self
        _self.last_comfy_error = f"{type(e).__name__}: {str(e)[:300]}"
        print(f"❌ No se pudo conectar a RunPod ({server_url}): {type(e).__name__}: {e}")
    return None

def esperar_y_descargar(server_url, prompt_id, ruta_salida, max_intentos=180, delay=10):
    """
    Monitorea la cola de ComfyUI y descarga el archivo mp4 final cuando termine.
    """
    aplicar_parche_dns_desde_url(server_url)
    server_url = server_url.strip("/")
    print(f"⏳ Esperando que el servidor procese el video {prompt_id}...")
    
    for intento in range(max_intentos):
        try:
            res = requests.get(f"{server_url}/history/{prompt_id}", timeout=10)
            if res.status_code == 200:
                history = res.json()
                if prompt_id in history:
                    # El prompt ha terminado, extraer la información del output
                    datos_prompt = history[prompt_id]
                    # Buscar outputs en los nodos (generalmente en el nodo 9 de guardado)
                    outputs = datos_prompt.get("outputs", {})
                    filename = None
                    
                    for node_id, node_output in outputs.items():
                        # VHS VideoCombine guarda en 'gifs' o 'images'
                        if "gifs" in node_output:
                            filename = node_output["gifs"][0]["filename"]
                            break
                        elif "images" in node_output:
                            filename = node_output["images"][0]["filename"]
                            break
                            
                    if filename:
                        # Descargar archivo
                        url_descarga = f"{server_url}/view?filename={filename}&type=output"
                        print(f"⬇️ Descargando video generado: {filename}...")
                        
                        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
                        res_file = requests.get(url_descarga, stream=True)
                        
                        if res_file.status_code == 200:
                            with open(ruta_salida, "wb") as f:
                                for chunk in res_file.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            print(f"✅ Descarga completada: {ruta_salida}")
                            return True
                        else:
                            print(f"❌ Falló la descarga del archivo: HTTP {res_file.status_code}")
                    else:
                        print("❌ El prompt terminó pero no se encontró un archivo de video de salida.")
                    return False
        except Exception as e:
            # Errores de red transitorios se ignoran durante el polling
            pass
            
        time.sleep(delay)
        if intento % 3 == 0:
            print(f"   ...siguiendo progreso (intento {intento}/{max_intentos})")
            
    print(f"⏱️ Tiempo de espera agotado para el prompt {prompt_id}.")
    return False

def generar_fondo_miniatura(server_url, prompt_texto, ruta_salida, seed=9999):
    """
    Genera una imagen artística de alta calidad en RunPod para usarla como fondo de miniatura.
    """
    aplicar_parche_dns_desde_url(server_url)
    server_url = server_url.strip("/")
    print("🎨 Encolando generación de fondo de miniatura...")
    
    # Workflow simple de T2I para miniatura
    workflow_t2i = {
        "3": {
            "inputs": {
                "seed": seed,
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "class_type": "KSampler"
        },
        "4": {
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        "5": {
            "inputs": {"width": 1280, "height": 720, "batch_size": 1},
            "class_type": "EmptyLatentImage"
        },
        "6": {
            "inputs": {
                "text": f"High quality cinematic 8k thumbnail background, medical clinic, {prompt_texto}, depth of field, sharp focus",
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": {
                "text": "blurry, low quality, distorted, text, watermark, bad anatomy, ugly",
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "8": {
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {"filename_prefix": "Thumbnail_BG", "images": ["8", 0]},
            "class_type": "SaveImage"
        }
    }
    
    try:
        response = requests.post(f"{server_url}/prompt", json={"prompt": workflow_t2i}, timeout=30)
        if response.status_code == 200:
            prompt_id = response.json()["prompt_id"]
            return esperar_y_descargar(server_url, prompt_id, ruta_salida)
    except Exception as e:
        print(f"❌ Error al generar miniatura en RunPod: {e}")
    return False
