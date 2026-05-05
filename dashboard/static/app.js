const terminal = document.getElementById('terminal');
const preview = document.getElementById('preview');
const btnDraft = document.getElementById('btnDraft');
const btnMedia = document.getElementById('btnMedia');
const btnPublish = document.getElementById('btnPublish');
const btnRun = document.getElementById('btnRun');
const btnStop = document.getElementById('btnStop');
const btnClear = document.getElementById('btnClear');
const btnRefreshPreview = document.getElementById('btnRefreshPreview');
const connStatus = document.getElementById('connStatus');
const phaseItems = document.querySelectorAll('.phase-item');

let ws;
let isRunning = false;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        connStatus.textContent = '● Connected';
        connStatus.style.color = '#10b981';
    };

    ws.onclose = () => {
        connStatus.textContent = '● Disconnected';
        connStatus.style.color = '#ef4444';
        setTimeout(connectWebSocket, 3000); 
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'log') {
            appendLog(msg.data);
            updatePhase(msg.data);
            // 만약 초안 생성이 끝났다는 로그가 오면 미리보기 갱신
            if (msg.data.includes('Phase 2 complete') || msg.data.includes('블로그 & 대본 생성 완료')) {
                loadPreview();
            }
        } else if (msg.type === 'status') {
            if (msg.data === 'RUNNING') {
                isRunning = true;
                setButtonsDisabled(true);
                btnStop.style.display = 'block';
                appendLog(`[System] Starting pipeline mode: ${msg.mode || 'all'}`);
            } else if (msg.data === 'STOPPED') {
                isRunning = false;
                setButtonsDisabled(false);
                btnStop.style.display = 'none';
                appendLog(`[System] Pipeline finished or stopped.`);
                loadPreview();
            }
        }
    };
}

function setButtonsDisabled(disabled) {
    [btnDraft, btnMedia, btnPublish, btnRun].forEach(btn => {
        btn.disabled = disabled;
        btn.style.opacity = disabled ? "0.5" : "1.0";
        btn.style.cursor = disabled ? "not-allowed" : "pointer";
    });
}

function appendLog(text) {
    const div = document.createElement('div');
    div.className = 'log-line';
    
    if (text.includes('[FAIL]') || text.includes('에러') || text.toLowerCase().includes('error')) {
        div.classList.add('error');
    } else if (text.includes('[WARN]') || text.includes('경고')) {
        div.classList.add('warning');
    } else if (text.includes('[OK]') || text.includes('완료') || text.includes('성공') || text.includes('>>>')) {
        div.classList.add('success');
    }
    
    div.textContent = text;
    terminal.appendChild(div);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
    terminal.innerHTML = '<div class="log-line" style="color: #64748b;">Terminal cleared.</div>';
}

function resetPhases() {
    phaseItems.forEach(item => {
        item.classList.remove('active', 'done');
    });
}

function updatePhase(log) {
    const phaseMatch = log.match(/Phase (\d+)/);
    if (phaseMatch) {
        const pNum = parseInt(phaseMatch[1]);
        phaseItems.forEach(item => {
            const currentPhase = parseInt(item.dataset.phase);
            if (currentPhase < pNum) {
                item.classList.remove('active');
                item.classList.add('done');
            } else if (currentPhase === pNum) {
                item.classList.add('active');
            }
        });
    }
}

async function loadPreview() {
    try {
        const res = await fetch('/api/latest_draft');
        const data = await res.json();
        preview.textContent = data.content;
    } catch (e) {
        preview.textContent = "미리보기를 불러오지 못했습니다.";
    }
}

function sendAction(action, mode = "all") {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action, mode }));
    }
}

btnDraft.addEventListener('click', () => sendAction('start', 'draft'));
btnMedia.addEventListener('click', () => sendAction('start', 'media'));
btnPublish.addEventListener('click', () => sendAction('start', 'publish'));
btnRun.addEventListener('click', () => sendAction('start', 'all'));
btnStop.addEventListener('click', () => sendAction('stop'));
btnClear.addEventListener('click', clearTerminal);
btnRefreshPreview.addEventListener('click', loadPreview);

// Initialize
connectWebSocket();
loadPreview();
