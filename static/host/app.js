'use strict';

// ================================================================
// Auth check
// ================================================================

const token = sessionStorage.getItem('hayaoshy_token');
if (!token) {
  window.location.replace('/host/login');
}

// ================================================================
// State
// ================================================================

let socket          = null;
let currentStatus   = 'waiting';
let ranking         = [];
let currentRankIdx  = 0;
let questionNumber  = 1;

// ================================================================
// DOM refs
// ================================================================

const connDot         = document.getElementById('conn-dot');
const connLabel       = document.getElementById('conn-label');
const logoutBtn       = document.getElementById('logout-btn');

const statusBadge     = document.getElementById('status-badge');
const questionLabel   = document.getElementById('question-label');
const participantCount = document.getElementById('participant-count');
const participantList = document.getElementById('participant-list');

const btnOpen   = document.getElementById('btn-open');
const btnClose  = document.getElementById('btn-close');
const btnNext   = document.getElementById('btn-next');
const btnReset  = document.getElementById('btn-reset');

const rankingContainer = document.getElementById('ranking-container');
const qrImg            = document.getElementById('qr-img');
const qrUrl            = document.getElementById('qr-url');

// ================================================================
// WebSocket
// ================================================================

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url   = `${proto}//${location.host}/ws/host?token=${encodeURIComponent(token)}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    setConnected(true);
  };

  socket.onmessage = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch { return; }
    handleMessage(data);
  };

  socket.onclose = () => {
    setConnected(false);
    // Auto-reconnect after 3 seconds
    setTimeout(connect, 3000);
  };

  socket.onerror = () => {
    setConnected(false);
  };
}

function setConnected(connected) {
  if (connected) {
    connDot.className   = 'conn-dot connected';
    connLabel.textContent = '接続済み';
  } else {
    connDot.className   = 'conn-dot disconnected';
    connLabel.textContent = '切断 (再接続中...)';
  }
}

// ================================================================
// Message handler
// ================================================================

function handleMessage(data) {
  switch (data.type) {

    case 'auth_error':
      sessionStorage.removeItem('hayaoshy_token');
      alert('認証エラー: 再ログインしてください');
      window.location.replace('/host/login');
      break;

    case 'init':
      currentStatus  = data.status   || 'waiting';
      questionNumber = data.question_number || 1;
      ranking        = data.ranking   || [];
      currentRankIdx = data.current_rank_index || 0;
      updateStatus(currentStatus);
      updateParticipants(data.participants || []);
      renderRanking();
      break;

    case 'participant_update':
      updateParticipants(data.participants || []);
      break;

    case 'status_change':
      currentStatus  = data.status;
      if (data.question_number) {
        questionNumber = data.question_number;
        questionLabel.textContent = questionNumber;
      }
      if (data.status === 'open') {
        ranking        = [];
        currentRankIdx = 0;
        renderRanking();
      }
      updateStatus(data.status);
      break;

    case 'result_update':
      ranking        = data.ranking || [];
      currentRankIdx = data.current_rank_index ?? 0;
      renderRanking();
      break;

    case 'reset':
      currentStatus  = 'waiting';
      ranking        = [];
      currentRankIdx = 0;
      questionNumber = data.question_number || (questionNumber + 1);
      questionLabel.textContent = questionNumber;
      updateStatus('waiting');
      renderRanking();
      break;

    default:
      break;
  }
}

// ================================================================
// UI updaters
// ================================================================

function updateStatus(status) {
  // Badge
  statusBadge.className = `host-status-badge badge-${status}`;
  const labels = { waiting: '待機中', open: '受付中', closed: '締め切り' };
  statusBadge.textContent = labels[status] || status;

  // Buttons
  switch (status) {
    case 'waiting':
      btnOpen.disabled  = false;
      btnClose.disabled = true;
      btnNext.disabled  = true;
      btnReset.disabled = true;
      break;
    case 'open':
      btnOpen.disabled  = true;
      btnClose.disabled = false;
      btnNext.disabled  = true;
      btnReset.disabled = true;
      break;
    case 'closed':
      btnOpen.disabled  = false;
      btnClose.disabled = true;
      btnNext.disabled  = ranking.length > currentRankIdx + 1 ? false : true;
      btnReset.disabled = false;
      break;
  }
}

function updateParticipants(participants) {
  participantCount.textContent = `${participants.length} 人`;

  if (participants.length === 0) {
    participantList.innerHTML = '<p class="empty-msg">参加者を待っています...</p>';
    return;
  }

  participantList.innerHTML = participants
    .map(
      (id) => `
        <div class="participant-item">
          <span class="participant-icon">👤</span>
          <span class="participant-name">${escHtml(id)}</span>
        </div>
      `
    )
    .join('');
}

function renderRanking() {
  if (!ranking || ranking.length === 0) {
    rankingContainer.innerHTML = '<p class="empty-msg">まだ回答者がいません</p>';
    // Update next button state
    if (currentStatus === 'closed') {
      btnNext.disabled  = true;
      btnReset.disabled = false;
    }
    return;
  }

  const medals = ['🥇', '🥈', '🥉'];

  rankingContainer.innerHTML = ranking
    .map((id, i) => {
      const isCurrent = i === currentRankIdx;
      const isPast    = i < currentRankIdx;
      const medal     = medals[i];

      const badgeEl = isCurrent
        ? `<span class="current-badge-host">回答中</span>`
        : '';

      const rankEl = medal
        ? `<span class="rank-medal">${medal}</span>`
        : `<span class="rank-num-badge">${i + 1}</span>`;

      return `
        <div class="ranking-card ${isCurrent ? 'current' : ''} ${isPast ? 'past' : ''}">
          ${rankEl}
          <span class="rank-id">${escHtml(id)}</span>
          ${badgeEl}
        </div>
      `;
    })
    .join('');

  // Update button states for closed status
  if (currentStatus === 'closed') {
    btnNext.disabled  = currentRankIdx >= ranking.length - 1;
    btnReset.disabled = false;
  }
}

// ================================================================
// QR code loader
// ================================================================

async function loadQR() {
  try {
    const resp = await fetch('/api/host/qr', {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (resp.status === 401) {
      sessionStorage.removeItem('hayaoshy_token');
      window.location.replace('/host/login');
      return;
    }

    if (resp.ok) {
      const blob = await resp.blob();
      qrImg.src  = URL.createObjectURL(blob);
      qrUrl.textContent = `${location.protocol}//${location.host}/`;
    }
  } catch {
    qrImg.alt = 'QR コードを読み込めませんでした';
  }
}

// ================================================================
// Event listeners
// ================================================================

function send(obj) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(obj));
  } else {
    console.warn("Cannot send message. Socket open status:", socket ? socket.readyState : 'null');
  }
}

btnOpen.addEventListener('click', () => {
  send({ type: 'host_open' });
});

btnClose.addEventListener('click', () => {
  send({ type: 'host_close' });
});

btnNext.addEventListener('click', () => {
  send({ type: 'host_next_candidate' });
});

btnReset.addEventListener('click', () => {
  if (confirm('次の問題に進みますか？ （現在の回答状況がリセットされます）')) {
    send({ type: 'host_reset' });
  }
});

logoutBtn.addEventListener('click', () => {
  sessionStorage.removeItem('hayaoshy_token');
  window.location.replace('/host/login');
});

// ================================================================
// Utilities
// ================================================================

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ================================================================
// Init
// ================================================================

loadQR();
connect();
