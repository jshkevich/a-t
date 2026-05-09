export function extractText(textData) {
  if (typeof textData === 'string') return textData;
  if (Array.isArray(textData)) {
    return textData.map((part) => (typeof part === 'string' ? part : part.text || '')).join('');
  }
  return '';
}

export function getParticipants(chatJson) {
  const usersMap = {};
  const messageCount = {};
  chatJson.messages.forEach((message) => {
    if (message.from && message.from_id && message.type === 'message') {
      usersMap[message.from_id] = message.from;
      const text = extractText(message.text);
      if (text.trim().length > 0) {
        messageCount[message.from_id] = (messageCount[message.from_id] ?? 0) + 1;
      }
    }
  });

  return Object.entries(usersMap)
    .map(([id, name]) => ({ id, name, messageCount: messageCount[id] ?? 0 }))
    .sort((a, b) => (b.messageCount - a.messageCount) || a.name.localeCompare(b.name, 'ru'));
}

export function getUserMessages(chatJson, userId) {
  return chatJson.messages
    .filter((message) => message.from_id === userId && message.type === 'message')
    .map((message) => extractText(message.text))
    .filter((text) => text.trim().length > 0);
}

