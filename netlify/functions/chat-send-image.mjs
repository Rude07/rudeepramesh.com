import {
  OWNER_CHAT_ID,
  BOT_TOKEN,
  appendMessage,
  json,
  store,
  validSession,
} from './_chat-lib.mjs';

// Netlify caps a function request at 6MB and base64 inflates by a third, so
// anything above this shouldn't have survived the client-side resize.
const MAX_BYTES = 3_500_000;
const RATE_LIMIT = 6; // images
const RATE_WINDOW = 300_000; // per five minutes, per session

async function withinRateLimit(sessionId) {
  const key = `rate-img:${sessionId}`;
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

  const { sessionId, dataUrl, page } = body;
  if (!validSession(sessionId)) return json({ error: 'Invalid session' }, 400);

  const match = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/.exec(
    typeof dataUrl === 'string' ? dataUrl : ''
  );
  if (!match) return json({ error: 'Unsupported image' }, 400);

  const [, mime, b64] = match;
  const bytes = Buffer.from(b64, 'base64');
  if (!bytes.length) return json({ error: 'Empty image' }, 400);
  if (bytes.length > MAX_BYTES) return json({ error: 'Image is too large' }, 413);

  if (!(await withinRateLimit(sessionId))) {
    return json({ error: 'Too many images. Wait a few minutes.' }, 429);
  }

  const ext = mime === 'image/png' ? 'png' : mime === 'image/webp' ? 'webp' : 'jpg';
  const form = new FormData();
  form.append('chat_id', String(OWNER_CHAT_ID));
  form.append(
    'caption',
    `Image · ${sessionId}\n${typeof page === 'string' ? page.slice(0, 120) : '/'}\n\n— reply to this message to answer`
  );
  form.append('photo', new Blob([bytes], { type: mime }), `upload.${ext}`);

  // No content-type header here on purpose: fetch sets the multipart boundary.
  const res = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendPhoto`, {
    method: 'POST',
    body: form,
  });
  const data = await res.json();
  if (!data.ok) return json({ error: 'Telegram rejected the image' }, 502);

  const ts = Date.now();
  await appendMessage(sessionId, { from: 'visitor', kind: 'image', ts });
  await store().set(`tg:${data.result.message_id}`, sessionId);

  return json({ ok: true, ts });
};
