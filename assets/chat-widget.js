/* Live chat widget — monochrome, self-contained, no dependencies.
   Renders inside a shadow root so the host site's CSS can't reach it. */
(() => {
  const BASE = '/.netlify/functions';
  const KEY = 'rs-chat-session';
  const OPEN_KEY = 'rs-chat-open';

  const sessionId = (() => {
    let id = localStorage.getItem(KEY);
    if (!/^[a-z0-9]{16}$/.test(id || '')) {
      id = Array.from(crypto.getRandomValues(new Uint8Array(10)))
        .map((b) => b.toString(36).padStart(2, '0'))
        .join('')
        .slice(0, 16);
      localStorage.setItem(KEY, id);
    }
    return id;
  })();

  const host = document.createElement('div');
  host.setAttribute('data-chat-widget', '');
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });

  root.innerHTML = `
    <style>
      :host {
        --ink: #000;
        --paper: #fff;
        --hairline: rgba(0, 0, 0, 0.18);
        --muted: rgba(0, 0, 0, 0.5);
        all: initial;
        font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      }
      @media (prefers-color-scheme: dark) {
        :host {
          --ink: #fff;
          --paper: #000;
          --hairline: rgba(255, 255, 255, 0.24);
          --muted: rgba(255, 255, 255, 0.55);
        }
      }
      * { box-sizing: border-box; margin: 0; font-family: inherit; }

      .launcher {
        position: fixed; right: 20px; bottom: 20px; z-index: 2147483000;
        width: 52px; height: 52px; border-radius: 50%;
        background: var(--ink); color: var(--paper);
        border: none; cursor: pointer;
        display: grid; place-items: center;
      }
      .launcher:focus-visible { outline: 2px solid var(--ink); outline-offset: 3px; }
      .launcher svg { width: 22px; height: 22px; fill: none;
        stroke: currentColor; stroke-width: 1.75; }

      .panel {
        position: fixed; right: 20px; bottom: 84px; z-index: 2147483000;
        width: 340px; max-height: min(520px, calc(100vh - 120px));
        background: var(--paper); color: var(--ink);
        border: 1px solid var(--hairline);
        display: none; flex-direction: column; overflow: hidden;
      }
      .panel[data-open] { display: flex; }

      header {
        display: flex; align-items: baseline; justify-content: space-between;
        gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--hairline);
      }
      header h2 { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
      header p { font-size: 12px; color: var(--muted); }
      .close { background: none; border: none; color: var(--muted);
        cursor: pointer; font-size: 20px; line-height: 1; padding: 0 2px; }
      .close:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

      .log { flex: 1; overflow-y: auto; padding: 16px;
        display: flex; flex-direction: column; gap: 10px; }
      .msg { max-width: 82%; padding: 9px 12px; font-size: 14px;
        line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }
      .msg.visitor { align-self: flex-end; background: var(--ink); color: var(--paper); }
      .msg.owner { align-self: flex-start; border: 1px solid var(--hairline); }
      .empty { font-size: 13px; color: var(--muted); line-height: 1.5; }
      .status { font-size: 12px; color: var(--muted); align-self: center; }

      form { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--hairline); }
      textarea {
        flex: 1; resize: none; border: none; background: none; color: var(--ink);
        font-size: 14px; line-height: 1.4; max-height: 90px; padding: 6px 2px;
      }
      textarea:focus { outline: none; }
      textarea::placeholder { color: var(--muted); }
      .send { background: none; border: none; color: var(--ink); cursor: pointer;
        font-size: 14px; font-weight: 600; padding: 6px 4px; }
      .send:disabled { color: var(--muted); cursor: default; }
      .send:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

      @media (max-width: 480px) {
        .panel { right: 12px; left: 12px; width: auto; bottom: 78px; }
        .launcher { right: 14px; bottom: 14px; }
      }
      @media (prefers-reduced-motion: no-preference) {
        .panel[data-open] { animation: rise 160ms ease-out; }
        @keyframes rise { from { opacity: 0; transform: translateY(6px); } }
      }
    </style>

    <button class="launcher" aria-label="Open chat" aria-expanded="false">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12Z"
              stroke-linejoin="round"/>
      </svg>
    </button>

    <section class="panel" role="dialog" aria-label="Chat with Rude">
      <header>
        <div>
          <h2>Chat with Rude</h2>
          <p>Usually replies within a few minutes</p>
        </div>
        <button class="close" aria-label="Close chat">&times;</button>
      </header>
      <div class="log" aria-live="polite">
        <p class="empty">Ask about a project, a rate, or a timeline. Messages reach me directly.</p>
      </div>
      <form>
        <textarea rows="1" placeholder="Write a message" maxlength="1000"
                  aria-label="Message"></textarea>
        <button class="send" type="submit">Send</button>
      </form>
    </section>
  `;

  const $ = (sel) => root.querySelector(sel);
  const launcher = $('.launcher');
  const panel = $('.panel');
  const log = $('.log');
  const form = $('form');
  const input = $('textarea');
  const sendBtn = $('.send');

  let since = 0;
  let polling = false;
  let started = false;

  const scroll = () => { log.scrollTop = log.scrollHeight; };

  function render(message) {
    $('.empty')?.remove();
    const el = document.createElement('div');
    el.className = `msg ${message.from}`;
    el.textContent = message.text;
    log.appendChild(el);
    since = Math.max(since, message.ts || 0);
    scroll();
  }

  function status(text) {
    let el = $('.status');
    if (!text) return el?.remove();
    if (!el) {
      el = document.createElement('p');
      el.className = 'status';
      log.appendChild(el);
    }
    el.textContent = text;
    scroll();
  }

  async function loadHistory() {
    try {
      const res = await fetch(
        `${BASE}/chat-poll?sessionId=${sessionId}&history=1`
      );
      const data = await res.json();
      (data.messages || []).forEach(render);
    } catch {
      /* An empty log is a fine starting state. */
    }
  }

  async function poll() {
    if (polling) return;
    polling = true;
    let backoff = 1000;

    while (polling) {
      try {
        const res = await fetch(
          `${BASE}/chat-poll?sessionId=${sessionId}&since=${since}`
        );
        if (!res.ok) throw new Error('poll failed');
        const data = await res.json();
        (data.messages || []).forEach(render);
        backoff = 1000;
      } catch {
        await new Promise((r) => setTimeout(r, backoff));
        backoff = Math.min(backoff * 2, 30000);
      }
    }
  }

  async function open() {
    panel.setAttribute('data-open', '');
    launcher.setAttribute('aria-expanded', 'true');
    launcher.setAttribute('aria-label', 'Close chat');
    sessionStorage.setItem(OPEN_KEY, '1');
    input.focus();

    if (!started) {
      started = true;
      await loadHistory();
    }
    poll();
  }

  function close() {
    panel.removeAttribute('data-open');
    launcher.setAttribute('aria-expanded', 'false');
    launcher.setAttribute('aria-label', 'Open chat');
    sessionStorage.removeItem(OPEN_KEY);
    polling = false;
    launcher.focus();
  }

  launcher.addEventListener('click', () =>
    panel.hasAttribute('data-open') ? close() : open()
  );
  $('.close').addEventListener('click', close);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.hasAttribute('data-open')) close();
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 90)}px`;
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    sendBtn.disabled = true;
    input.value = '';
    input.style.height = 'auto';
    status('');

    try {
      const res = await fetch(`${BASE}/chat-send`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ sessionId, text, page: location.pathname }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Message did not send.');
      render({ from: 'visitor', text, ts: data.ts });
    } catch (err) {
      status(err.message || 'Message did not send. Try again.');
      input.value = text;
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });

  // Stop holding a connection open while the tab is in the background.
  document.addEventListener('visibilitychange', () => {
    if (!panel.hasAttribute('data-open')) return;
    if (document.hidden) polling = false;
    else poll();
  });

  if (sessionStorage.getItem(OPEN_KEY)) open();
})();
