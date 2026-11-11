// ---------------------------------------------------------------------------
// Frontend del tutor. El estudiante ve solo el texto de `response`.
// La metadata y el perfil solo se muestran con ?debug=1 (uso del investigador).
// ---------------------------------------------------------------------------
let problems = [];
let currentProblem = null;
let conversationHistory = [];
let sending = false;
let limitReached = false;
let reviewMode = false; // debug: viendo la conversación de otro ID, sin poder enviar
let reviewTimer = null;

const API_URL = window.ENV_API_URL || '';
const TIMEOUT_MS = 90000; // el primer acceso a Render puede tardar si el servicio estaba dormido
const DEBUG = new URLSearchParams(location.search).get('debug') === '1';
document.body.classList.toggle('debug', DEBUG);

const $ = (id) => document.getElementById(id);

const ERRORES_HTTP = {
    404: 'Este problema ya no está disponible. Recarga la página.',
    422: 'No se pudo enviar tu mensaje. Revisa que no esté vacío ni supere los 4000 caracteres.',
    503: 'El servicio está ocupado. Intenta de nuevo en unos segundos.',
};

// ---------- utilidades ----------

function escapeHtml(texto) {
    return String(texto)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Escapa primero y luego aplica el formato mínimo (negrita y saltos de línea).
function formatear(texto) {
    return escapeHtml(texto)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function refreshSend() {
    $('sendBtn').disabled = !currentProblem || sending || limitReached || reviewMode;
    $('problemSelect').disabled = sending;
}

// ---------- problemas ----------

async function loadProblems() {
    try {
        const res = await fetchConTiempo(`${API_URL}/problems`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        problems = await res.json();
        const select = $('problemSelect');
        problems.forEach((p) => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.id} — ${p.titulo}`;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('No se pudieron cargar los problemas:', err);
        appendNote('No se pudieron cargar los problemas. Recarga la página en unos segundos.');
    }
}

function loadProblem() {
    reviewMode = false;
    const problemId = $('problemSelect').value;
    currentProblem = problems.find((p) => p.id === problemId) || null;
    conversationHistory = [];

    if (!currentProblem) {
        $('problemCard').style.display = 'none';
        refreshSend();
        return;
    }

    $('problemTitle').textContent = currentProblem.titulo;
    $('problemText').textContent = currentProblem.enunciado;
    $('problemBloom').textContent = `Bloom: ${currentProblem.nivel_bloom}`;
    $('problemSdlc').textContent = `SDLC: ${currentProblem.fase_sdlc}`;
    $('problemConcept').textContent = currentProblem.concepto;
    $('problemCard').style.display = 'block';

    $('chatMessages').innerHTML = `
        <div class="welcome-message">
            <h2>${escapeHtml(currentProblem.titulo)}</h2>
            <p>${escapeHtml(currentProblem.enunciado)}</p>
        </div>
    `;
    refreshSend();
}

// ---------- envío ----------

async function fetchConTiempo(url, opciones = {}) {
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), TIMEOUT_MS);
    try {
        return await fetch(url, { ...opciones, signal: control.signal });
    } finally {
        clearTimeout(temporizador);
    }
}

async function sendMessage() {
    if (sending || limitReached || !currentProblem) return;

    const input = $('messageInput');
    const message = input.value.trim();
    if (!message) return;

    const studentId = $('studentId').value.trim();
    if (!studentId) {
        appendNote('Escribe tu ID de estudiante antes de enviar.');
        $('studentId').focus();
        return;
    }

    sending = true;
    refreshSend();

    const burbuja = appendMessage('user', message);
    input.value = '';
    input.style.height = 'auto';
    conversationHistory.push({ role: 'user', content: message });
    $('typingIndicator').classList.add('visible');

    // Deshace el envío: quita la burbuja, el historial y devuelve el texto al campo.
    const deshacer = () => {
        burbuja.remove();
        if (conversationHistory.at(-1)?.role === 'user') conversationHistory.pop();
        input.value = message;
    };

    try {
        const res = await fetchConTiempo(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                problem_id: currentProblem.id,
                messages: conversationHistory,
            }),
        });

        if (!res.ok) {
            console.error('Error del servidor:', res.status, await res.text());
            deshacer();
            appendNote(ERRORES_HTTP[res.status] || 'Ocurrió un problema en el servidor. Intenta de nuevo.');
            return;
        }

        const data = await res.json();
        const meta = data.metadata || {};

        if (meta.motivo === 'limite_turnos') {
            deshacer();
            input.value = '';
            appendMessage('agent', data.response, meta);
            bloquearSesion();
            return;
        }

        if (meta.registrado === false) {
            // El turno no se procesó (p. ej. falló el clasificador): el estudiante puede reenviar.
            deshacer();
            appendNote(data.response);
            return;
        }

        conversationHistory.push({ role: 'assistant', content: data.response });
        appendMessage('agent', data.response, meta);
        updateProfile(data.profile);
        if (!DEBUG) $('studentId').disabled = true; // el ID no cambia a mitad de la sesión

    } catch (err) {
        console.error(err);
        deshacer();
        appendNote(err.name === 'AbortError'
            ? 'La respuesta tardó demasiado. Intenta de nuevo.'
            : 'No pude conectarme con el servidor. Revisa tu conexión e intenta de nuevo.');
    } finally {
        sending = false;
        $('typingIndicator').classList.remove('visible');
        refreshSend();
    }
}

function bloquearSesion() {
    limitReached = true;
    $('messageInput').disabled = true;
    $('messageInput').placeholder = 'Has completado la sesión.';
    if (!DEBUG) $('studentId').disabled = true;
}

// ---------- pintado ----------

function appendMessage(role, text, metadata = null, fecha = null) {
    const container = $('chatMessages');
    container.querySelector('.welcome-message')?.remove();

    const div = document.createElement('div');
    div.className = `message ${role}`;

    let metaHTML = '';
    if (DEBUG && metadata && metadata.clasificacion) {
        const labels = {
            CORRECTA: '✅ Correcta',
            PARCIAL: '⚠️ Parcial',
            EC: '🔴 Error conceptual',
            EP: '🟡 Error procedimental',
            SOLICITUD_DIRECTA: '🚫 Solicitud directa',
            INACTIVO: '💤 Inactivo',
        };
        const label = labels[metadata.clasificacion] || metadata.clasificacion;
        const nivel = metadata.nivel_intervencion > 0 ? ` · Nivel ${metadata.nivel_intervencion}` : '';
        const bloom = metadata.nivel_bloom ? ` · Bloom: ${metadata.nivel_bloom}` : '';
        metaHTML = `<span class="metadata-badge">${escapeHtml(label + nivel + bloom)}</span>`;
    }

    div.innerHTML = `
        <div class="message-bubble">${formatear(text)}</div>
        ${metaHTML}
        <div class="message-meta">${role === 'user' ? 'Tú' : 'Agente Tutor'} · ${fecha ? new Date(fecha).toLocaleString() : new Date().toLocaleTimeString()}</div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

// Aviso del sistema (no es parte de la conversación ni del historial).
function appendNote(text) {
    const container = $('chatMessages');
    container.querySelector('.welcome-message')?.remove();
    const div = document.createElement('div');
    div.className = 'system-note';
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function updateProfile(profile) {
    if (!DEBUG || !profile) return;
    $('statTotal').textContent = profile.total_interacciones || 0;
    $('statEC').textContent = profile.errores_conceptuales || 0;
    $('statEP').textContent = profile.errores_procedimentales || 0;
    $('statCorrectas').textContent = profile.respuestas_correctas || 0;
    const nivel = profile.nivel_intervencion_promedio;
    $('statNivel').innerHTML = nivel ? nivel.toFixed(1) : '<small>—</small>';
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

$('messageInput').addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});


// ---------- revisión (solo ?debug=1) ----------

async function adminFetch(ruta) {
    const token = $('adminToken').value.trim();
    if (!token) throw new Error('Escribe el token de administrador.');
    const res = await fetchConTiempo(`${API_URL}${ruta}`, { headers: { 'X-Admin-Token': token } });
    if (res.status === 401) throw new Error('Token inválido.');
    if (res.status === 404) throw new Error('El panel de revisión no está activado en el servidor.');
    if (!res.ok) throw new Error(`Error del servidor (${res.status}).`);
    try { sessionStorage.setItem('adminToken', token); } catch (_) { /* sin almacenamiento */ }
    return res.json();
}

async function loadStudentIds() {
    const info = $('adminInfo');
    info.textContent = 'Cargando…';
    try {
        const lista = await adminFetch('/admin/students');
        const datalist = $('studentList');
        datalist.innerHTML = '';
        lista.forEach((e) => {
            const opt = document.createElement('option');
            opt.value = e.student_id;
            opt.label = `${e.turnos} turno${e.turnos === 1 ? '' : 's'}`;
            datalist.appendChild(opt);
        });
        info.textContent = `${lista.length} ID${lista.length === 1 ? '' : 's'} registrados. Haz clic en el campo de ID para elegir uno.`;
    } catch (err) {
        info.textContent = err.message;
    }
}

async function reviewStudent(id) {
    const info = $('adminInfo');
    try {
        const logs = await adminFetch(`/admin/students/${encodeURIComponent(id)}/conversation`);
        if ($('studentId').value.trim() !== id) return; // el campo cambió mientras cargaba

        reviewMode = true;
        $('chatMessages').innerHTML = '';
        if (!logs.length) {
            appendNote(`El ID ${id} no tiene conversaciones registradas.`);
        } else {
            appendNote(`Revisión de ${id} · ${logs.length} turno${logs.length === 1 ? '' : 's'} · solo lectura`);
            let problema = null;
            logs.forEach((log) => {
                if (log.problem_id !== problema) {
                    problema = log.problem_id;
                    appendNote(`Problema ${problema}`);
                }
                appendMessage('user', log.student_message, null, log.timestamp);
                appendMessage('agent', log.agent_response, {
                    clasificacion: log.clasificacion,
                    nivel_intervencion: log.nivel_intervencion,
                    nivel_bloom: log.nivel_bloom,
                }, log.timestamp);
            });
        }
        $('chatMessages').scrollTop = 0;
        info.textContent = `Mostrando la conversación de ${id}.`;
        refreshSend();
    } catch (err) {
        info.textContent = err.message;
    }
}

function exitReview() {
    reviewMode = false;
    conversationHistory = [];
    if (currentProblem) {
        const actual = currentProblem;
        $('chatMessages').innerHTML = `
            <div class="welcome-message">
                <h2>${escapeHtml(actual.titulo)}</h2>
                <p>${escapeHtml(actual.enunciado)}</p>
            </div>
        `;
    } else {
        $('chatMessages').innerHTML = `
            <div class="welcome-message">
                <h2>Bienvenido al Agente Tutor</h2>
                <p>Selecciona un problema en el panel izquierdo<br>y escribe tu respuesta para comenzar.</p>
            </div>
        `;
    }
    $('adminInfo').textContent = '';
    refreshSend();
}

if (DEBUG) {
    // Al elegir (o escribir) un ID registrado se muestra su conversación.
    $('studentId').addEventListener('input', (e) => {
        clearTimeout(reviewTimer);
        const id = e.target.value.trim();
        const registrado = [...$('studentList').options].some((o) => o.value === id);
        if (registrado && !sending) reviewTimer = setTimeout(() => reviewStudent(id), 250);
    });
    try {
        const guardado = sessionStorage.getItem('adminToken');
        if (guardado) { $('adminToken').value = guardado; loadStudentIds(); }
    } catch (_) { /* sin almacenamiento */ }
}

loadProblems();
window.loadStudentIds = loadStudentIds;
window.exitReview = exitReview;
window.loadProblem = loadProblem;
window.sendMessage = sendMessage;
window.handleKeyDown = handleKeyDown;
