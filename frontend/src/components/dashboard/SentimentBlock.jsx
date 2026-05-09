const EMOTION_EMOJIS = {
  'радость': '😊',
  'счастье': '😊',
  'грусть': '😢',
  'печаль': '😢',
  'гнев': '😠',
  'злость': '😠',
  'раздражение': '😤',
  'страх': '😨',
  'тревога': '😰',
  'отвращение': '🤢',
  'стыд': '😳',
  'вина': '😔',
  'скука': '😴',
  'удивление': '😮',
  'интерес': '🤔',
  'нейтральное': '😐',
  'спокойствие': '😌',
  'обожание': '😍',
  'нежность': '🥰',
  'восхищение': '🤩',
  'удовольствие': '😋',
  'любовь': '❤️',
  'надежда': '🌟',
  'решимость': '💪',
  'гордость': '👑',
  'усталость': '😩',
  'разочарование': '😞',
  'одиночество': '🥺',
  'ревность': '😟',
};

export default function SentimentBlock({ tonality, emotions = [] }) {
  return (
    <>
      <h2 className="section-title">Тональность и эмоции</h2>
      <section className="card">
        <div className="tonality-bar-wrapper">
          <div className="tonality-labels">
            <span style={{ color: '#10b981' }}>Поз {tonality.positive}%</span>
            <span style={{ color: '#94a3b8' }}>Нейтр {tonality.neutral}%</span>
            <span style={{ color: '#f43f5e' }}>Нег {tonality.negative}%</span>
          </div>
          <div className="tonality-line">
            <div style={{ width: `${tonality.positive}%`, background: '#10b981' }}></div>
            <div style={{ width: `${tonality.neutral}%`, background: '#64748b' }}></div>
            <div style={{ width: `${tonality.negative}%`, background: '#f43f5e' }}></div>
          </div>
        </div>

        {emotions.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <div
              style={{
                fontSize: '13px',
                color: 'var(--text-muted)',
                marginBottom: '10px',
                fontWeight: 600,
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
              }}
            >
              Эмоциональный профиль
            </div>
            {emotions.map((emotion, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '5px 0',
                  fontSize: '14px',
                  borderBottom:
                    idx < emotions.length - 1 ? '1px solid var(--border-color)' : 'none',
                }}
              >
                <span style={{ color: '#cbd5e1' }}>
                  {EMOTION_EMOJIS[emotion.label.toLowerCase()] || '💬'} {emotion.label}
                </span>
                <span
                  style={{
                    color: 'var(--accent-blue)',
                    fontWeight: 600,
                    minWidth: '40px',
                    textAlign: 'right',
                  }}
                >
                  {emotion.percentage}%
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
