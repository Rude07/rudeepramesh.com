import {
  OWNER_CHAT_ID,
  WEBHOOK_SECRET,
  appendMessage,
  store,
  telegram,
} from './_chat-lib.mjs';

// Telegram retries on non-2xx, so we return 200 for everything we've decided
// to ignore — only genuine failures should bounce.
const ok = () => new Response('ok');

export default async (req) => {
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405 });

  if (req.headers.get('x-telegram-bot-api-secret-token') !== WEBHOOK_SECRET) {
    return new Response('Forbidden', { status: 403 });
  }

  let update;
  try {
    update = await req.json();
  } catch {
    return ok();
  }

  const msg = update.message;
  if (!msg?.text) return ok();
  if (String(msg.chat.id) !== String(OWNER_CHAT_ID)) return ok();

  if (!msg.reply_to_message) {
    await telegram('sendMessage', {
      chat_id: OWNER_CHAT_ID,
      text: 'Swipe-reply to a visitor message to answer it. A plain message has no session attached, so it goes nowhere.',
    });
    return ok();
  }

  const sessionId = await store().get(`tg:${msg.reply_to_message.message_id}`, {
    type: 'text',
  });

  if (!sessionId) {
    await telegram('sendMessage', {
      chat_id: OWNER_CHAT_ID,
      text: "That message isn't linked to a session — it may be older than the stored history. Reply to a newer one.",
    });
    return ok();
  }

  await appendMessage(sessionId, {
    from: 'owner',
    text: msg.text.slice(0, 2000),
    ts: Date.now(),
  });

  // Lets your reply be replied to as well, so a thread stays continuous.
  await store().set(`tg:${msg.message_id}`, sessionId);

  return ok();
};
