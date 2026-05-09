const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function analyzeProfile(username, messages) {
  const response = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, messages }),
  });

  if (!response.ok) {
    let detail = 'Ошибка ответа от сервера';
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = String(body.detail);
      }
    } catch {
      // keep fallback detail
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function semanticSearch(messages, query, topK = 5, minScore = 0.2) {
  const response = await fetch(`${API_URL}/semantic-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, query, topK, minScore }),
  });

  if (!response.ok) {
    let detail = 'Ошибка ответа от сервера';
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // keep fallback detail
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function telegramSemanticSearch(chat, query, topUsers = 5, perUserK = 2, minScore = 0.25) {
  const response = await fetch(`${API_URL}/telegram/semantic-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat, query, topUsers, perUserK, minScore }),
  });

  if (!response.ok) {
    let detail = 'Ошибка ответа от сервера';
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // keep fallback detail
    }
    throw new Error(detail);
  }

  return response.json();
}

export function getApiBaseUrl() {
  return API_URL;
}

