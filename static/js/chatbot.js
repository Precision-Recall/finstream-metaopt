/* ═══════════════════════════════════════════════════════
   CHATBOT — Finstream AI  (chatbot.js)
   Endpoint: https://5t0g1bahwj.execute-api.us-east-1.amazonaws.com/api/chat
   ═══════════════════════════════════════════════════════ */

(function () {
  'use strict';

  const API_URL = 'https://5t0g1bahwj.execute-api.us-east-1.amazonaws.com/api/chat';

  /* ── DOM references ── */
  const toggleBtn   = document.getElementById('chatbotToggleBtn');
  const chatPanel   = document.getElementById('chatPanel');
  const messagesEl  = document.getElementById('chatMessages');
  const inputEl     = document.getElementById('chatInput');
  const sendBtn     = document.getElementById('chatSendBtn');
  const clearBtn    = document.getElementById('chatClearBtn');
  const iconOpen    = document.getElementById('chatIconOpen');
  const iconClose   = document.getElementById('chatIconClose');
  const btnLabel    = document.getElementById('chatBtnLabel');

  /* ── State ── */
  let history = [];       // [{role: 'user'|'assistant', content: '...'}]
  let isOpen  = false;
  let isBusy  = false;

  /* ─────────────────────────────────────────────
     Toggle panel open / close
  ───────────────────────────────────────────── */
  function openPanel() {
    chatPanel.hidden = false;
    toggleBtn.classList.add('active');
    iconOpen.style.display  = 'none';
    iconClose.style.display = '';
    btnLabel.textContent = 'CLOSE';
    isOpen = true;
    inputEl.focus();
  }

  function closePanel() {
    chatPanel.hidden = true;
    toggleBtn.classList.remove('active');
    iconOpen.style.display  = '';
    iconClose.style.display = 'none';
    btnLabel.textContent = 'FINSTREAM AI';
    isOpen = false;
  }

  toggleBtn.addEventListener('click', () => {
    if (isOpen) closePanel(); else openPanel();
  });

  /* ─────────────────────────────────────────────
     Clear conversation
  ───────────────────────────────────────────── */
  clearBtn.addEventListener('click', () => {
    history = [];
    messagesEl.innerHTML = `
      <div class="chat-greeting">
        <p class="chat-greeting-title">How can I help you?</p>
        <p class="chat-greeting-sub">Ask about predictions, drift events, model weights, or system state.</p>
      </div>`;
  });

  /* ─────────────────────────────────────────────
     Render helpers
  ───────────────────────────────────────────── */
  function removeGreeting() {
    const greet = messagesEl.querySelector('.chat-greeting');
    if (greet) greet.remove();
  }

  function appendBubble(role, text) {
    const div = document.createElement('div');
    div.className = `chat-bubble ${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function appendTyping() {
    const el = document.createElement('div');
    el.className = 'chat-typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  /* ─────────────────────────────────────────────
     Send message
  ───────────────────────────────────────────── */
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isBusy) return;

    isBusy = true;
    setSendState(false);
    removeGreeting();

    /* Append user bubble */
    appendBubble('user', text);
    history.push({ role: 'user', content: text });
    inputEl.value = '';

    /* Show typing indicator */
    const typing = appendTyping();

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: history.slice(0, -1),   // send prior turns, not the one just added
        }),
      });

      typing.remove();

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status} — ${errText}`);
      }

      const data = await res.json();

      // Unwrap reply — backend should return a string, but guard against
      // the raw strands {role, content:[{text}]} object leaking through.
      let reply = data.response || data.error || '(no response)';
      if (typeof reply === 'object' && reply !== null) {
        const blocks = reply.content;
        if (Array.isArray(blocks)) {
          reply = blocks.map(b => (typeof b === 'object' ? b.text || '' : b)).join(' ').trim();
        } else {
          reply = JSON.stringify(reply);
        }
      }

      appendBubble(data.error ? 'error' : 'assistant', reply);
      history.push({ role: 'assistant', content: reply });

    } catch (err) {
      typing.remove();
      appendBubble('error', `⚠ ${err.message}`);
    } finally {
      isBusy = false;
      setSendState(true);
      inputEl.focus();
    }
  }

  function setSendState(enabled) {
    sendBtn.disabled = !enabled;
    inputEl.disabled = !enabled;
  }

  /* ─────────────────────────────────────────────
     Events
  ───────────────────────────────────────────── */
  sendBtn.addEventListener('click', sendMessage);

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  /* Close panel when pressing Escape */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen) closePanel();
  });

})();
