// ==========================================================================
// 🤖 LÓGICA DE CONTROL DE LA FÁBRICA DE VIDEOS v5.0
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

window.cambiarIdiomaResultados = function(lang) {
    idiomaActual = lang;
    
    // Cambiar clase active en los botones
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
    let opc1Url = `${API_BASE_URL}/outputs/${activeFolderName}/miniatura_opcion1.png?t=${t}`;
    
    // Mostrar/ocultar opciones de miniaturas 2 y 3 (solo disponibles en español)
    const colOpc2 = document.getElementById("thumb-img-opc2")?.closest(".thumbnail-item");
    const colOpc3 = document.getElementById("thumb-img-opc3")?.closest(".thumbnail-item");
    
    if (lang === "es") {
        if (colOpc2) colOpc2.style.display = "flex";
        if (colOpc3) colOpc3.style.display = "flex";
    } else {
        if (colOpc2) colOpc2.style.display = "none";
        if (colOpc3) colOpc3.style.display = "none";
        videoUrl = `${API_BASE_URL}/outputs/${activeFolderName}/video_final_${lang}.mp4?t=${t}`;
        opc1Url = `${API_BASE_URL}/outputs/${activeFolderName}/miniatura_final_${lang}.png?t=${t}`;
    }
    
    // Cargar video
    const playerSource = videoPlayer.querySelector("source");
    if (playerSource) {
        playerSource.src = videoUrl;
        videoPlayer.load();
        downloadVideoBtn.href = videoUrl;
        downloadVideoBtn.innerText = `📥 Descargar Video Final (${lang.toUpperCase()})`;
    }
    
    // Cargar miniatura opcion 1
    const imgOpc1 = document.getElementById("thumb-img-opc1");
    const btnOpc1 = document.getElementById("download-opc1-btn");
    if (imgOpc1) {
        imgOpc1.src = opc1Url;
        if (btnOpc1) {
            btnOpc1.href = opc1Url;
            btnOpc1.innerText = `Descargar Miniatura (${lang.toUpperCase()})`;
        }
    }
    
    // Cargar textos en YouTube Kit
    const vData = datosClonados[lang];
    if (vData) {
        document.getElementById("pub-titulo").value = vData.titulos ? vData.titulos[0] : "";
        document.getElementById("pub-descripcion").value = vData.descripcion || "";
        document.getElementById("pub-tags").value = vData.tags ? vData.tags.join(", ") : "";
    }
};

// Elementos del DOM
const serverStatus = document.getElementById("server-status");
const competidorUrls = document.getElementById("competidor-urls");
const btnRastrear = document.getElementById("btn-rastrear");
const containerSeleccionVideo = document.getElementById("container-seleccion-video");
const selectVideosVirales = document.getElementById("select-videos-virales");
const temaManual = document.getElementById("tema-manual");
const btnRedactar = document.getElementById("btn-redactar");
const selectDuracion = document.getElementById("select-duracion");

const runpodUrl = document.getElementById("runpod-url");
const selectVoz = document.getElementById("select-voz");
const selectEstilo = document.getElementById("select-estilo");
const selectOrientacion = document.getElementById("select-orientacion");
const selectMusica = document.getElementById("select-musica");
const competidorVideoIdInput = document.getElementById("competidor-video-id");
const btnProducir = document.getElementById("btn-producir");

const progressSpinner = document.getElementById("progress-spinner");
const progressEtapa = document.getElementById("progress-etapa");
const progressPorcentaje = document.getElementById("progress-porcentaje");
const progressBar = document.getElementById("progress-bar");
const consoleOutput = document.getElementById("console-output");
const btnLimpiarLog = document.getElementById("btn-limpiar-log");

const thumbnailImg = document.getElementById("thumbnail-img");
const videoPlayer = document.getElementById("video-player");
const downloadThumbBtn = document.getElementById("download-thumb-btn");
const downloadVideoBtn = document.getElementById("download-video-btn");
const btnRegenerarMinia = document.getElementById("btn-regenerar-minia");

// Modal de Guion
const modalGuion = document.getElementById("modal-guion");
const modalTitulosContainer = document.getElementById("modal-titulos-container");
const modalTextoMinia = document.getElementById("modal-texto-minia");
const modalGuionTexto = document.getElementById("modal-guion-texto");
const btnCloseModal = document.getElementById("btn-close-modal");
const btnCancelarGuion = document.getElementById("btn-cancelar-guion");
const modalWordCount = document.getElementById("modal-word-count");
const btnGuardarGuion = document.getElementById("btn-guardar-guion");

let tituloSeleccionadoModal = "";

function actualizarContadorPalabras() {
    const texto = modalGuionTexto.value || "";
    const palabras = texto.trim().split(/\s+/).filter(w => w.length > 0).length;
    if (modalWordCount) {
        modalWordCount.innerText = `Palabras: ${palabras}`;
    }
}

// 1. VERIFICAR CONEXIÓN CON BACKEND E INICIAR POLLING
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

// 2. POLLING DE ESTADO
async function pollStatus() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/status`);
        if (!res.ok) return;
        const data = await res.json();
        
        // Actualizar etapa y porcentaje
        progressEtapa.innerText = data.etapa;
        progressPorcentaje.innerText = `${data.progreso}%`;
        progressBar.style.width = `${data.progreso}%`;
        
        // Manejar ocupado/desocupado
        if (data.ocupado) {
            btnProducir.disabled = true;
            btnProducir.innerText = "⏳ PROCESANDO EN RunPod...";
            btnRedactar.disabled = true;
            btnRastrear.disabled = true;
            progressSpinner.style.display = "block";
        } else {
            btnProducir.disabled = false;
            btnProducir.innerText = "🚀 PRODUCIR VIDEO COMPLETO (1-CLIC)";
            btnRedactar.disabled = false;
            btnRastrear.disabled = false;
            progressSpinner.style.display = "none";
        }
        
        // Imprimir logs
        if (data.mensajes && data.mensajes.length > 0) {
            consoleOutput.innerHTML = "";
            data.mensajes.forEach(msg => {
                const line = document.createElement("div");
                line.className = "log-line";
                if (msg.includes("❌") || msg.includes("⚠️")) {
                    line.className += " error";
                } else if (msg.includes("✅") || msg.includes("🎉")) {
                    line.className += " success";
                } else if (msg.includes("🛰️") || msg.includes("🤖")) {
                    line.className += " system";
                }
                line.innerText = msg;
                consoleOutput.appendChild(line);
            });
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        
        // Si finalizó exitosamente, cargar assets generados
        if (data.etapa === "Completado" && data.directorio_salida) {
            const folderName = data.directorio_salida.split(/[\\/]/).pop();
            activeFolderName = folderName;
            
            // Cargar datos locales en español si no se han cargado
            if (!datosClonados.es) {
                datosClonados.es = data.datos_video || datosVideoActual;
            }
            
            // Mostrar u ocultar pestañas de idiomas
            const hasEn = data.clonar_idiomas && data.clonar_idiomas.includes("en");
            const hasPt = data.clonar_idiomas && data.clonar_idiomas.includes("pt");
            
            const tabEnPub = document.getElementById("btn-lang-en");
            const tabPtPub = document.getElementById("btn-lang-pt");
            const tabEnPrev = document.getElementById("btn-prev-en");
            const tabPtPrev = document.getElementById("btn-prev-pt");
            
            if (tabEnPub) tabEnPub.style.display = hasEn ? "inline-block" : "none";
            if (tabPtPub) tabPtPub.style.display = hasPt ? "inline-block" : "none";
            if (tabEnPrev) tabEnPrev.style.display = hasEn ? "inline-block" : "none";
            if (tabPtPrev) tabPtPrev.style.display = hasPt ? "inline-block" : "none";
            
            // Si clonar a Inglés está activado, intentar descargar los textos en inglés si no están cargados
            if (hasEn && !datosClonados.en) {
                try {
                    fetch(`${API_BASE_URL}/outputs/${folderName}/info_video_en.json`)
                        .then(r => r.json())
                        .then(json_en => {
                            datosClonados.en = json_en;
                            if (idiomaActual === "en") cambiarIdiomaResultados("en");
                        }).catch(e => {});
                } catch(e) {}
            }
            
            // Si clonar a Portugués está activado, intentar descargar los textos en portugués si no están cargados
            if (hasPt && !datosClonados.pt) {
                try {
                    fetch(`${API_BASE_URL}/outputs/${folderName}/info_video_pt.json`)
                        .then(r => r.json())
                        .then(json_pt => {
                            datosClonados.pt = json_pt;
                            if (idiomaActual === "pt") cambiarIdiomaResultados("pt");
                        }).catch(e => {});
                } catch(e) {}
            }
            
            // Actualizar vista del idioma actual
            cambiarIdiomaResultados(idiomaActual);
            
            // Asegurar que las miniaturas de las opciones 2 y 3 en español se carguen si estamos en español
            if (idiomaActual === "es") {
                const opc2Url = `${API_BASE_URL}/outputs/${folderName}/miniatura_opcion2.png?t=${Date.now()}`;
                const opc3Url = `${API_BASE_URL}/outputs/${folderName}/miniatura_opcion3.png?t=${Date.now()}`;
                const imgOpc2 = document.getElementById("thumb-img-opc2");
                const imgOpc3 = document.getElementById("thumb-img-opc3");
                const btnOpc2 = document.getElementById("download-opc2-btn");
                const btnOpc3 = document.getElementById("download-opc3-btn");
                
                if (imgOpc2 && imgOpc2.src !== opc2Url) {
                    imgOpc2.src = opc2Url;
                    btnOpc2.href = opc2Url;
                    btnOpc2.style.display = "inline-flex";
                }
                if (imgOpc3 && imgOpc3.src !== opc3Url) {
                    imgOpc3.src = opc3Url;
                    btnOpc3.href = opc3Url;
                    btnOpc3.style.display = "inline-flex";
                }
            }
            
            // Mostrar Kit y Botones de descarga
            document.getElementById("publish-kit").style.display = "block";
            downloadVideoBtn.style.display = "inline-flex";
            const btnOpc1 = document.getElementById("download-opc1-btn");
            if (btnOpc1) btnOpc1.style.display = "inline-flex";
            if (btnRegenerarMinia) btnRegenerarMinia.style.display = "inline-block";
        }
    } catch (e) {
        console.error("Error en polling:", e);
    }
}

// 3. RASTREAR COMPETENCIA
btnRastrear.addEventListener("click", async () => {
    const urls = competidorUrls.value.split("\n").map(u => u.trim()).filter(u => u.length > 0);
    if (urls.length === 0) {
        alert("Por favor ingresa al menos un enlace de canal de YouTube.");
        return;
    }
    
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
                    opt.value = item.title;
                    opt.dataset.id = item.id;
                    opt.innerText = item.label || item.title; // Mostrar visualizaciones, fecha y canal
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

// Manejar selección del video en la lista
selectVideosVirales.addEventListener("change", (e) => {
    const chosenOption = selectVideosVirales.options[selectVideosVirales.selectedIndex];
    if (chosenOption.value) {
        temaManual.value = chosenOption.value;
        videoIdCompetidorSeleccionado = chosenOption.dataset.id || "";
        competidorVideoIdInput.value = videoIdCompetidorSeleccionado;
        actualizarCompetitorThumbPreview();
    }
});

// 4. REDACTAR GUION CON GEMINI
btnRedactar.addEventListener("click", async () => {
    const tema = temaManual.value.trim();
    if (!tema) {
        alert("Escribe un tema o selecciona uno de los videos ganadores primero.");
        return;
    }
    
    btnRedactar.disabled = true;
    btnRedactar.innerText = "⏳ GEMINI REDACTANDO...";
    
    // Obtener idiomas seleccionados para clonar
    const clonarIdiomas = [];
    if (document.getElementById("clone-en")?.checked) clonarIdiomas.push("en");
    if (document.getElementById("clone-pt")?.checked) clonarIdiomas.push("pt");

    try {
        const res = await fetch(`${API_BASE_URL}/api/redactar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                tema: tema,
                duracion_min: parseFloat(selectDuracion.value) || 1.0,
                clonar_idiomas: clonarIdiomas
            })
        });
        
        if (res.ok) {
            datosVideoActual = await res.json();
            temaOriginalRedactado = tema; // Guardar el tema original redactado
            abrirModalGuion(datosVideoActual);
        } else {
            const err = await res.json();
            alert(`Error redactando guión: ${err.detail || "Error desconocido"}`);
        }
    } catch (e) {
        alert("Error al conectar con la API de Gemini.");
    } finally {
        btnRedactar.disabled = false;
        btnRedactar.innerText = "🧠 REDACTAR GUION E IDEAS (GEMINI)";
    }
});

// 5. MODAL DE EDICIÓN DE GUION
function abrirModalGuion(datos) {
    modalTitulosContainer.innerHTML = "";
    
    // Crear cartas para los títulos sugeridos
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
    modalTextoMinia.value = datos.texto_miniatura;
    modalGuionTexto.value = datos.guion_locucion;
    actualizarContadorPalabras();
    
    modalGuion.style.display = "flex";
}

modalGuionTexto.addEventListener("input", actualizarContadorPalabras);

// Guardar guion modificado en el modal
btnGuardarGuion.addEventListener("click", () => {
    if (!datosVideoActual) return;
    
    datosVideoActual.texto_miniatura = modalTextoMinia.value.trim();
    datosVideoActual.guion_locucion = modalGuionTexto.value.trim();
    
    // Reemplazar la lista de títulos para poner el elegido de primero
    const index = datosVideoActual.titulos.indexOf(tituloSeleccionadoModal);
    if (index > -1) {
        datosVideoActual.titulos.splice(index, 1);
    }
    datosVideoActual.titulos.unshift(tituloSeleccionadoModal);
    
    const temaNuevo = tituloSeleccionadoModal;
    const temaOriginal = temaOriginalRedactado || temaManual.value;
    
    temaManual.value = temaNuevo;
    modalGuion.style.display = "none";
    
    // Guardar cambios locales en el backend
    actualizarGuionEnServidor(temaOriginal, temaNuevo, datosVideoActual);
    temaOriginalRedactado = temaNuevo; // Actualizar para futuras ediciones
});

async function actualizarGuionEnServidor(temaOriginal, temaNuevo, datos) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/guion/guardar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                tema_original: temaOriginal,
                tema_nuevo: temaNuevo,
                datos: datos
            })
        });
        if (res.ok) {
            console.log("💾 Guion y carpeta de salida actualizados correctamente en servidor.");
        }
    } catch (e) {
        console.error("Error al sincronizar guion modificado:", e);
    }
}

// Cerrar modal
const cerrarModal = () => { modalGuion.style.display = "none"; };
btnCloseModal.addEventListener("click", cerrarModal);
btnCancelarGuion.addEventListener("click", cerrarModal);

// 6. LANZAR PRODUCCIÓN (PRODUCIR)
btnProducir.addEventListener("click", async () => {
    // Limpiar variables de clonación anteriores
    datosClonados = { es: null, en: null, pt: null };
    idiomaActual = 'es';
    activeFolderName = "";
    
    // Ocultar pestañas de idiomas
    const btnEn = document.getElementById("btn-lang-en");
    if (btnEn) btnEn.style.display = "none";
    const btnPt = document.getElementById("btn-lang-pt");
    if (btnPt) btnPt.style.display = "none";
    const btnEnPrev = document.getElementById("btn-prev-en");
    if (btnEnPrev) btnEnPrev.style.display = "none";
    const btnPtPrev = document.getElementById("btn-prev-pt");
    if (btnPtPrev) btnPtPrev.style.display = "none";
    
    // Ocultar botones de descarga
    if (downloadVideoBtn) downloadVideoBtn.style.display = "none";
    const btnOpc1 = document.getElementById("download-opc1-btn");
    if (btnOpc1) btnOpc1.style.display = "none";
    const btnOpc2 = document.getElementById("download-opc2-btn");
    if (btnOpc2) btnOpc2.style.display = "none";
    const btnOpc3 = document.getElementById("download-opc3-btn");
    if (btnOpc3) btnOpc3.style.display = "none";

    const tema = temaManual.value.trim();
    const urlComfy = runpodUrl.value.trim();
    
    if (!tema) {
        alert("Por favor establece el Tema del video.");
        return;
    }
    if (!urlComfy) {
        alert("Escribe la URL del Proxy de RunPod.");
        return;
    }
    
    // Obtener idiomas seleccionados para clonar
    const clonarIdiomas = [];
    if (document.getElementById("clone-en")?.checked) clonarIdiomas.push("en");
    if (document.getElementById("clone-pt")?.checked) clonarIdiomas.push("pt");

    const bodyPayload = {
        tema: tema,
        url_runpod: urlComfy,
        voz: selectVoz.value,
        estilo_video: selectEstilo.value,
        orientacion: selectOrientacion.value,
        musica_genero: selectMusica.value,
        competidor_video_id: competidorVideoIdInput.value.trim() || null,
        sub_fuente: document.getElementById("select-sub-fuente").value,
        sub_color_iluminado: document.getElementById("select-sub-color-iluminado").value,
        sub_color_fondo: document.getElementById("select-sub-color-fondo").value,
        sub_animacion: document.getElementById("select-sub-animacion").value,
        tono_voz: document.getElementById("select-sub-pitch").value,
        velocidad_voz: document.getElementById("select-sub-rate").value,
        volumen_musica: parseFloat(document.getElementById("select-volumen-musica").value),
        clonar_idiomas: clonarIdiomas
    };
    
    btnProducir.disabled = true;
    btnProducir.innerText = "⏳ PROCESANDO EN RunPod...";
    
    try {
        // Limpiar consola local
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

// Limpiar logs
btnLimpiarLog.addEventListener("click", async () => {
    try {
        await fetch(`${API_BASE_URL}/api/status/clear`, { method: "POST" });
        consoleOutput.innerHTML = '<div class="log-line system">[SISTEMA] Consola limpia.</div>';
    } catch (e) {}
});

// Actualizar la previsualización de subtítulos en vivo
function actualizarSubtitulosLivePreview() {
    const previewContainer = document.getElementById("sub-preview-display");
    if (!previewContainer) return;
    
    const font = document.getElementById("select-sub-fuente").value;
    const colorInactivo = document.getElementById("select-sub-color-fondo").value;
    
    const cssColorMap = {
        white: "#ffffff",
        gray: "#aaaaaa",
        yellow: "#ffff00",
        red: "#ff3333",
        green: "#39ff14",
        cyan: "#00ffff",
        magenta: "#ff00ff",
        orange: "#ffaa00",
        purple: "#b026ff"
    };
    
    const colInactiveHex = cssColorMap[colorInactivo] || "#ffffff";
    
    previewContainer.style.fontFamily = `"${font}", "Arial Black", sans-serif`;
    
    const words = previewContainer.querySelectorAll(".preview-word");
    words.forEach((w) => {
        w.style.color = colInactiveHex;
        w.style.textShadow = "2px 2px 0px #000, -2px -2px 0px #000, 2px -2px 0px #000, -2px 2px 0px #000";
        w.style.transform = "scale(1)";
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
        
        const colorInactivo = document.getElementById("select-sub-color-fondo").value;
        const colorIluminado = document.getElementById("select-sub-color-iluminado").value;
        const animacion = document.getElementById("select-sub-animacion").value;
        
        const cssColorMap = {
            white: "#ffffff",
            gray: "#aaaaaa",
            yellow: "#ffff00",
            red: "#ff3333",
            green: "#39ff14",
            cyan: "#00ffff",
            magenta: "#ff00ff",
            orange: "#ffaa00",
            purple: "#b026ff"
        };
        const colInactiveHex = cssColorMap[colorInactivo] || "#ffffff";
        const colActiveHex = cssColorMap[colorIluminado] || "#ffff00";
        
        words.forEach((w) => {
            w.style.color = colInactiveHex;
            w.style.transform = "scale(1)";
        });
        
        if (animacion === "karaoke") {
            for (let i = 0; i <= activeIndex; i++) {
                if (words[i]) words[i].style.color = colActiveHex;
            }
        } else {
            if (words[activeIndex]) {
                words[activeIndex].style.color = colActiveHex;
                words[activeIndex].style.transform = "scale(1.15)";
            }
        }
        
        activeIndex = (activeIndex + 1) % (words.length + 1);
    }, 450);
}

function actualizarCompetitorThumbPreview() {
    const competitorVideoIdInput = document.getElementById("competidor-video-id");
    const competitorThumbContainer = document.getElementById("competitor-thumb-preview-container");
    const competitorThumbImg = document.getElementById("competitor-thumb-img");
    if (!competitorVideoIdInput || !competitorThumbContainer || !competitorThumbImg) return;
    
    const id = competitorVideoIdInput.value.trim();
    if (id && id.length >= 8) {
        competitorThumbImg.src = `https://img.youtube.com/vi/${id}/maxresdefault.jpg`;
        competitorThumbContainer.style.display = "block";
    } else {
        competitorThumbContainer.style.display = "none";
    }
}

// Inicialización del script
async function init() {
    // Autocompletar la URL de RunPod ComfyUI basada en el origin actual
    const currentOrigin = window.location.origin;
    if (currentOrigin.includes("-5000.proxy.runpod.net")) {
        const comfyUrl = currentOrigin.replace("-5000.proxy.runpod.net", "-8188.proxy.runpod.net");
        if (runpodUrl) runpodUrl.value = comfyUrl;
    } else if (currentOrigin.includes("localhost") || currentOrigin.includes("127.0.0.1")) {
        // Cargar config del servidor local para autocompletar la URL de RunPod
        try {
            const resConfig = await fetch(`${API_BASE_URL}/api/config`);
            if (resConfig.ok) {
                const configData = await resConfig.json();
                if (configData.pod_id) {
                    const comfyUrl = `https://${configData.pod_id}-8188.proxy.runpod.net`;
                    if (runpodUrl) runpodUrl.value = comfyUrl;
                }
            }
        } catch (e) {
            console.error("Error al cargar config de RunPod:", e);
        }
    }

    // Cargar canales guardados en localStorage
    const savedUrls = localStorage.getItem("competidor_urls");
    if (savedUrls) {
        competidorUrls.value = savedUrls;
    }
    
    // Guardar cambios automáticamente
    competidorUrls.addEventListener("input", () => {
        localStorage.setItem("competidor_urls", competidorUrls.value);
    });

    // Event listeners para la vista previa de subtítulos
    ["select-sub-fuente", "select-sub-color-fondo", "select-sub-color-iluminado", "select-sub-animacion"].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("change", () => {
                actualizarSubtitulosLivePreview();
                iniciarAnimacionLivePreview();
            });
        }
    });

    // Iniciar previsualización
    actualizarSubtitulosLivePreview();
    iniciarAnimacionLivePreview();

    // Event listener para miniatura de competidor
    if (competidorVideoIdInput) {
        competidorVideoIdInput.addEventListener("input", actualizarCompetitorThumbPreview);
        actualizarCompetitorThumbPreview();
    }

    const online = await verificarConexion();
    if (online) {
        pollStatus();
        pollingInterval = setInterval(() => {
            verificarConexion();
            pollStatus();
        }, 1500);
    } else {
        // Seguir buscando servidor cada 3 segundos hasta conectar
        setTimeout(init, 3000);
    }
}

// Función global para copiar textos al portapapeles
window.copiarTexto = function(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    el.select();
    el.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(el.value);
    
    // Obtener el botón al lado
    const btn = el.nextElementSibling;
    if (btn) {
        const origText = btn.innerText;
        btn.innerText = "¡Copiado!";
        btn.style.background = "#10b981"; // Verde éxito
        btn.style.color = "white";
        setTimeout(() => {
            btn.innerText = origText;
            btn.style.background = "";
            btn.style.color = "";
        }, 1500);
    }
};

// 7. RE-GENERAR SOLO MINIATURA
if (btnRegenerarMinia) {
    btnRegenerarMinia.addEventListener("click", async () => {
        const tema = temaManual.value.trim();
        const urlComfy = runpodUrl.value.trim();
        if (!tema) {
            alert("No hay un tema de video establecido.");
            return;
        }
        if (!urlComfy) {
            alert("Escribe la URL del Proxy de RunPod.");
            return;
        }
        
        btnRegenerarMinia.disabled = true;
        btnRegenerarMinia.innerText = "⏳ RE-GENERANDO...";
        
        try {
            const res = await fetch(`${API_BASE_URL}/api/miniatura/regenerar`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tema: tema,
                    url_runpod: urlComfy,
                    competidor_video_id: competidorVideoIdInput.value.trim() || null
                })
            });
            
            if (res.ok) {
                alert("🎨 ¡Fondo de miniatura re-generado con éxito! Las nuevas opciones ya están listas.");
                cambiarIdiomaResultados(idiomaActual); // Forzar recarga de las miniaturas en la vista
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

init();
