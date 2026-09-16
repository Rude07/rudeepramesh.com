import { BOT_TOKEN, readThread, validSession } from './_chat-lib.mjs';

const MIME = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  gif: 'image/gif',
};

export default async (req) => {
  const url = new URL(req.url);
  const sessionId = url.searchParams.get('sessionId');
  const fileId = url.searchParams.get('fileId');

  if (!validSession(sessionId)) return new Response('Invalid session', { status: 400 });
  if (!fileId || fileId.length > 200) return new Response('Invalid file', { status: 400 });

  // Authorization: the file must appear in this session's own thread. Without
  // this, anyone could pull arbitrary files out of the bot's storage.
  const thread = await readThread(sessionId);
  if (!thread.some((m) => m.fileId === fileId)) {
    return new Response('Not found', { status: 404 });
  }

  const infoRes = await fetch(
    `https://api.telegram.org/bot${BOT_TOKEN}/getFile?file_id=${encodeURIComponent(fileId)}`
  );
  const info = await infoRes.json();
  if (!info.ok) return new Response('Not found', { status: 404 });

  // The token lives only in this request, server-side. The browser never sees it.
  const fileRes = await fetch(
    `https://api.telegram.org/file/bot${BOT_TOKEN}/${info.result.file_path}`
  );
  if (!fileRes.ok) return new Response('Not found', { status: 404 });

  const ext = info.result.file_path.split('.').pop().toLowerCase();
  const bytes = await fileRes.arrayBuffer();

  return new Response(bytes, {
    headers: {
      'content-type': MIME[ext] || 'application/octet-stream',
      // Telegram file ids are stable, so this is safe to cache hard in the
      // visitor's own browser. private keeps it out of shared caches.
      'cache-control': 'private, max-age=86400',
    },
  });
};
