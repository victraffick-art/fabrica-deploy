#!/bin/bash
echo "=========================================================================="
echo "🚀 INICIANDO FÁBRICA DE VIDEOS EN RUNPOD (ENTORNO VIRTUAL PERSISTENTE)"
echo "=========================================================================="

# Crear entorno virtual si no existe en la carpeta persistente
VENV_DIR="/workspace/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creando entorno virtual persistente en $VENV_DIR..."
    python3 -m venv $VENV_DIR
    source $VENV_DIR/bin/activate
    
    echo "⏳ 1. Instalando PyTorch compatible con CUDA 12.4 (Soluciona error de Drivers)..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
    
    echo "⏳ 2. Instalando dependencias de la Fábrica de Videos..."
    pip install fastapi uvicorn pydantic requests edge-tts google-api-python-client google-auth-oauthlib google-auth-httplib2 pillow aiohttp sqlalchemy alembic comfy_aimdo opencv-python-headless accelerate gitpython librosa gguf toml ftfy
    
    echo "⏳ 3. Instalando dependencias de ComfyUI..."
    if [ -f "/workspace/ComfyUI/requirements.txt" ]; then
        pip install -r /workspace/ComfyUI/requirements.txt
    fi
    
    # ── NUEVO: Instalar automáticamente los requirements de todos los custom nodes ──
    echo "⏳ 3.5. Resolviendo dependencias de todos los custom nodes de ComfyUI..."
    for req_file in /workspace/ComfyUI/custom_nodes/*/requirements.txt; do
        if [ -f "$req_file" ]; then
            _node_name=$(basename $(dirname "$req_file"))
            echo "   -> Instalando dependencias para: $_node_name"
            pip install --no-cache-dir -r "$req_file" 2>/dev/null || true
        fi
    done
else
    echo "✅ Entorno virtual detectado. Activando..."
    source $VENV_DIR/bin/activate
fi

# Eliminar duplicados de WanVideoWrapper para evitar conflictos
if [ -d "/workspace/ComfyUI/custom_nodes/ComfyUI_WanVideoWrapper" ]; then
    echo "🧹 Eliminando carpeta duplicada ComfyUI_WanVideoWrapper..."
    rm -rf /workspace/ComfyUI/custom_nodes/ComfyUI_WanVideoWrapper
fi

# Verificar ComfyUI y Nodos
echo "⏳ 4. Verificando repositorios y modelos..."
if [ ! -d "/workspace/ComfyUI" ]; then
    echo "   Clonando ComfyUI..."
    git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI
    pip install -r /workspace/ComfyUI/requirements.txt
fi

# Aplicar parche de inicio automático en main.py de ComfyUI (hace que arranque venv y backend solos en cualquier reinicio)
python3 -c "
import os
main_path = '/workspace/ComfyUI/main.py'
if os.path.exists(main_path):
    with open(main_path, 'r') as f:
        content = f.read()
    if 'AUTO START PATCH' not in content:
        patch = '''# --- AUTO START PATCH ---
import os, sys, subprocess
venv = '/workspace/venv/lib/python3.10/site-packages'
if os.path.exists(venv):
    if venv not in sys.path:
        sys.path.insert(0, venv)
    os.environ['VIRTUAL_ENV'] = '/workspace/venv'
    os.environ['PATH'] = '/workspace/venv/bin:' + os.environ.get('PATH', '')
    try:
        import urllib.request
        urllib.request.urlopen('http://127.0.0.1:5000/estado', timeout=1)
    except Exception:
        subprocess.Popen(['/workspace/venv/bin/python', '/workspace/Canal_de_Salud_de_Victor/servidor_api.py'], stdout=open('/workspace/Canal_de_Salud_de_Victor/servidor_factory.log', 'w'), stderr=subprocess.STDOUT)
# ------------------------
'''
        with open(main_path, 'w') as f:
            f.write(patch + content)
        print('   ✅ Parche de auto-arranque aplicado a ComfyUI main.py')
"

CUSTOM_NODES=/workspace/ComfyUI/custom_nodes
mkdir -p $CUSTOM_NODES

if [ ! -d "$CUSTOM_NODES/ComfyUI-WanVideoWrapper" ]; then
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git $CUSTOM_NODES/ComfyUI-WanVideoWrapper
    pip install -r $CUSTOM_NODES/ComfyUI-WanVideoWrapper/requirements.txt 2>/dev/null || true
fi

if [ ! -d "$CUSTOM_NODES/ComfyUI-VideoHelperSuite" ]; then
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git $CUSTOM_NODES/ComfyUI-VideoHelperSuite
    pip install -r $CUSTOM_NODES/ComfyUI-VideoHelperSuite/requirements.txt 2>/dev/null || true
fi

# Directorio de modelos
MODELS_DIR=/workspace/ComfyUI/models
mkdir -p $MODELS_DIR/wan_video $MODELS_DIR/text_encoders $MODELS_DIR/vae

# Descarga de modelos (si no existen o pesan 0 bytes)
descargar_si_falta() {
    local ruta="$1"
    local url="$2"
    local nombre="$3"
    
    if [ ! -f "$ruta" ] || [ ! -s "$ruta" ]; then
        echo "   Descargando $nombre..."
        rm -f "$ruta" # Eliminar si existia con 0 bytes
        wget -q --show-progress -O "$ruta" "$url"
    else
        echo "   ✅ $nombre ya listo."
    fi
}

descargar_si_falta "$MODELS_DIR/wan_video/wan2.1_t2v_1.3B_bf16.safetensors" \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-T2V-1_3B_bf16.safetensors" \
    "Modelo Wan2.1 T2V"

descargar_si_falta "$MODELS_DIR/text_encoders/umt5-xxl-enc-bf16.safetensors" \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors" \
    "T5 Encoder"

descargar_si_falta "$MODELS_DIR/vae/Wan2_1_VAE_bf16.safetensors" \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors" \
    "VAE Model"

echo "🛰️ 5. Iniciando Backend API de la Fábrica en segundo plano..."
cd /workspace/Canal_de_Salud_de_Victor
python servidor_api.py > servidor_factory.log 2>&1 &

echo "🎨 6. Iniciando ComfyUI..."
cd /workspace/ComfyUI
python main.py --port 8188 --listen 0.0.0.0 --highvram
