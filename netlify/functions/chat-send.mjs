import {
  OWNER_CHAT_ID,
  appendMessage,
  json,
  store,
  telegram,
  validSession,
} from './_chat-lib.mjs';

const MAX_LENGTH = 1000;
const RATE_LIMIT = 15; // messages
const RATE_WINDOW = 60_000; // per minute, per session

async function withinRateLimit(sessionId) {
  const key = `rate:${sessionId}`;
  const now = Date.now();
  const record = (await store().get(key, { type: 'json' })) || { count: 0, start: now };

  if (now - record.start > RATE_WINDOW) {
    await store().setJSON(key, { count: 1, start: now });
    return true;
  }
  if (record.count >= RATE_LIMIT) return false;

  await store().setJSON(key, { count: record.count + 1, start: record.start });
  return true;
}

export default async (req) => {
  if (req.method !== 'POST') return json({ error: 'Method not allowed' }, 405);

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: 'Invalid request' }, 400);
  }

  const { sessionId, text, page } = body;
  if (!validSession(sessionId)) return json({ error: 'Invalid session' }, 400);
  if (typeof text !== 'string') return json({ error: 'Invalid message' }, 400);

  const clean = text.trim().slice(0, MAX_LENGTH);
  if (!clean) return json({ error: 'Message is empty' }, 400);

  if (!(await withinRateLimit(sessionId))) {
    return json({ error: 'Too many messages. Wait a minute and try again.' }, 429);
  }

  const message = { from: 'visitor', text: clean, ts: Date.now() };
  await appendMessage(sessionId, message);

  const thread = await store().get(`msgs:${sessionId}`, { type: 'json' });
  const isFirst = thread.filter((m) => m.from === 'visitor').length === 1;

  const header = isFirst
    ? `New chat · ${sessionId}\n${typeof page === 'string' ? page.slice(0, 120) : '/'}`
    : `${sessionId}`;

  const sent = await telegram('sendMessage', {
    chat_id: OWNER_CHAT_ID,
    text: `${header}\n\n${clean}\n\n— reply to this message to answer`,
    disable_web_page_preview: true,
  });

  // Maps the Telegram message you'll reply to back to this visitor's session.
  await store().set(`tg:${sent.message_id}`, sessionId);

  return json({ ok: true, ts: message.ts });
};
