import { json, readThread, sleep, validSession } from './_chat-lib.mjs';

// Netlify caps synchronous functions at 10s. Hold just under it, then return
// empty so the browser reconnects — this is cheaper than polling on a timer
// and delivers replies in well under a second.
const HOLD_MS = 8500;
const CHECK_EVERY = 600;

export default async (req) => {
  const url = new URL(req.url);
  const sessionId = url.searchParams.get('sessionId');
  const since = Number(url.searchParams.get('since') || 0);
  const wantsHistory = url.searchParams.get('history') === '1';

  if (!validSession(sessionId)) return json({ error: 'Invalid session' }, 400);

  if (wantsHistory) {
    const thread = await readThread(sessionId);
    return json({ messages: thread });
  }

  const deadline = Date.now() + HOLD_MS;
  while (Date.now() < deadline) {
    const thread = await readThread(sessionId);
    const fresh = thread.filter((m) => m.from === 'owner' && m.ts > since);
    if (fresh.length) return json({ messages: fresh });
    await sleep(CHECK_EVERY);
  }

  return json({ messages: [] });
};
