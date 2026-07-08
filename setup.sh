#!/bin/bash
echo "=== DESPLEGANDO FABRICA DE VIDEOS ==="
REPO_DIR="/workspace/fabrica-deploy-tmp"

# Copiar archivos Python al directorio de trabajo
mkdir -p /workspace/Canal_de_Salud_de_Victor/frontend
cp $REPO_DIR/servidor_api.py /workspace/Canal_de_Salud_de_Victor/
cp $REPO_DIR/locutor.py /workspace/Canal_de_Salud_de_Victor/
cp $REPO_DIR/generador.py /workspace/Canal_de_Salud_de_Victor/
cp $REPO_DIR/editor.py /workspace/Canal_de_Salud_de_Victor/
cp $REPO_DIR/miniaturizador.py /workspace/Canal_de_Salud_de_Victor/
if [ -f "$REPO_DIR/subidor_youtube.py" ]; then
    cp $REPO_DIR/subidor_youtube.py /workspace/Canal_de_Salud_de_Victor/
fi
cp $REPO_DIR/frontend/index.html /workspace/Canal_de_Salud_de_Victor/frontend/
cp $REPO_DIR/frontend/style.css /workspace/Canal_de_Salud_de_Victor/frontend/
cp $REPO_DIR/frontend/app.js /workspace/Canal_de_Salud_de_Victor/frontend/

# Decodificar token.pickle
if [ -f "$REPO_DIR/token.pickle.b64" ]; then
    base64 -d $REPO_DIR/token.pickle.b64 > /workspace/Canal_de_Salud_de_Victor/token.pickle
    echo "✅ Token de YouTube decodificado."
fi

# Copiar arrancar.sh
cp $REPO_DIR/arrancar.sh /workspace/arrancar.sh
chmod +x /workspace/arrancar.sh

# Crear scripts de inicio automatico para RunPod
echo "🤖 Configurando auto-arranque para futuros reinicios del Pod..."
AUTOSTART_CONTENT='#!/bin/bash
echo "🤖 [AUTOSTART] Iniciando ComfyUI y la API de la Fabrica de Videos..."
cd /workspace && ./arrancar.sh &
'
echo "$AUTOSTART_CONTENT" > /workspace/pre_start.sh
chmod +x /workspace/pre_start.sh

# Tambien en la raiz del contenedor / por compatibilidad
if [ -w "/pre_start.sh" ] || [ ! -f "/pre_start.sh" ]; then
    echo "$AUTOSTART_CONTENT" > /pre_start.sh 2>/dev/null || true
    chmod +x /pre_start.sh 2>/dev/null || true
fi

echo "=== DESPLIEGUE COMPLETADO ==="
ls -la /workspace/Canal_de_Salud_de_Victor/
echo ""
echo "Ahora ejecuta: cd /workspace && ./arrancar.sh"
