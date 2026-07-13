'use strict';

// ================================================================
// State machine
// ================================================================

const STATE = Object.freeze({
  ENTRY:      'entry',
  CONNECTING: 'connecting',
  WAITING:    'waiting',
  OPEN:       'open',
  PRESSED:    'pressed',
  CLOSED:     'closed',
});

let currentState = STATE.ENTRY;
let socket       = null;
let myId         = null;
let myRank       = null;
let questionNum  = 1;
let roomId       = null;

// ================================================================
// DOM refs
// ================================================================

const screenEntry  = document.getElementById('screen-entry');
const screenBuzzer = document.getElementById('screen-buzzer');

const entryForm    = document.getElementById('entry-form');
const entryInput   = document.getElementById('participant-id');
const entryError   = document.getElementById('entry-error');
const entryBtn     = document.getElementById('entry-btn');
const entryBtnText = document.getElementById('entry-btn-text');

const myIdDisplay   = document.getElementById('my-id-display');
const statusBadge   = document.getElementById('status-badge');
const questionLabel = document.getElementById('question-label');

const buzzerRing    = document.getElementById('buzzer-ring');
const buzzerBtn     = document.getElementById('buzzer-btn');
const buzzerText    = document.getElementById('buzzer-text');
const buzzerSubtext = document.getElementById('buzzer-subtext');

const pressResult   = document.getElementById('press-result');
const pressRankNum  = document.getElementById('press-rank-num');

const rankingSection = document.getElementById('ranking-section');
const rankingList    = document.getElementById('ranking-list');

// ================================================================
// UI helpers
// ================================================================

function showScreen(name) {
  screenEntry.classList.remove('active');
  screenBuzzer.classList.remove('active');
  if (name === 'entry')  screenEntry.classList.add('active');
  if (name === 'buzzer') screenBuzzer.classList.add('active');
}

function setBuzzerState(state) {
  buzzerBtn.className = `buzzer-btn state-${state}`;
}

function setStatus(text, cls) {
  statusBadge.textContent = text;
  statusBadge.className   = `status-badge status-${cls}`;
}

function updateUI(state) {
  currentState = state;
  document.body.className = `state-${state}`;

  switch (state) {

    case STATE.WAITING:
      setStatus('待機中', 'waiting');
      setBuzzerState('waiting');
      buzzerText.textContent    = '待機中';
      buzzerSubtext.textContent = '司会者の合図をお待ちください';
      buzzerBtn.disabled        = true;
      pressResult.classList.add('hidden');
      rankingSection.classList.add('hidden');
      rankingList.innerHTML = '';
      myRank = null;
      break;

    case STATE.OPEN:
      setStatus('受付中', 'open');
      setBuzzerState('open');
      buzzerText.textContent    = 'PUSH!';
      buzzerSubtext.textContent = 'ボタンを押してください！';
      buzzerBtn.disabled        = false;
      pressResult.classList.add('hidden');
      rankingSection.classList.add('hidden');
      rankingList.innerHTML = '';
      myRank = null;
      // Vibration for mobile
      if (navigator.vibrate) navigator.vibrate([80, 40, 80]);
      break;

    case STATE.PRESSED:
      setStatus('受付済み', 'pressed');
      setBuzzerState('pressed');
      buzzerText.textContent    = `第 ${myRank} 位`;
      buzzerSubtext.textContent = '回答受付済みです';
      buzzerBtn.disabled        = true;
      pressRankNum.textContent  = myRank;
      pressResult.classList.remove('hidden');
      break;

    case STATE.CLOSED:
      setStatus('締め切り', 'closed');
      setBuzzerState('closed');
      buzzerText.textContent    = myRank ? `第 ${myRank} 位` : '---';
      buzzerSubtext.textContent = '受付は終了しました';
      buzzerBtn.disabled        = true;
      break;
  }
}

// ================================================================
// Ranking renderer
// ================================================================

function renderRanking(ranking, currentRankIndex) {
  if (!ranking || ranking.length === 0) {
    rankingSection.classList.add('hidden');
    return;
  }

  rankingSection.classList.remove('hidden');
  rankingList.innerHTML = '';

  const medals = ['🥇', '🥈', '🥉'];

  ranking.forEach((id, i) => {
    const li = document.createElement('li');
    li.className = 'ranking-item';
    if (i === currentRankIndex) li.classList.add('current');
    if (id === myId) li.classList.add('mine');

    const rankNum  = document.createElement('span');
    rankNum.className   = 'rank-num';
    rankNum.textContent = medals[i] || `${i + 1}`;

    const rankName  = document.createElement('span');
    rankName.className   = 'rank-name';
    rankName.textContent = id;

    li.appendChild(rankNum);
    li.appendChild(rankName);

    if (id === myId) {
      const badge = document.createElement('span');
      badge.className   = 'mine-badge';
      badge.textContent = 'あなた';
      li.appendChild(badge);
    }

    rankingList.appendChild(li);
  });
}

// ================================================================
// WebSocket
// ================================================================

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url   = `${proto}//${location.host}/ws/participant?room_id=${encodeURIComponent(roomId)}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    socket.send(JSON.stringify({ type: 'join', participant_id: myId }));
  };

  socket.onmessage = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch { return; }
    handleMessage(data);
  };

  socket.onclose = () => {
    setStatus('切断', 'closed');
    buzzerBtn.disabled = true;
  };

  socket.onerror = () => {
    entryError.textContent = '接続に失敗しました。ページを再読み込みしてください。';
    resetEntryBtn();
    showScreen('entry');
    currentState = STATE.ENTRY;
    socket = null;
  };
}

// ================================================================
// Message handler
// ================================================================

function handleMessage(data) {
  switch (data.type) {

    case 'join_ack':
      if (data.success) {
        myIdDisplay.textContent = myId;
        document.getElementById('room-id-display-participant').textContent = `Room: ${roomId}`;
        showScreen('buzzer');
        questionNum = data.question_number || 1;
        questionLabel.textContent = `問題 ${questionNum}`;
        const initState = { open: STATE.OPEN, closed: STATE.CLOSED }[data.status] || STATE.WAITING;
        updateUI(initState);
      } else {
        entryError.textContent = data.reason || 'エントリーに失敗しました';
        resetEntryBtn();
        if (socket) { socket.close(); socket = null; }
      }
      break;

    case 'status_change':
      if (data.status === 'open') {
        updateUI(STATE.OPEN);
        if (data.question_number) {
          questionNum = data.question_number;
          questionLabel.textContent = `問題 ${questionNum}`;
        }
      } else if (data.status === 'closed') {
        // If already pressed, keep PRESSED UI but update status badge
        if (currentState === STATE.PRESSED) {
          setStatus('締め切り', 'closed');
        } else {
          updateUI(STATE.CLOSED);
        }
      } else if (data.status === 'waiting') {
        updateUI(STATE.WAITING);
      }
      break;

    case 'press_ack':
      myRank = data.rank;
      updateUI(STATE.PRESSED);
      break;

    case 'result_update':
      // In CLOSED or PRESSED state, show the ranking
      if (currentState === STATE.CLOSED || currentState === STATE.PRESSED) {
        renderRanking(data.ranking, data.current_rank_index);
      }
      break;

    case 'reset':
      questionNum = data.question_number || (questionNum + 1);
      questionLabel.textContent = `問題 ${questionNum}`;
      updateUI(STATE.WAITING);
      break;

    default:
      break;
  }
}

// ================================================================
// Event listeners
// ================================================================

function resetEntryBtn() {
  entryBtn.disabled     = false;
  entryBtnText.textContent = '参加する';
}

entryForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const rId = document.getElementById('room-id').value.trim();
  const id = entryInput.value.trim();
  
  if (!rId) {
    entryError.textContent = 'ルームIDを入力してください';
    return;
  }
  if (!id) {
    entryError.textContent = 'IDを入力してください';
    return;
  }

  roomId = rId;
  myId = id;
  entryError.textContent    = '';
  entryBtn.disabled         = true;
  entryBtnText.textContent  = '接続中...';
  connect();
});

buzzerBtn.addEventListener('click', () => {
  if (currentState !== STATE.OPEN || !socket) return;
  buzzerBtn.disabled = true; // 二重送信防止
  socket.send(JSON.stringify({ type: 'press' }));
});

// ================================================================
// Init
// ================================================================
const urlParams = new URLSearchParams(window.location.search);
const roomParam = urlParams.get('room');
if (roomParam) {
  document.getElementById('room-id').value = roomParam;
  document.getElementById('room-id-group').style.display = 'none';
}
showScreen('entry');
