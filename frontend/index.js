let problems = [];
let currentProblem = null;
let conversationHistory = [];
const API_URL = window.ENV_API_URL || '';

// Cargar problemas al iniciar
async function loadProblems() {
    const res = await fetch(`${API_URL}/problems`);
    problems = await res.json();
    const select = document.getElementById('problemSelect');
    problems.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.id} — ${p.titulo}`;
        select.appendChild(opt);
    });
}

function loadProblem() {
    const problemId = document.getElementById('problemSelect').value;
    if (!problemId) {
        document.getElementById('problemCard').style.display = 'none';
        document.getElementById('sendBtn').disabled = true;
        return;
    }

    currentProblem = problems.find(p => p.id === problemId);
    if (!currentProblem) return;

    document.getElementById('problemTitle').textContent = currentProblem.titulo;
    document.getElementById('problemText').textContent = currentProblem.enunciado;
    document.getElementById('problemBloom').textContent = `Bloom: ${currentProblem.nivel_bloom}`;
    document.getElementById('problemSdlc').textContent = `SDLC: ${currentProblem.fase_sdlc}`;
    document.getElementById('problemConcept').textContent = currentProblem.concepto;
    document.getElementById('problemCard').style.display = 'block';
    document.getElementById('sendBtn').disabled = false;

    // Resetear conversación
    conversationHistory = [];
    document.getElementById('chatMessages').innerHTML = `
        <div class="welcome-message">
            <h2>${currentProblem.titulo}</h2>
            <p>${currentProblem.enunciado}</p>
        </div>
    `;
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    if (!message || !currentProblem) return;

    const studentId = document.getElementById('studentId').value || 'EST001';

    // Mostrar mensaje del estudiante
    appendMessage('user', message);
    input.value = '';
    input.style.height = 'auto';

    // Agregar a historial
    conversationHistory.push({ role: 'user', content: message });

    // Mostrar indicador de escritura
    document.getElementById('typingIndicator').classList.add('visible');
    document.getElementById('sendBtn').disabled = true;

    try {
        const res = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                problem_id: currentProblem.id,
                messages: conversationHistory
            })
        });

        if (!res.ok) {
            const errText = await res.text();
            console.error('Error del servidor:', res.status, errText);
            throw new Error(`El servidor respondió ${res.status}`);
        }

        const data = await res.json();

        conversationHistory.push({ role: 'assistant', content: data.response });
        appendMessage('agent', data.response, data.metadata);
        updateProfile(data.profile);

    } catch (err) {
        console.error(err);
        // No dejar en el historial el mensaje del usuario que falló
        if (conversationHistory.at(-1)?.role === 'user') conversationHistory.pop();
        appendMessage('agent', `Error: ${err.message}. Revisa la consola para más detalle.`);
    } finally {
        document.getElementById('typingIndicator').classList.remove('visible');
        document.getElementById('sendBtn').disabled = false;
    }
}

function appendMessage(role, text, metadata = null) {
    const container = document.getElementById('chatMessages');
    const welcome = container.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `message ${role}`;

    let metaHTML = '';
    if (metadata && metadata.clasificacion) {
        const labels = {
            'CORRECTA': '✅ Correcta',
            'PARCIAL': '⚠️ Parcial',
            'EC': '🔴 Error conceptual',
            'EP': '🟡 Error procedimental',
            'SOLICITUD_DIRECTA': '🚫 Solicitud directa',
            'INACTIVO': '💤 Inactivo'
        };
        const label = labels[metadata.clasificacion] || metadata.clasificacion;
        const nivel = metadata.nivel_intervencion > 0 ? ` · Nivel ${metadata.nivel_intervencion}` : '';
        const bloom = metadata.nivel_bloom ? ` · Bloom: ${metadata.nivel_bloom}` : '';
        metaHTML = `<span class="metadata-badge">${label}${nivel}${bloom}</span>`;
    }

    div.innerHTML = `
        <div class="message-bubble">${text.replace(/\n/g, '<br>')}</div>
        ${metaHTML}
        <div class="message-meta">${role === 'user' ? 'Tú' : 'Agente Tutor'} · ${new Date().toLocaleTimeString()}</div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function updateProfile(profile) {
    if (!profile) return;
    document.getElementById('statTotal').textContent = profile.total_interacciones || 0;
    document.getElementById('statEC').textContent = profile.errores_conceptuales || 0;
    document.getElementById('statEP').textContent = profile.errores_procedimentales || 0;
    document.getElementById('statCorrectas').textContent = profile.respuestas_correctas || 0;
    const nivel = profile.nivel_intervencion_promedio;
    document.getElementById('statNivel').innerHTML = nivel
        ? nivel.toFixed(1)
        : '<small>—</small>';
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// Auto-resize textarea
document.getElementById('messageInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

loadProblems();
window.loadProblem = loadProblem;
window.sendMessage = sendMessage;
window.handleKeyDown = handleKeyDown;
