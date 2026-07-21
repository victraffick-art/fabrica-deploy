// ==========================================================================
// 🤖 LÓGICA DE CONTROL DE LA FÁBRICA DE VIDEOS v6.0
// Nuevas funciones: Filtro IA/Faceless · Cards Horizontales · Stats Modal · Gráficas
// ==========================================================================

const API_BASE_URL = window.location.origin;
let datosVideoActual = null;
let videoIdCompetidorSeleccionado = "";
let pollingInterval = null;

// Variables para multilenguaje
let datosClonados = { es: null, en: null, pt: null };
let idiomaActual = 'es';
let activeFolderName = "";
let temaOriginalRedactado = "";

// Instancias de Chart.js para el modal
let chartVideoViews = null;
let chartChannelGrowth = null;

window.cambiarIdiomaResultados = function(lang) {
    idiomaActual = lang;
    
    document.querySelectorAll(".lang-tab-btn").forEach(btn => {
        if (btn.getAttribute("data-lang") === lang) {
            btn.classList.add("active");
            btn.style.background = "var(--primary-color)";
            btn.style.color = "white";
        } else {
            btn.classList.remove("active");
            btn.style.background = "";
            btn.style.color = "";
        }
    });
    
    if (!activeFolderName) return;
    
    const t = Date.now();
    let videoUrl = `${API_BASE_URL}/outputs/${activeFolderName}/video_final.mp4?t=${t}`;
    let opc1Url  = `${API_BASE_URL}/outputs/${activeFolderName}/miniatura_opcion1.png?t=${t}`;
    
    const colOpc2 = document.getElementById("thumb-img-opc2")?.closest(".thumbnail-item");
    const colOpc3 = document.getElementById("thumb-img-opc3")?.closest(".thumbnail-item");
    
    if (lang === "es") {
        if (colOpc2) colOpc2.style.display = "flex";
        if (colOpc3) colOpc3.style.display = "flex";
    } else {
        if (colOpc2) colOpc2.style.display = "none";
        if (colOpc3) colOpc3.style.display = "none";
        videoUrl = `${API_BASE_URL}/outputs/${activeFolderName}/video_final_${lang}.mp4?t=${t}`;
        opc1Url  = `${API_BASE_URL}/outputs/${activeFolderName}/miniatura_final_${lang}.png?t=${t}`;
    }
    
    const playerSource = videoPlayer.querySelector("source");
    if (playerSource) {
        playerSource.src = videoUrl;
        videoPlayer.load();
        downloadVideoBtn.href = videoUrl;
        downloadVideoBtn.innerText = `📥 Descargar Video Final (${lang.toUpperCase()})`;
    }
    
    const imgOpc1 = document.getElementById("thumb-img-opc1");
    const btnOpc1 = document.getElementById("download-opc1-btn");
    if (imgOpc1) {
        imgOpc1.src = opc1Url;
        if (btnOpc1) {
            btnOpc1.href = opc1Url;
            btnOpc1.innerText = `Descargar Miniatura (${lang.toUpperCase()})`;
        }
    }
    
    const vData = datosClonados[lang];
    if (vData) {
        document.getElementById("pub-titulo").value      = vData.titulos ? vData.titulos[0] : "";
        document.getElementById("pub-descripcion").value = vData.descripcion || "";
        document.getElementById("pub-tags").value        = vData.tags ? vData.tags.join(", ") : "";
    }
};

// Elementos del DOM
const serverStatus          = document.getElementById("server-status");
const competidorUrls        = document.getElementById("competidor-urls");
const btnRastrear           = document.getElementById("btn-rastrear");
const containerSeleccionVideo = document.getElementById("container-seleccion-video");
const selectVideosVirales   = document.getElementById("select-videos-virales");
const temaManual            = document.getElementById("tema-manual");
const btnRedactar           = document.getElementById("btn-redactar");
const selectDuracion        = document.getElementById("select-duracion");
const runpodUrl             = document.getElementById("runpod-url");
const selectVoz             = document.getElementById("select-voz");
const selectEstilo          = document.getElementById("select-estilo");
const selectOrientacion     = document.getElementById("select-orientacion");
const selectMusica          = document.getElementById("select-musica");
const competidorVideoIdInput = document.getElementById("competidor-video-id");
const btnProducir           = document.getElementById("btn-producir");
const progressSpinner       = document.getElementById("progress-spinner");
const progressEtapa         = document.getElementById("progress-etapa");
const progressPorcentaje    = document.getElementById("progress-porcentaje");
const progressBar           = document.getElementById("progress-bar");
const consoleOutput         = document.getElementById("console-output");
const btnLimpiarLog         = document.getElementById("btn-limpiar-log");
const videoPlayer           = document.getElementById("video-player");
const downloadVideoBtn      = document.getElementById("download-video-btn");
const btnRegenerarMinia     = document.getElementById("btn-regenerar-minia");
const modalGuion            = document.getElementById("modal-guion");
const modalTitulosContainer = document.getElementById("modal-titulos-container");
const modalTextoMinia       = document.getElementById("modal-texto-minia");
const modalGuionTexto       = document.getElementById("modal-guion-texto");
const btnCloseModal         = document.getElementById("btn-close-modal");
const btnCancelarGuion      = document.getElementById("btn-cancelar-guion");
const modalWordCount        = document.getElementById("modal-word-count");
const btnGuardarGuion       = document.getElementById("btn-guardar-guion");

let tituloSeleccionadoModal = "";

function actualizarContadorPalabras() {
    const texto   = modalGuionTexto.value || "";
    const palabras = texto.trim().split(/\s+/).filter(w => w.length > 0).length;
    if (modalWordCount) modalWordCount.innerText = `Palabras: ${palabras}`;
}

// ─── CONEXIÓN ──────────────────────────────────────────────────────────────
async function verificarConexion() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/status`);
        if (res.ok) {
            serverStatus.className = "server-status-pill online";
            serverStatus.querySelector(".status-text").innerText = "Servidor Local Conectado";
            return true;
        }
    } catch (e) {
        serverStatus.className = "server-status-pill offline";
        serverStatus.querySelector(".status-text").innerText = "Backend Desconectado (Puerto 5000)";
    }
    return false;
}

// ─── DIALOGO DE CONFIRMACIÓN DE RUNPOD ──────────────────────────────────────
function mostrarModalConfirmacionRunpod(mensaje, onConfirm, onRetry, onCancel) {
    const existing = document.getElementById("comfy-confirm-modal");
    if (existing) existing.remove();
    
    const overlay = document.createElement("div");
    overlay.id = "comfy-confirm-modal";
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(5, 8, 16, 0.9); backdrop-filter: blur(12px);
        display: flex; align-items: center; justify-content: center;
        z-index: 10000; font-family: 'Inter', sans-serif;
    `;
    
    overlay.innerHTML = `
        <div class="glass-card" style="width: 90%; max-width: 500px; padding: 30px; text-align: center; border: 1px solid rgba(245, 158, 11, 0.4); box-shadow: 0 20px 50px rgba(0,0,0,0.8); background: #111827;">
            <div style="font-size: 3rem; margin-bottom: 15px;">⚠️</div>
            <h2 style="font-size: 1.3rem; font-weight: 800; color: #fff; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Confirmación de RunPod</h2>
            <p style="font-size: 0.9rem; color: #94a3b8; line-height: 1.5; margin-bottom: 25px;">${mensaje}</p>
            <div style="display: flex; flex-direction: column; gap: 10px;">
                <button id="comfy-btn-confirm" class="btn btn-accent btn-full" style="background: linear-gradient(135deg, #f59e0b, #d97706); border:none; color:white; font-weight:bold; height:42px; cursor:pointer;">🚀 Sí, Usar RunPod (ComfyUI)</button>
                <button id="comfy-btn-retry" class="btn btn-secondary btn-full" style="height:42px; cursor:pointer;">🔄 Reintentar Generación Gratis</button>
                <button id="comfy-btn-cancel" class="btn btn-secondary btn-full" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.2); height:42px; cursor:pointer;">❌ Cancelar Todo</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    document.getElementById("comfy-btn-confirm").onclick = () => { overlay.remove(); onConfirm(); };
    document.getElementById("comfy-btn-retry").onclick = () => { overlay.remove(); onRetry(); };
    document.getElementById("comfy-btn-cancel").onclick = () => { overlay.remove(); onCancel(); };
}

// ─── POLLING ───────────────────────────────────────────────────────────────
async function pollStatus() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/status`);
        if (!res.ok) return;
        const data = await res.json();
        
        progressEtapa.innerText       = data.etapa;
        progressPorcentaje.innerText  = `${data.progreso}%`;
        progressBar.style.width       = `${data.progreso}%`;
        
        if (data.esperando_confirmacion_runpod) {
            if (!document.getElementById("comfy-confirm-modal")) {
                mostrarModalConfirmacionRunpod(
                    "Las opciones de miniaturas gratuitas en la nube han fallado. ¿Deseas encender RunPod (ComfyUI) y continuar la producción del video allí, o reintentar gratis?",
                    async () => {
                        await fetch(`${API_BASE_URL}/api/producir/confirmar_comfy`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ respuesta: "comfy" })
                        });
                    },
                    async () => {
                        await fetch(`${API_BASE_URL}/api/producir/confirmar_comfy`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ respuesta: "retry" })
                        });
                    },
                    async () => {
                        await fetch(`${API_BASE_URL}/api/producir/confirmar_comfy`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ respuesta: "cancel" })
                        });
                    }
                );
            }
        }
        
        if (data.ocupado) {
            btnProducir.disabled  = true;
            btnProducir.innerText = "⏳ PROCESANDO EN RunPod...";
            btnRedactar.disabled  = true;
            btnRastrear.disabled  = true;
            progressSpinner.style.display = "block";
        } else {
            btnProducir.disabled  = false;
            btnProducir.innerText = "🚀 PRODUCIR VIDEO COMPLETO (1-CLIC)";
            btnRedactar.disabled  = false;
            btnRastrear.disabled  = false;
            progressSpinner.style.display = "none";
            if (data.etapa === "Completado" && pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        }
        
        if (data.mensajes && data.mensajes.length > 0) {
            consoleOutput.innerHTML = "";
            data.mensajes.forEach(msg => {
                const line = document.createElement("div");
                line.className = "log-line";
                if (msg.includes("❌") || msg.includes("⚠️")) line.className += " error";
                else if (msg.includes("✅") || msg.includes("🎉")) line.className += " success";
                else if (msg.includes("🛰️") || msg.includes("🤖")) line.className += " system";
                line.innerText = msg;
                consoleOutput.appendChild(line);
            });
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        
        if (data.etapa === "Completado" && data.directorio_salida) {
            const folderName = data.directorio_salida.split(/[\\\/]/).pop();
            if (activeFolderName === folderName) return;
            activeFolderName = folderName;
            if (!datosClonados.es) datosClonados.es = data.datos_video || datosVideoActual;
            
            const hasEn = data.clonar_idiomas && data.clonar_idiomas.includes("en");
            const hasPt = data.clonar_idiomas && data.clonar_idiomas.includes("pt");
            
            const tabs = ["btn-lang-en","btn-lang-pt","btn-prev-en","btn-prev-pt"];
            const flags = [hasEn, hasPt, hasEn, hasPt];
            tabs.forEach((id, i) => {
                const el = document.getElementById(id);
                if (el) el.style.display = flags[i] ? "inline-block" : "none";
            });
            
            if (hasEn && !datosClonados.en) {
                fetch(`${API_BASE_URL}/outputs/${folderName}/info_video_en.json`)
                    .then(r => r.json()).then(j => { datosClonados.en = j; if (idiomaActual==="en") cambiarIdiomaResultados("en"); }).catch(()=>{});
            }
            if (hasPt && !datosClonados.pt) {
                fetch(`${API_BASE_URL}/outputs/${folderName}/info_video_pt.json`)
                    .then(r => r.json()).then(j => { datosClonados.pt = j; if (idiomaActual==="pt") cambiarIdiomaResultados("pt"); }).catch(()=>{});
            }
            
            cambiarIdiomaResultados(idiomaActual);
            
            if (idiomaActual === "es") {
                const t2 = Date.now();
                ["opc2","opc3"].forEach((opt, i) => {
                    const img = document.getElementById(`thumb-img-${opt}`);
                    const btn = document.getElementById(`download-${opt}-btn`);
                    const url = `${API_BASE_URL}/outputs/${folderName}/miniatura_opcion${i+2}.png?t=${t2}`;
                    if (img && img.src !== url) {
                        img.src = url;
                        if (btn) { btn.href = url; btn.style.display = "inline-flex"; }
                    }
                });
            }
            
            document.getElementById("publish-kit").style.display = "block";
            downloadVideoBtn.style.display = "inline-flex";
            const b1 = document.getElementById("download-opc1-btn");
            if (b1) b1.style.display = "inline-flex";
            if (btnRegenerarMinia) btnRegenerarMinia.style.display = "inline-block";
        }
    } catch (e) {
        console.error("Error en polling:", e);
    }
}

// ─── RASTREAR ──────────────────────────────────────────────────────────────
btnRastrear.addEventListener("click", async () => {
    const urls = competidorUrls.value.split("\n").map(u => u.trim()).filter(u => u.length > 0);
    if (urls.length === 0) { alert("Por favor ingresa al menos un enlace de canal de YouTube."); return; }
    
    btnRastrear.disabled = true;
    btnRastrear.innerText = "⏳ RASTREANDO CANALES...";
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/rastrear`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ canales: urls })
        });
        if (res.ok) {
            const data = await res.json();
            selectVideosVirales.innerHTML = '<option value="">-- Selecciona un tema viral --</option>';
            if (data.temas && data.temas.length > 0) {
                data.temas.forEach(item => {
                    const opt = document.createElement("option");
                    opt.value    = item.title;
                    opt.dataset.id = item.id;
                    opt.innerText = item.label || item.title;
                    selectVideosVirales.appendChild(opt);
                });
                containerSeleccionVideo.style.display = "block";
                alert("¡Rastreo exitoso! Se encontraron temas virales populares. Elige uno en el menú.");
            } else {
                alert("No se detectaron videos populares recientes. Escribe un tema manual.");
            }
        }
    } catch (e) {
        alert("Error de conexión al rastrear. Asegúrate de que el servidor FastAPI esté encendido en tu PC.");
    } finally {
        btnRastrear.disabled = false;
        btnRastrear.innerText = "🔍 DETECTAR VIDEOS VIRALES (OUTLIERS)";
    }
});

selectVideosVirales.addEventListener("change", () => {
    const chosen = selectVideosVirales.options[selectVideosVirales.selectedIndex];
    if (chosen.value) {
        temaManual.value = chosen.value;
        videoIdCompetidorSeleccionado = chosen.dataset.id || "";
        competidorVideoIdInput.value  = videoIdCompetidorSeleccionado;
        actualizarCompetitorThumbPreview();
    }
});

// ─── REDACTAR ──────────────────────────────────────────────────────────────
btnRedactar.addEventListener("click", async () => {
    const tema = temaManual.value.trim();
    if (!tema) { alert("Escribe un tema o selecciona uno de los videos ganadores primero."); return; }
    
    btnRedactar.disabled = true;
    btnRedactar.innerText = "⏳ GEMINI REDACTANDO...";
    
    const clonarIdiomas = [];
    if (document.getElementById("clone-en")?.checked) clonarIdiomas.push("en");
    if (document.getElementById("clone-pt")?.checked) clonarIdiomas.push("pt");

    try {
        const res = await fetch(`${API_BASE_URL}/api/redactar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tema, duracion_min: parseFloat(selectDuracion.value) || 1.0,
                clonar_idiomas: clonarIdiomas,
                estructura:   document.getElementById("select-narrativa").value,
                intro_pers:   document.getElementById("txt-intro-pers").value.trim(),
                cierre_pers:  document.getElementById("txt-cierre-pers").value.trim(),
                competidor_video_id: competidorVideoIdInput ? competidorVideoIdInput.value.trim() : null
            })
        });
        if (res.ok) {
            datosVideoActual = await res.json();
            temaOriginalRedactado = tema;
            abrirModalGuion(datosVideoActual);
        } else {
            const err = await res.json();
            alert(`Error redactando guión: ${err.detail || "Error desconocido"}`);
        }
    } catch (e) {
        alert("Error al conectar con la API de Gemini.");
    } finally {
        btnRedactar.disabled  = false;
        btnRedactar.innerText = "🧠 REDACTAR GUION E IDEAS (GEMINI)";
    }
});

// ─── MODAL GUIÓN ──────────────────────────────────────────────────────────
function abrirModalGuion(datos) {
    modalTitulosContainer.innerHTML = "";
    datos.titulos.forEach((t, idx) => {
        const card = document.createElement("div");
        card.className = "title-option-card" + (idx === 0 ? " selected" : "");
        card.innerText = t;
        card.addEventListener("click", () => {
            document.querySelectorAll(".title-option-card").forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            tituloSeleccionadoModal = t;
        });
        modalTitulosContainer.appendChild(card);
    });
    tituloSeleccionadoModal = datos.titulos[0];
    modalTextoMinia.value   = datos.texto_miniatura;
    modalGuionTexto.value   = datos.guion_locucion;
    actualizarContadorPalabras();
    modalGuion.style.display = "flex";
}

modalGuionTexto.addEventListener("input", actualizarContadorPalabras);

btnGuardarGuion.addEventListener("click", () => {
    if (!datosVideoActual) return;
    datosVideoActual.texto_miniatura = modalTextoMinia.value.trim();
    datosVideoActual.guion_locucion  = modalGuionTexto.value.trim();
    
    const index = datosVideoActual.titulos.indexOf(tituloSeleccionadoModal);
    if (index > -1) datosVideoActual.titulos.splice(index, 1);
    datosVideoActual.titulos.unshift(tituloSeleccionadoModal);
    
    const temaNuevo   = tituloSeleccionadoModal;
    const temaOriginal = temaOriginalRedactado || temaManual.value;
    temaManual.value   = temaNuevo;
    modalGuion.style.display = "none";
    
    actualizarGuionEnServidor(temaOriginal, temaNuevo, datosVideoActual);
    temaOriginalRedactado = temaNuevo;
});

async function actualizarGuionEnServidor(temaOriginal, temaNuevo, datos) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/guion/guardar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tema_original: temaOriginal, tema_nuevo: temaNuevo, datos })
        });
        if (res.ok) console.log("💾 Guion actualizado en servidor.");
    } catch (e) { console.error("Error al sincronizar guion:", e); }
}

const cerrarModal = () => { modalGuion.style.display = "none"; };
btnCloseModal.addEventListener("click", cerrarModal);
btnCancelarGuion.addEventListener("click", cerrarModal);

// ─── PRODUCIR ──────────────────────────────────────────────────────────────
btnProducir.addEventListener("click", async () => {
    datosClonados = { es: null, en: null, pt: null };
    idiomaActual  = 'es';
    activeFolderName = "";
    
    ["btn-lang-en","btn-lang-pt","btn-prev-en","btn-prev-pt"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });
    if (downloadVideoBtn) downloadVideoBtn.style.display = "none";
    ["download-opc1-btn","download-opc2-btn","download-opc3-btn"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });

    const tema    = temaManual.value.trim();
    const urlComfy = runpodUrl.value.trim();
    if (!tema)     { alert("Por favor establece el Tema del video."); return; }
    if (!urlComfy) { alert("Escribe la URL del Proxy de RunPod."); return; }
    
    const clonarIdiomas = [];
    if (document.getElementById("clone-en")?.checked) clonarIdiomas.push("en");
    if (document.getElementById("clone-pt")?.checked) clonarIdiomas.push("pt");

    const bodyPayload = {
        tema, url_runpod: urlComfy,
        voz:             selectVoz.value,
        estilo_video:    selectEstilo.value,
        orientacion:     selectOrientacion.value,
        musica_genero:   selectMusica.value,
        competidor_video_id: competidorVideoIdInput.value.trim() || null,
        sub_fuente:      document.getElementById("select-sub-fuente").value,
        sub_color_iluminado: document.getElementById("select-sub-color-iluminado").value,
        sub_color_fondo: document.getElementById("select-sub-color-fondo").value,
        sub_animacion:   document.getElementById("select-sub-animacion").value,
        sub_size:        parseInt(document.getElementById("select-sub-size").value) || 64,
        sub_outline:     parseInt(document.getElementById("select-sub-outline").value) || 3,
        sub_align:       document.getElementById("select-sub-align").value,
        sub_max_words:   document.getElementById("select-sub-max-words").value,
        sub_margin_v:    parseInt(document.getElementById("select-sub-margin-v").value) || 150,
        video_quality:   document.getElementById("select-video-quality").value,
        tono_voz:        document.getElementById("select-sub-pitch").value,
        velocidad_voz:   document.getElementById("select-sub-rate").value,
        volumen_musica:  parseFloat(document.getElementById("select-volumen-musica").value),
        clonar_idiomas:  clonarIdiomas
    };
    
    btnProducir.disabled  = true;
    btnProducir.innerText = "⏳ PROCESANDO EN RunPod...";
    
    try {
        consoleOutput.innerHTML = '<div class="log-line system">[SISTEMA] Conectando con servidor local de producción...</div>';
        const res = await fetch(`${API_BASE_URL}/api/producir`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyPayload)
        });
        if (res.ok) {
            const data = await res.json();
            console.log(data);
        } else {
            const err = await res.json();
            alert(`Error de producción: ${err.detail || "Error en el servidor"}`);
            btnProducir.disabled = false;
        }
    } catch (e) {
        alert("No se pudo conectar con el servidor local para iniciar la producción.");
        btnProducir.disabled = false;
    }
});

// ─── LIMPIAR LOG ───────────────────────────────────────────────────────────
btnLimpiarLog.addEventListener("click", async () => {
    try {
        await fetch(`${API_BASE_URL}/api/status/clear`, { method: "POST" });
        consoleOutput.innerHTML = '<div class="log-line system">[SISTEMA] Consola limpia.</div>';
    } catch (e) {}
});

// ─── LIVE PREVIEW SUBTÍTULOS ───────────────────────────────────────────────
function actualizarSubtitulosLivePreview() {
    const previewContainer = document.getElementById("sub-preview-display");
    if (!previewContainer) return;
    
    const sizeVal    = document.getElementById("select-sub-size").value;
    const outlineVal = document.getElementById("select-sub-outline").value;
    const marginVVal = document.getElementById("select-sub-margin-v").value;
    
    document.getElementById("val-sub-size").innerText    = `${sizeVal} pt`;
    document.getElementById("val-sub-outline").innerText = `${outlineVal} px`;
    document.getElementById("val-sub-margin-v").innerText = `${marginVVal} px`;
    
    const font       = document.getElementById("select-sub-fuente").value;
    const colorInact = document.getElementById("select-sub-color-fondo").value;
    const alignVal   = document.getElementById("select-sub-align").value;
    
    const cssColorMap = {
        white:"#ffffff", gray:"#aaaaaa", yellow:"#ffff00",
        red:"#ff3333",   green:"#39ff14", cyan:"#00ffff", magenta:"#ff00ff"
    };
    const colInactiveHex = cssColorMap[colorInact] || "#ffffff";
    
    previewContainer.style.fontFamily   = `"${font}", "Arial Black", sans-serif`;
    previewContainer.style.fontSize     = `${sizeVal * 0.5}px`;
    previewContainer.style.justifyContent = alignVal.includes("Centrado") ? "center"
        : alignVal.includes("Izquierda") ? "flex-start" : "flex-end";
    previewContainer.style.bottom       = `${marginVVal * 0.12}px`;
    
    const out = parseInt(outlineVal);
    let shadowStr = "";
    if (out > 0) {
        for (let x = -out; x <= out; x++)
            for (let y = -out; y <= out; y++)
                if (x !== 0 || y !== 0) shadowStr += `${x}px ${y}px 0px #000, `;
        shadowStr = shadowStr.slice(0, -2);
    } else { shadowStr = "none"; }
    
    previewContainer.querySelectorAll(".preview-word").forEach(w => {
        w.style.color = colInactiveHex;
        w.style.textShadow = shadowStr;
        w.style.transform  = "scale(1)";
        w.style.transition = "all 0.2s ease";
    });
}

let subtitlePreviewInterval = null;
function iniciarAnimacionLivePreview() {
    if (subtitlePreviewInterval) clearInterval(subtitlePreviewInterval);
    let activeIndex = 0;
    const previewContainer = document.getElementById("sub-preview-display");
    if (!previewContainer) return;
    
    subtitlePreviewInterval = setInterval(() => {
        const words = previewContainer.querySelectorAll(".preview-word");
        if (words.length === 0) return;
        
        const colorInact  = document.getElementById("select-sub-color-fondo").value;
        const colorActive = document.getElementById("select-sub-color-iluminado").value;
        const animacion   = document.getElementById("select-sub-animacion").value;
        const cssColorMap = {
            white:"#ffffff", gray:"#aaaaaa", yellow:"#ffff00",
            red:"#ff3333",   green:"#39ff14", cyan:"#00ffff", magenta:"#ff00ff"
        };
        const colInactiveHex = cssColorMap[colorInact]  || "#ffffff";
        const colActiveHex   = cssColorMap[colorActive] || "#ffff00";
        
        words.forEach(w => { w.style.color = colInactiveHex; w.style.transform = "scale(1)"; });
        
        if (animacion === "karaoke") {
            for (let i = 0; i <= activeIndex; i++)
                if (words[i]) words[i].style.color = colActiveHex;
        } else if (animacion === "pop") {
            if (words[activeIndex]) {
                words[activeIndex].style.color = colActiveHex;
                words[activeIndex].style.transform = "scale(1.15)";
            }
        }
        activeIndex = (activeIndex + 1) % (words.length + 1);
    }, 450);
}

function actualizarCompetitorThumbPreview() {
    const container = document.getElementById("competitor-thumb-preview-container");
    const img       = document.getElementById("competitor-thumb-img");
    if (!competidorVideoIdInput || !container || !img) return;
    const id = competidorVideoIdInput.value.trim();
    if (id && id.length >= 8) {
        img.src = `https://img.youtube.com/vi/${id}/maxresdefault.jpg`;
        container.style.display = "block";
    } else {
        container.style.display = "none";
    }
}

function actualizarAspectoSimulador() {
    const screen = document.getElementById("video-simulator-screen");
    const badge  = document.getElementById("simulator-aspect-badge");
    if (!screen || !badge || !selectOrientacion) return;
    if (selectOrientacion.value === "vertical") {
        screen.style.width = "220px";
        screen.style.aspectRatio = "9/16";
        badge.innerText = "VERTICAL (9:16)";
        badge.style.background = "#e11d48";
    } else {
        screen.style.width = "100%";
        screen.style.aspectRatio = "16/9";
        badge.innerText = "HORIZONTAL (16:9)";
        badge.style.background = "#ff0000";
    }
}

// ============================================================
// 🔍  MARKETPLACE — BÚSQUEDA YOUTUBE CON FILTRO IA/FACELESS
// ============================================================
const btnBuscarYoutube = document.getElementById("btn-buscar-youtube");

if (btnBuscarYoutube) {
    btnBuscarYoutube.addEventListener("click", async () => {
        const searchQueryInput  = document.getElementById("search-query");
        const searchDateSelect  = document.getElementById("search-date");
        const searchOrderSelect = document.getElementById("search-order");
        const searchLangSelect  = document.getElementById("search-lang");
        const searchDurationSelect = document.getElementById("search-duration");
        const searchLimitSelect = document.getElementById("search-limit");
        const filterIA          = document.getElementById("filter-ia-faceless");
        
        const searchResultsContainer = document.getElementById("search-results-container");
        const searchResultsGrid      = document.getElementById("search-results-grid");
        
        let query = searchQueryInput.value.trim();
        if (!query) { alert("Por favor ingresa un término o nicho de búsqueda."); return; }
        
        // ── Filtro IA/Faceless: enriquecer la query ────────────────────────
        const soloIA = filterIA ? filterIA.checked : false;
        if (soloIA) {
            query += ' ("AI voiceover" OR "voz en off" OR "faceless" OR "text to speech" OR "IA" OR "voice over" OR "narrated" OR "TTS")';
        }
        
        btnBuscarYoutube.disabled = true;
        btnBuscarYoutube.innerText = "⏳ BUSCANDO TENDENCIAS...";
        
        searchResultsGrid.innerHTML = `
            <div class="search-loader-container">
                <div class="spinner-glow"></div>
                <div class="loader-text">
                    ${soloIA
                        ? "🤖 Filtrando canales Faceless e IA con voz en off..."
                        : "Buscando en la API oficial de YouTube, rastreando estadísticas de canales, calculando Outlier Ratios y estimando ingresos del nicho..."}
                </div>
            </div>
        `;
        searchResultsContainer.style.display = "block";
        
        try {
            const res = await fetch(`${API_BASE_URL}/api/nicho/buscar`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query,
                    fecha:   searchDateSelect.value,
                    orden:   searchOrderSelect.value,
                    limite:  parseInt(searchLimitSelect.value),
                    idioma:  searchLangSelect.value,
                    duracion: searchDurationSelect.value,
                    solo_ia: soloIA
                })
            });
            
            if (res.ok) {
                const data = await res.json();
                if (data.videos && data.videos.length > 0) {
                    mostrarResultadosMarketplace(data.videos, searchResultsGrid, searchResultsContainer, soloIA);
                } else {
                    searchResultsGrid.innerHTML = `<div style="text-align:center; padding: 40px; color:#94a3b8; font-style:italic;">No se encontraron videos populares con los filtros seleccionados.</div>`;
                }
            } else {
                const err = await res.json();
                searchResultsGrid.innerHTML = `<div style="text-align:center; padding: 40px; color:#f87171; font-weight:bold;">Error de búsqueda: ${err.detail || "Error desconocido"}</div>`;
            }
        } catch (e) {
            searchResultsGrid.innerHTML = `<div style="text-align:center; padding: 40px; color:#f87171; font-weight:bold;">Error de conexión. Asegúrate de que el servidor local esté ejecutándose.</div>`;
        } finally {
            btnBuscarYoutube.disabled = false;
            btnBuscarYoutube.innerText = "🔍 BUSCAR VIDEOS GANADORES";
        }
    });
}

// ─── Formatear fecha relativa ──────────────────────────────────────────────
function formatearFechaRelativa(fechaISO) {
    if (!fechaISO) return "Desconocida";
    try {
        const fecha = new Date(fechaISO);
        const ahora = new Date();
        const diffMs = ahora - fecha;
        const diffDias  = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        const diffMeses = Math.floor(diffDias / 30);
        const diffAnios = Math.floor(diffDias / 365);
        if (diffDias < 1) return "Hoy";
        if (diffDias < 7)  return `Hace ${diffDias}d`;
        if (diffDias < 31) return `Hace ${Math.floor(diffDias/7)}sem`;
        if (diffMeses < 12) return `Hace ${diffMeses}m`;
        return `Hace ${diffAnios}a`;
    } catch { return "Desconocida"; }
}

function formatearFechaCorta(fechaISO) {
    if (!fechaISO) return "—";
    try {
        return new Date(fechaISO).toLocaleDateString("es-ES", { year:"numeric", month:"short", day:"numeric" });
    } catch { return "—"; }
}

// ─── Detectar si el canal es posiblemente IA/Faceless ─────────────────────
function esPosiblementeIA(v) {
    const keywords = ["ai","artificial","faceless","voice","tts","narrat","voz","text to speech",
                      "generated","robot","neural","automatiz","educa","salud","tips","datos","top"];
    const titleLow = (v.title || "").toLowerCase();
    const chanLow  = (v.channelTitle || "").toLowerCase();
    return keywords.some(k => titleLow.includes(k) || chanLow.includes(k));
}

// ─── RENDERIZAR CARDS HORIZONTALES ────────────────────────────────────────
function mostrarResultadosMarketplace(videos, resultsGrid, resultsContainer, soloIA) {
    resultsGrid.innerHTML = "";
    
    videos.forEach(v => {
        const card = document.createElement("div");
        card.className = "marketplace-card";
        
        // Calcular colores del outlier
        const isHot      = (v.outlier_ratio || 0) >= 150;
        const outlierCls = isHot ? "mc-badge-outlier-hot" : "mc-badge-outlier-normal";
        const outlierTxt = `${(v.outlier_ratio || 0).toFixed(0)}% ${isHot ? "🔥" : "📊"}`;
        
        const fechaVideo    = formatearFechaRelativa(v.publishedAt);
        const posibleIA     = soloIA || esPosiblementeIA(v);
        
        card.innerHTML = `
            <!-- THUMBNAIL -->
            <div class="mc-thumb-col">
                <img src="${v.thumbnail_url || ''}" alt="thumb" loading="lazy" onerror="this.src='placeholder_minia.png'">
                <span class="mc-duration-badge">${v.duration_fmt || '—'}</span>
                ${posibleIA ? '<span class="mc-ai-badge">🤖 FACELESS/IA</span>' : ''}
                <div class="mc-play-overlay">
                    <div class="mc-play-icon">▶</div>
                </div>
            </div>

            <!-- INFO -->
            <div class="mc-info-col">
                <div>
                    <div class="mc-title"></div>
                    <div class="mc-channel">
                        <span>📺</span>
                        <span class="mc-channel-name-txt"></span>
                        <span class="mc-channel-dot"></span>
                        <span>${v.subscribers_formatted || '—'} subs</span>
                    </div>
                    <div class="mc-badges">
                        <span class="mc-badge mc-badge-views">👁️ ${v.views_formatted || '—'}</span>
                        <span class="mc-badge ${outlierCls}">🚀 Outlier ${outlierTxt}</span>
                        <span class="mc-badge mc-badge-earn">💰 $${(v.earnings_min||0).toFixed(0)}–$${(v.earnings_max||0).toFixed(0)}</span>
                        <span class="mc-badge mc-badge-subs">👥 ${v.subscribers_formatted || '—'}</span>
                        <span class="mc-badge mc-badge-date">📅 ${fechaVideo}</span>
                    </div>
                </div>
                <div class="mc-card-footer">
                    <button class="mc-stats-btn">📊 Ver Estadísticas</button>
                    <button class="mc-select-btn">👉 Usar este Tema</button>
                </div>
            </div>
        `;
        
        // Asignar textos de manera segura (evitar XSS)
        card.querySelector(".mc-title").textContent          = v.title || "(Sin título)";
        card.querySelector(".mc-channel-name-txt").textContent = v.channelTitle || "Canal desconocido";
        
        // Botón "Ver Estadísticas" abre el popup
        card.querySelector(".mc-stats-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            abrirModalStats(v);
        });
        
        // Clic en la card también abre stats
        card.addEventListener("click", () => abrirModalStats(v));
        
        // Botón "Usar este Tema"
        card.querySelector(".mc-select-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            seleccionarTema(v);
        });
        
        resultsGrid.appendChild(card);
    });
    
    resultsContainer.style.display = "block";
}

function seleccionarTema(v) {
    if (temaManual)            temaManual.value = v.title;
    if (competidorVideoIdInput) {
        competidorVideoIdInput.value = v.id;
        actualizarCompetitorThumbPreview();
    }
    // Scroll suave al paso 1
    const cardPaso1 = document.getElementById("card-paso1");
    if (cardPaso1) cardPaso1.scrollIntoView({ behavior: "smooth", block: "center" });
    
    // Toast de confirmación
    mostrarToast(`✅ Tema cargado: "${v.title.substring(0, 50)}..."`);
}

// ─── TOAST NOTIFICATION ───────────────────────────────────────────────────
function mostrarToast(msg) {
    const existing = document.getElementById("toast-notif");
    if (existing) existing.remove();
    
    const toast = document.createElement("div");
    toast.id = "toast-notif";
    toast.style.cssText = `
        position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid rgba(16,185,129,0.4);
        color: #34d399; font-size: 0.85rem; font-weight: 700;
        padding: 12px 22px; border-radius: 30px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5), 0 0 12px rgba(16,185,129,0.2);
        z-index: 9999; animation: fadeInUp 0.3s ease;
        font-family: 'Inter', sans-serif; white-space: nowrap;
    `;
    toast.textContent = msg;
    
    // Inyectar keyframe una vez
    if (!document.getElementById("toast-keyframes")) {
        const style = document.createElement("style");
        style.id = "toast-keyframes";
        style.textContent = `
            @keyframes fadeInUp { from { opacity:0; transform: translateX(-50%) translateY(12px); } to { opacity:1; transform: translateX(-50%) translateY(0); } }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

// ============================================================
// 📊  MODAL DE ESTADÍSTICAS + GRÁFICAS (Chart.js)
// ============================================================
let currentVideoData = null;

function abrirModalStats(v) {
    currentVideoData = v;
    const modal = document.getElementById("modal-stats");
    if (!modal) return;
    
    // Título y canal
    document.getElementById("stats-modal-title").textContent   = v.title || "Sin título";
    document.getElementById("stats-modal-channel").textContent = `📺 ${v.channelTitle || "Canal desconocido"}`;
    
    // Thumbnail
    const imgEl = document.getElementById("stats-thumb");
    if (imgEl) {
        imgEl.src = v.thumbnail_url || "";
        imgEl.onerror = () => imgEl.src = "placeholder_minia.png";
    }
    
    // Duración
    const durBadge = document.getElementById("stats-duration-badge");
    if (durBadge) durBadge.textContent = v.duration_fmt || "—";
    
    // Links de acción
    const videoUrl  = `https://www.youtube.com/watch?v=${v.id}`;
    const channelUrl = v.channelId ? `https://www.youtube.com/channel/${v.channelId}`
                                   : `https://www.youtube.com/@${encodeURIComponent(v.channelTitle || "")}`;
    document.getElementById("stats-btn-video").href = videoUrl;
    document.getElementById("stats-btn-canal").href = channelUrl;
    
    // Métricas
    document.getElementById("stats-views").textContent   = v.views_formatted       || "—";
    document.getElementById("stats-subs").textContent    = v.subscribers_formatted || "—";
    document.getElementById("stats-outlier").textContent = `${(v.outlier_ratio || 0).toFixed(0)}%`;
    document.getElementById("stats-earn").textContent    = `$${(v.earnings_min||0).toFixed(0)}–$${(v.earnings_max||0).toFixed(0)}`;
    document.getElementById("stats-video-date").textContent   = formatearFechaCorta(v.publishedAt);
    document.getElementById("stats-channel-date").textContent = v.channelCreatedAt
        ? formatearFechaCorta(v.channelCreatedAt) : "No disponible";
    
    // Badge IA
    const iaBadge = document.getElementById("stats-ia-badge");
    if (iaBadge) iaBadge.style.display = esPosiblementeIA(v) ? "block" : "none";
    
    // KPIs
    const views     = v.viewCount || 0;
    const subs      = v.subscriberCount || 0;
    const outlier   = v.outlier_ratio || 0;
    
    // Velocidad: vistas/día desde publicación
    let velText = "—";
    if (v.publishedAt && views > 0) {
        const diasDesde = Math.max(1, Math.floor((Date.now() - new Date(v.publishedAt)) / (1000*60*60*24)));
        const vPorDia   = Math.round(views / diasDesde);
        velText = vPorDia >= 1000 ? `${(vPorDia/1000).toFixed(1)}K/día` : `${vPorDia}/día`;
    }
    document.getElementById("kpi-velocity").textContent = velText;
    
    // Potencial de replicación
    let potencial = "Bajo";
    if (outlier >= 300) potencial = "🔥 Extremo";
    else if (outlier >= 200) potencial = "🚀 Muy Alto";
    else if (outlier >= 150) potencial = "⭐ Alto";
    else if (outlier >= 100) potencial = "📈 Bueno";
    document.getElementById("kpi-potential").textContent = potencial;
    
    // Ratio vistas/subs
    const ratio = subs > 0 ? (views / subs).toFixed(1) : "—";
    document.getElementById("kpi-ratio").textContent = ratio !== "—" ? `${ratio}x` : "—";
    
    // Duración
    document.getElementById("kpi-duration").textContent = v.duration_fmt || "—";
    
    // Botón "Usar este tema"
    const btnSelect = document.getElementById("stats-btn-select");
    if (btnSelect) {
        btnSelect.onclick = () => {
            seleccionarTema(v);
            cerrarModalStats();
        };
    }
    
    modal.style.display = "flex";
    
    // Renderizar gráficas con pequeño delay para que el canvas esté visible
    setTimeout(() => {
        renderizarGraficas(v);
    }, 80);
}

window.cerrarModalStats = function(e) {
    if (e && e.target !== document.getElementById("modal-stats")) return;
    const modal = document.getElementById("modal-stats");
    if (modal) modal.style.display = "none";
    
    // Destruir instancias previas de Chart.js
    if (chartVideoViews)  { chartVideoViews.destroy();  chartVideoViews  = null; }
    if (chartChannelGrowth) { chartChannelGrowth.destroy(); chartChannelGrowth = null; }
};

// ─── GENERAR DATOS DE CRECIMIENTO SIMULADOS ───────────────────────────────
function generarCurvaCrecimiento(viewsTotal, publishedAt, outlierRatio, puntos = 12) {
    const dias = [];
    const vistas = [];
    
    const ahora  = new Date();
    const inicio = publishedAt ? new Date(publishedAt) : new Date(ahora.getTime() - 90 * 864e5);
    const diasTotales = Math.max(1, Math.floor((ahora - inicio) / (1000*60*60*24)));
    
    // Curva sigmoide + spike viral
    const spikeEn = Math.min(7, Math.floor(diasTotales * 0.1)); // el spike ocurre temprano
    const k = (outlierRatio || 100) / 100; // factor viral
    
    for (let i = 0; i <= puntos; i++) {
        const frac = i / puntos;
        const diaActual = Math.floor(frac * diasTotales);
        dias.push(frac < 0.05 ? "Día 0" : frac < 0.5
            ? `Día ${diaActual}`
            : frac === 1 ? "Hoy" : `Día ${diaActual}`);
        
        // Modelo de crecimiento: sigmoid con boost viral al inicio
        let progreso;
        if (frac <= spikeEn / diasTotales) {
            // Spike viral exponencial al principio
            progreso = Math.pow(frac / (spikeEn / diasTotales), 0.5) * 0.45 * k;
        } else {
            // Decaimiento gradual logarítmico
            const fracPost = (frac - spikeEn / diasTotales) / (1 - spikeEn / diasTotales);
            progreso = 0.45 * k + (1 - 0.45 * k) * Math.log(1 + fracPost * 9) / Math.log(10);
        }
        
        progreso = Math.min(1, progreso);
        const ruido = (Math.random() - 0.5) * 0.03;
        vistas.push(Math.max(0, Math.round((progreso + ruido) * viewsTotal)));
    }
    
    // Asegurar que el último valor sea el total real
    vistas[vistas.length - 1] = viewsTotal;
    return { dias, vistas };
}

function generarCrecimientoCanal(subsTotal, publishedAt, puntos = 12) {
    const meses = [];
    const suscriptores = [];
    
    const ahora  = new Date();
    const inicio = publishedAt ? new Date(publishedAt) : new Date(ahora.getTime() - 365 * 864e5);
    const mesTotales = Math.max(1, Math.floor((ahora - inicio) / (1000*60*60*24*30)));
    
    for (let i = 0; i <= puntos; i++) {
        const frac = i / puntos;
        const mesActual = Math.floor(frac * mesTotales);
        meses.push(mesActual === 0 ? "Inicio" : mesActual >= mesTotales ? "Hoy" : `Mes ${mesActual}`);
        
        // Crecimiento logarítmico (realista para canales)
        const progreso = Math.log(1 + frac * 9) / Math.log(10);
        const ruido    = (Math.random() - 0.5) * 0.04;
        suscriptores.push(Math.max(0, Math.round((progreso + ruido) * subsTotal)));
    }
    suscriptores[suscriptores.length - 1] = subsTotal;
    return { meses, suscriptores };
}

// ─── RENDERIZAR GRÁFICAS CON CHART.JS ─────────────────────────────────────
function renderizarGraficas(v) {
    // Limpiar instancias previas
    if (chartVideoViews)    { chartVideoViews.destroy();    chartVideoViews    = null; }
    if (chartChannelGrowth) { chartChannelGrowth.destroy(); chartChannelGrowth = null; }
    
    const viewsTotal = v.viewCount       || parseInt((v.views_formatted||"0").replace(/[KMkm,. ]/g,'')) * 1000 || 50000;
    const subsTotal  = v.subscriberCount || parseInt((v.subscribers_formatted||"0").replace(/[KMkm,. ]/g,'')) * 1000 || 5000;
    
    // ── Gráfica 1: Crecimiento de vistas del video ─────────────────────
    const curvaVistas = generarCurvaCrecimiento(viewsTotal, v.publishedAt, v.outlier_ratio, 10);
    
    const ctx1 = document.getElementById("chart-video-views");
    if (ctx1) {
        chartVideoViews = new Chart(ctx1, {
            type: "line",
            data: {
                labels: curvaVistas.dias,
                datasets: [{
                    label: "Vistas",
                    data:  curvaVistas.vistas,
                    borderColor: "rgba(56, 189, 248, 0.9)",
                    backgroundColor: createGradient(ctx1, "rgba(56,189,248,0.35)", "rgba(56,189,248,0.0)"),
                    borderWidth: 2,
                    tension: 0.45,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: "#38bdf8",
                    pointBorderColor: "#0f172a",
                    pointBorderWidth: 2,
                    pointHoverRadius: 6,
                }]
            },
            options: chartOptions("Vistas", v => {
                const val = v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(1)}K` : v;
                return val;
            })
        });
    }
    
    // ── Gráfica 2: Crecimiento de suscriptores del canal ───────────────
    const curvaCanal = generarCrecimientoCanal(subsTotal, v.channelCreatedAt || v.publishedAt, 10);
    
    const ctx2 = document.getElementById("chart-channel-growth");
    if (ctx2) {
        chartChannelGrowth = new Chart(ctx2, {
            type: "line",
            data: {
                labels: curvaCanal.meses,
                datasets: [{
                    label: "Suscriptores",
                    data:  curvaCanal.suscriptores,
                    borderColor: "rgba(16, 185, 129, 0.9)",
                    backgroundColor: createGradient(ctx2, "rgba(16,185,129,0.35)", "rgba(16,185,129,0.0)"),
                    borderWidth: 2,
                    tension: 0.45,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: "#10b981",
                    pointBorderColor: "#0f172a",
                    pointBorderWidth: 2,
                    pointHoverRadius: 6,
                }]
            },
            options: chartOptions("Suscriptores", v => {
                return v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(1)}K` : v;
            })
        });
    }
}

function createGradient(canvas, colorTop, colorBottom) {
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.offsetHeight || 160);
    gradient.addColorStop(0, colorTop);
    gradient.addColorStop(1, colorBottom);
    return gradient;
}

function chartOptions(label, tickFormatter) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: "rgba(15, 23, 42, 0.95)",
                borderColor: "rgba(255,255,255,0.08)",
                borderWidth: 1,
                titleColor: "#94a3b8",
                bodyColor: "#f1f5f9",
                bodyFont: { weight: "bold", family: "'JetBrains Mono', monospace" },
                padding: 10,
                callbacks: {
                    label: ctx => {
                        const val = ctx.parsed.y;
                        const fmt = val >= 1e6 ? `${(val/1e6).toFixed(2)}M`
                                  : val >= 1e3 ? `${(val/1e3).toFixed(1)}K`
                                  : val.toLocaleString();
                        return ` ${label}: ${fmt}`;
                    }
                }
            }
        },
        scales: {
            x: {
                grid:  { color: "rgba(255,255,255,0.04)", drawBorder: false },
                ticks: { color: "#475569", font: { size: 9, family: "'Inter', sans-serif" }, maxRotation: 0 }
            },
            y: {
                grid:  { color: "rgba(255,255,255,0.04)", drawBorder: false },
                ticks: {
                    color: "#475569",
                    font: { size: 9, family: "'Inter', sans-serif" },
                    callback: tickFormatter
                }
            }
        }
    };
}

// ─── Copiar al portapapeles ────────────────────────────────────────────────
window.copiarTexto = function(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.select();
    el.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(el.value);
    const btn = el.nextElementSibling;
    if (btn) {
        const origText = btn.innerText;
        btn.innerText = "¡Copiado!";
        btn.style.background = "#10b981";
        btn.style.color = "white";
        setTimeout(() => { btn.innerText = origText; btn.style.background=""; btn.style.color=""; }, 1500);
    }
};

// ─── REGENERAR MINIATURA ───────────────────────────────────────────────────
if (btnRegenerarMinia) {
    btnRegenerarMinia.addEventListener("click", async () => {
        const tema    = temaManual.value.trim();
        const urlComfy = runpodUrl.value.trim();
        if (!tema)     { alert("No hay un tema de video establecido."); return; }
        if (!urlComfy) { alert("Escribe la URL del Proxy de RunPod."); return; }
        
        btnRegenerarMinia.disabled = true;
        btnRegenerarMinia.innerText = "⏳ RE-GENERANDO...";
        
        try {
            const res = await fetch(`${API_BASE_URL}/api/miniatura/regenerar`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tema, url_runpod: urlComfy, competidor_video_id: competidorVideoIdInput.value.trim() || null })
            });
            if (res.ok) {
                const data = await res.json();
                if (data.status === "need_confirmation") {
                    mostrarModalConfirmacionRunpod(
                        data.message,
                        async () => {
                            btnRegenerarMinia.innerText = "⏳ ENCOLANDO EN RUNPOD...";
                            const res2 = await fetch(`${API_BASE_URL}/api/miniatura/regenerar`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ tema, url_runpod: urlComfy, competidor_video_id: competidorVideoIdInput.value.trim() || null, forzar_comfy: true })
                            });
                            if (res2.ok) {
                                mostrarToast("🎨 ¡Miniatura generada en RunPod con éxito!");
                                cambiarIdiomaResultados(idiomaActual);
                            } else {
                                alert("Error al re-generar miniatura en RunPod.");
                            }
                            btnRegenerarMinia.disabled = false;
                            btnRegenerarMinia.innerText = "🔄 Re-generar Solo Miniatura";
                        },
                        async () => {
                            btnRegenerarMinia.click();
                        },
                        () => {
                            btnRegenerarMinia.disabled = false;
                            btnRegenerarMinia.innerText = "🔄 Re-generar Solo Miniatura";
                        }
                    );
                    return;
                } else {
                    mostrarToast("🎨 ¡Miniatura re-generada con éxito!");
                    cambiarIdiomaResultados(idiomaActual);
                }
            } else {
                const err = await res.json();
                alert(`Error al regenerar miniatura: ${err.detail || "Error desconocido"}`);
            }
        } catch (e) {
            alert("Error de conexión al regenerar miniatura.");
        } finally {
            btnRegenerarMinia.disabled = false;
            btnRegenerarMinia.innerText = "🔄 Re-generar Solo Miniatura";
        }
    });
}

function mostrarMiniaturasManuales(data) {
    const box = document.getElementById("manual-results-box");
    box.style.display = "block";
    
    const img1 = document.getElementById("manual-img-opc1");
    const img2 = document.getElementById("manual-img-opc2");
    const img3 = document.getElementById("manual-img-opc3");
    
    img1.src = `${API_BASE_URL}${data.opcion1}`;
    img2.src = `${API_BASE_URL}${data.opcion2}`;
    img3.src = `${API_BASE_URL}${data.opcion3}`;
    
    document.getElementById("manual-download-opc1").href = `${API_BASE_URL}${data.opcion1}`;
    document.getElementById("manual-download-opc2").href = `${API_BASE_URL}${data.opcion2}`;
    document.getElementById("manual-download-opc3").href = `${API_BASE_URL}${data.opcion3}`;
}

// ─── CREADOR DE MINIATURAS MANUAL ──────────────────────────────────────────
const btnCrearMiniaManual = document.getElementById("btn-crear-minia-manual");
if (btnCrearMiniaManual) {
    btnCrearMiniaManual.addEventListener("click", async () => {
        const promptFondo = document.getElementById("manual-prompt-fondo").value.trim();
        const textoClick = document.getElementById("manual-texto-click").value.trim();
        const elemClave = document.getElementById("manual-elem-clave").value.trim();
        const compId = document.getElementById("manual-comp-id").value.trim();
        
        if (!promptFondo) {
            alert("Por favor ingresa una idea o prompt para el fondo de la miniatura.");
            return;
        }
        if (!textoClick) {
            alert("Por favor ingresa el texto clickbait de la miniatura.");
            return;
        }
        
        btnCrearMiniaManual.disabled = true;
        btnCrearMiniaManual.innerText = "⏳ GENERANDO MINIATURAS...";
        
        try {
            const res = await fetch(`${API_BASE_URL}/api/miniatura/crear_manual`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt_fondo: promptFondo,
                    texto_clickbait: textoClick,
                    elemento_clave: elemClave || null,
                    url_runpod: runpodUrl.value.trim(),
                    competidor_video_id: compId || null
                })
            });
            
            if (res.ok) {
                const data = await res.json();
                if (data.status === "need_confirmation") {
                    mostrarModalConfirmacionRunpod(
                        data.message,
                        async () => {
                            btnCrearMiniaManual.innerText = "⏳ ENCOLANDO EN RUNPOD...";
                            const res2 = await fetch(`${API_BASE_URL}/api/miniatura/crear_manual`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    prompt_fondo: promptFondo,
                                    texto_clickbait: textoClick,
                                    elemento_clave: elemClave || null,
                                    url_runpod: runpodUrl.value.trim(),
                                    competidor_video_id: compId || null,
                                    forzar_comfy: true
                                })
                            });
                            if (res2.ok) {
                                const data2 = await res2.json();
                                mostrarMiniaturasManuales(data2);
                                mostrarToast("🎨 ¡Miniaturas creadas en RunPod!");
                            } else {
                                alert("Error al crear miniatura en RunPod.");
                            }
                            btnCrearMiniaManual.disabled = false;
                            btnCrearMiniaManual.innerText = "🎨 GENERAR MINIATURAS HIGH-CTR";
                        },
                        async () => {
                            btnCrearMiniaManual.click();
                        },
                        () => {
                            btnCrearMiniaManual.disabled = false;
                            btnCrearMiniaManual.innerText = "🎨 GENERAR MINIATURAS HIGH-CTR";
                        }
                    );
                    return;
                } else {
                    mostrarMiniaturasManuales(data);
                    mostrarToast("🎨 ¡Miniaturas manuales generadas con éxito!");
                }
            } else {
                const err = await res.json();
                alert(`Error al crear miniatura: ${err.detail || "Error desconocido"}`);
            }
        } catch (e) {
            alert("Error de conexión al generar miniatura.");
        } finally {
            btnCrearMiniaManual.disabled = false;
            btnCrearMiniaManual.innerText = "🎨 GENERAR MINIATURAS HIGH-CTR";
        }
    });
}

// ─── INICIALIZACIÓN ────────────────────────────────────────────────────────
async function init() {
    const currentOrigin = window.location.origin;
    if (currentOrigin.includes("-5000.proxy.runpod.net")) {
        const comfyUrl = currentOrigin.replace("-5000.proxy.runpod.net", "-8188.proxy.runpod.net");
        if (runpodUrl) runpodUrl.value = comfyUrl;
    } else if (currentOrigin.includes("localhost") || currentOrigin.includes("127.0.0.1")) {
        try {
            const resConfig = await fetch(`${API_BASE_URL}/api/config`);
            if (resConfig.ok) {
                const configData = await resConfig.json();
                if (configData.pod_id) {
                    const comfyUrl = `https://${configData.pod_id}-8188.proxy.runpod.net`;
                    if (runpodUrl) runpodUrl.value = comfyUrl;
                }
            }
        } catch (e) { console.error("Error al cargar config de RunPod:", e); }
    }

    const savedUrls = localStorage.getItem("competidor_urls");
    if (savedUrls) competidorUrls.value = savedUrls;
    competidorUrls.addEventListener("input", () => {
        localStorage.setItem("competidor_urls", competidorUrls.value);
    });

    // Subtítulos live preview
    ["select-sub-fuente","select-sub-color-fondo","select-sub-color-iluminado","select-sub-animacion","select-sub-align","select-sub-max-words"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", () => { actualizarSubtitulosLivePreview(); iniciarAnimacionLivePreview(); });
    });

    ["select-sub-size","select-sub-outline","select-sub-margin-v"].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input",  () => actualizarSubtitulosLivePreview());
            el.addEventListener("change", () => { actualizarSubtitulosLivePreview(); iniciarAnimacionLivePreview(); });
        }
    });

    actualizarSubtitulosLivePreview();
    iniciarAnimacionLivePreview();

    if (competidorVideoIdInput) {
        competidorVideoIdInput.addEventListener("input", actualizarCompetitorThumbPreview);
        actualizarCompetitorThumbPreview();
    }

    if (selectOrientacion) {
        selectOrientacion.addEventListener("change", actualizarAspectoSimulador);
        actualizarAspectoSimulador();
    }

    // Cerrar modal stats al pulsar ESC
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            const modalStats = document.getElementById("modal-stats");
            if (modalStats && modalStats.style.display === "flex") cerrarModalStats();
            if (modalGuion && modalGuion.style.display === "flex") cerrarModal();
        }
    });

    const online = await verificarConexion();
    if (online) {
        pollStatus();
        pollingInterval = setInterval(() => { verificarConexion(); pollStatus(); }, 1500);
    } else {
        setTimeout(init, 3000);
    }
}

init();
