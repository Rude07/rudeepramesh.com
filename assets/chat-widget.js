/* Live chat widget — monochrome, self-contained, no dependencies.
   Renders inside a shadow root so the host site's CSS can't reach it. */
(() => {
  const BASE = '/.netlify/functions';
  const KEY = 'rs-chat-session';
  const OPEN_KEY = 'rs-chat-open';

  const newId = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(10)))
      .map((b) => b.toString(36).padStart(2, '0'))
      .join('')
      .slice(0, 16);

  // sessionStorage, not localStorage: a refresh keeps the conversation alive
  // so your replies still land, but closing the tab wipes it for good.
  const sessionId = (() => {
    let id = sessionStorage.getItem(KEY);
    if (!/^[a-z0-9]{16}$/.test(id || '')) {
      id = newId();
      sessionStorage.setItem(KEY, id);
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
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter,
          Helvetica, Arial, sans-serif;
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
        width: 340px; height: min(520px, calc(100vh - 120px));
        background: var(--paper); color: var(--ink);
        border: 1px solid var(--hairline);
        display: none; flex-direction: column; overflow: hidden;
      }
      .panel[data-open] { display: flex; }

      header {
        display: flex; align-items: baseline; justify-content: space-between;
        gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--hairline);
        flex: 0 0 auto;
      }
      header h2 { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
      header p { font-size: 12px; color: var(--muted); }
      .close { background: none; border: none; color: var(--muted);
        cursor: pointer; font-size: 20px; line-height: 1; padding: 0 2px; }
      .close:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

      .log { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 16px;
        display: flex; flex-direction: column; gap: 10px; }
      .msg { max-width: 82%; padding: 9px 12px; font-size: 14px;
        line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }
      .msg.visitor { align-self: flex-end; background: var(--ink); color: var(--paper); }
      .msg.owner { align-self: flex-start; border: 1px solid var(--hairline); }
      .empty { font-size: 13px; color: var(--muted); line-height: 1.5; }
      .status { font-size: 12px; color: var(--muted); align-self: center; }

      form { display: flex; gap: 8px; padding: 12px;
        border-top: 1px solid var(--hairline); flex: 0 0 auto; }
      textarea {
        flex: 1; resize: none; border: none; background: none; color: var(--ink);
        font-size: 16px; line-height: 1.4; max-height: 90px; padding: 6px 2px;
      }
      textarea:focus { outline: none; }
      textarea::placeholder { color: var(--muted); }
      .send { background: none; border: none; color: var(--ink); cursor: pointer;
        font-size: 14px; font-weight: 600; padding: 6px 4px; }
      .send:disabled { color: var(--muted); cursor: default; }
      .send:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

      @media (max-width: 480px) {
        .panel { right: 12px; left: 12px; width: auto; bottom: 78px;
          height: min(460px, calc(100vh - 160px)); }
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
  const seen = new Set();

  // Each poll loop claims a generation number. Stopping bumps the counter, so
  // an older loop still waiting on fetch exits instead of running alongside a
  // newer one — which is what rendered replies two and four times over.
  let generation = 0;
  const stopPolling = () => { generation += 1; };

  const scroll = () => { log.scrollTop = log.scrollHeight; };

  function render(message) {
    const key = `${message.from}:${message.ts}:${message.text}`;
    if (seen.has(key)) return;
    seen.add(key);

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

  async function poll() {
    const mine = (generation += 1);
    let backoff = 1000;

    while (mine === generation) {
      try {
        const res = await fetch(
          `${BASE}/chat-poll?sessionId=${sessionId}&since=${since}`
        );
        if (!res.ok) throw new Error('poll failed');
        const data = await res.json();
        if (mine !== generation) return; // superseded while awaiting
        (data.messages || []).forEach(render);
        backoff = 1000;
      } catch {
        await new Promise((r) => setTimeout(r, backoff));
        backoff = Math.min(backoff * 2, 30000);
      }
    }
  }

  function open() {
    panel.setAttribute('data-open', '');
    launcher.setAttribute('aria-expanded', 'true');
    launcher.setAttribute('aria-label', 'Close chat');
    sessionStorage.setItem(OPEN_KEY, '1');
    input.focus();
    poll();
  }

  function close() {
    panel.removeAttribute('data-open');
    launcher.setAttribute('aria-expanded', 'false');
    launcher.setAttribute('aria-label', 'Open chat');
    sessionStorage.removeItem(OPEN_KEY);
    stopPolling();
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

  // Don't hold a connection open while the tab is backgrounded.
  document.addEventListener('visibilitychange', () => {
    if (!panel.hasAttribute('data-open')) return;
    if (document.hidden) stopPolling();
    else poll();
  });

  if (sessionStorage.getItem(OPEN_KEY)) open();
})();
