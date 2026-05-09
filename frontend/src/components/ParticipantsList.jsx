import { useMemo, useState } from 'react';

export default function ParticipantsList({ participants, onSelect, onCancel, onSemanticSearch }) {
  const [query, setQuery] = useState('');
  const [semanticQuery, setSemanticQuery] = useState('');
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState('');
  const [semanticResults, setSemanticResults] = useState([]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return participants;
    return participants.filter((user) => (
      user.name.toLowerCase().includes(q) || String(user.id).toLowerCase().includes(q)
    ));
  }, [participants, query]);

  const runSemantic = async () => {
    const q = semanticQuery.trim();
    if (!q || !onSemanticSearch) return;
    setSemanticLoading(true);
    setSemanticError('');
    try {
      const resp = await onSemanticSearch(q, 6, 2, 0.25);
      setSemanticResults(resp?.results ?? []);
    } catch (e) {
      setSemanticError(e?.message || 'Не удалось выполнить поиск по чату');
    } finally {
      setSemanticLoading(false);
    }
  };

  return (
    <div className="app-theme center-screen">
      <div className="card" style={{ width: '100%', maxWidth: '520px' }}>
        <h2 className="section-title" style={{ margin: '0 0 15px 0', textAlign: 'center' }}>
          Кого будем анализировать?
        </h2>
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px', marginBottom: '10px' }}>
          Найдено участников: {participants.length} (отсортировано по сообщениям)
        </p>

        <div className="chat-semantic-search">
          <div className="chat-semantic-search__title">Поиск по всему чату</div>
          <div className="chat-semantic-search__bar">
            <input
              value={semanticQuery}
              onChange={(e) => setSemanticQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') runSemantic();
              }}
              placeholder="Поиск по фразе или слову"
              className="chat-semantic-search__input"
            />
            <button className="secondary-btn chat-semantic-search__btn" onClick={runSemantic} disabled={semanticLoading}>
              {semanticLoading ? 'Ищу...' : 'Найти'}
            </button>
          </div>
          {semanticError ? <div className="chat-semantic-search__error">{semanticError}</div> : null}
          {semanticResults.length ? (
            <div className="chat-semantic-search__results">
              {semanticResults.map((u) => (
                <div key={u.userId} className="chat-semantic-search__item">
                  <div className="chat-semantic-search__item-head">
                    <div className="chat-semantic-search__who">
                      <b>{Math.round((u.score ?? 0) * 100)}%</b> {u.name}
                    </div>
                    <button className="secondary-btn chat-semantic-search__profile-btn" onClick={() => onSelect(u.userId, u.name)} style={{ width: '60%' }}>
                      Профилировать
                    </button>
                  </div>
                  {u.matches?.length ? (
                    <div className="chat-semantic-search__matches">
                      {u.matches.map((m, idx) => (
                        <div key={`${u.userId}-${m.messageIndex}-${idx}`} className="chat-semantic-search__match">
                          <span className="chat-semantic-search__match-score">{Math.round((m.score ?? 0) * 100)}%</span>
                          <span className="chat-semantic-search__match-text">{m.message}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="sep" style={{ margin: '14px 0' }} />

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск по имени или ID..."
          style={{
            width: '90%',
            marginBottom: '12px',
            padding: '10px 12px',
            borderRadius: '10px',
            border: '1px solid var(--card-border)',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
          }}
        />

        <div className="participants-list">
          {filtered.map((user) => (
            <button key={user.id} className="user-select-btn" onClick={() => onSelect(user.id, user.name)}>
              <div className="user-avatar">{user.name.charAt(0).toUpperCase()}</div>
              <span>{user.name} ({user.messageCount ?? 0})</span>
            </button>
          ))}
        </div>

        <button className="secondary-btn" style={{ marginTop: '15px' }} onClick={onCancel}>
          Отмена
        </button>
      </div>
    </div>
  );
}

