import { getStore } from '@netlify/blobs';

export const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
export const OWNER_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
export const WEBHOOK_SECRET = process.env.TELEGRAM_WEBHOOK_SECRET;

// Strong consistency matters: the poll function must see a reply the instant
// the webhook function writes it.
export const store = () => getStore({ name: 'chat', consistency: 'strong' });

export const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Session ids are generated client-side. Only accept the exact shape we issue,
// so nobody can use this as a scratch key-value store.
export const validSession = (id) => typeof id === 'string' && /^[a-z0-9]{16}$/.test(id);

export async function readThread(id) {
  return (await store().get(`msgs:${id}`, { type: 'json' })) || [];
}

export async function appendMessage(id, message) {
  const thread = await readThread(id);
  thread.push(message);
  // Keep threads bounded so a single session can't grow without limit.
  const trimmed = thread.slice(-200);
  await store().setJSON(`msgs:${id}`, trimmed);
  return message;
}

export async function telegram(method, payload) {
  const res = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(`Telegram ${method} failed: ${data.description}`);
  return data.result;
}
