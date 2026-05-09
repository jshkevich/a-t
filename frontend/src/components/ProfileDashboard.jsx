import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

const EMOTION_EMOJIS = {
  'радость': '😊', 'счастье': '😊', 'грусть': '😢', 'печаль': '😢',
  'гнев': '😠', 'злость': '😠', 'раздражение': '😤', 'страх': '😨',
  'тревога': '😰', 'отвращение': '🤢', 'стыд': '😳', 'вина': '😔',
  'скука': '😴', 'удивление': '😮', 'интерес': '🤔', 'нейтральное': '😐',
  'спокойствие': '😌', 'обожание': '😍', 'нежность': '🥰', 'восхищение': '🤩',
  'удовольствие': '😋', 'любовь': '❤️', 'надежда': '🌟', 'решимость': '💪',
  'гордость': '👑', 'усталость': '😩', 'разочарование': '😞', 'одиночество': '🥺',
  'ревность': '😟',
};

const EMOTION_RU = {
  joy: 'радость',
  happiness: 'счастье',
  sadness: 'грусть',
  anger: 'гнев',
  fear: 'страх',
  disgust: 'отвращение',
  surprise: 'удивление',
  neutral: 'нейтральное',
};

const PIE_COLORS = ['#38bdf8', '#10b981', '#f59e0b', '#f43f5e', '#a78bfa', '#94a3b8', '#22c55e', '#fb7185'];

function clamp01(x) {
  const n = Number(x);
  if (Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function formatConfidence(value) {
  const v = clamp01(value);
  return `${Math.round(v * 100)}%`;
}

function ConfidencePill({ value }) {
  const v = clamp01(value);
  if (v <= 0) return null;
  return <span className="confidence-pill">Уверенность {formatConfidence(v)}</span>;
}

function normalizeEmotionLabel(label) {
  const raw = String(label ?? '').trim();
  const lower = raw.toLowerCase();
  return EMOTION_RU[lower] || lower;
}

function TonalityBar({ tonality }) {
  return (
    <div className="compact-row">
      <span className="row-label">
        Тональность
        <div className="row-sub">
          <ConfidencePill value={tonality?.confidence} />
        </div>
      </span>
      <div className="tonality-compact">
        <div className="tonality-track">
          <div className="bar-pos" style={{ width: `${tonality.positive}%` }} />
          <div className="bar-neu" style={{ width: `${tonality.neutral}%` }} />
          <div className="bar-neg" style={{ width: `${tonality.negative}%` }} />
        </div>
        <div className="tonality-nums">
          <span className="t-pos">+{tonality.positive}%</span>
          <span className="t-neu">~{tonality.neutral}%</span>
          <span className="t-neg">−{tonality.negative}%</span>
        </div>
      </div>
    </div>
  );
}

function EmotionRow({ emotions }) {
  if (!emotions.length) return null;
  const pieData = emotions.map((e) => ({
    name: normalizeEmotionLabel(e.label),
    value: e.percentage,
  }));
  return (
    <div className="compact-row emotion-row">
      <span className="row-label">Эмоции</span>
      <div className="emotion-grid">
        <div className="emotion-chips">
          {emotions.slice(0, 8).map((e, i) => {
            const ru = normalizeEmotionLabel(e.label);
            return (
              <span key={i} className="emo-chip">
                {EMOTION_EMOJIS[ru] || '💬'} {ru} <b>{e.percentage}%</b>
                <span className="emo-conf">{formatConfidence(e.confidence)}</span>
              </span>
            );
          })}
        </div>
        <div className="emotion-pie">
          <div className="emotion-pie-title">Распределение</div>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={2}>
                {pieData.map((_, idx) => (
                  <Cell key={`cell-${idx}`} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(val, name) => [`${val}%`, String(name)]}
                contentStyle={{ background: '#0b1220', border: '1px solid #334155', borderRadius: 12, color: '#f8fafc' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="compact-row">
      <span className="row-label">{label}</span>
      <span className="row-value">{value || '—'}</span>
    </div>
  );
}

function InterestsRow({ topics }) {
  if (!topics || !topics.length) return null;
  return (
    <div className="compact-row">
      <span className="row-label">Интересы</span>
      <div className="interest-chips">
        {topics.slice(0, 8).map((t, i) => (
          <span key={i} className="int-chip">
            {t.name}
            <span className="chip-conf">{formatConfidence(t.confidence)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function KeywordsRow({ keywords }) {
  if (!keywords || !keywords.length) return null;
  return (
    <div className="compact-row">
      <span className="row-label">Ключевые слова</span>
      <div className="kw-chips">
        {keywords.slice(0, 10).map((w, i) => (
          <span key={i} className="kw-chip">
            {w.keyword}
            <span className="chip-conf">{formatConfidence(w.confidence)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function PatternsRow({ patterns }) {
  if (!patterns || !patterns.length) return null;
  return (
    <div className="compact-row">
      <span className="row-label">Паттерны речи</span>
      <div className="patterns-mini">
        {patterns.slice(0, 4).map((p, i) => (
          <span key={i} className="pat-item">
            {p.pattern}
            <span className="pat-conf">{formatConfidence(p.confidence)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function SemanticSearchRow({ onSearch }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    try {
      const response = await onSearch(q, 5, 0.2);
      setResults(response?.results ?? []);
    } catch (err) {
      setError(err.message || 'Не удалось выполнить semantic поиск');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="semantic-search">
      <div className="semantic-search__head">
        <div className="semantic-search__title">Semantic поиск сообщений</div>
        <div className="semantic-search__hint">
          Введите фразу — найдём самые похожие сообщения (по смыслу).
        </div>
      </div>

      <div className="semantic-search__bar">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') runSearch();
          }}
          placeholder="Например: конфликт на работе"
          className="semantic-search__input"
        />
        <button className="secondary-btn semantic-search__btn" disabled={loading} onClick={runSearch}>
          {loading ? 'Ищу...' : 'Искать'}
        </button>
      </div>

      {error ? <div className="semantic-search__error">{error}</div> : null}
      {results.length > 0 ? (
        <div className="semantic-search__results">
          {results.map((item, idx) => (
            <div key={`${item.index ?? 'i'}-${idx}`} className="semantic-search__item">
              <div className="semantic-search__score">{Math.round(item.score * 100)}%</div>
              <div className="semantic-search__msg">{item.message}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function ProfileDashboard({ data, onBack, onSemanticSearch }) {
  const { demographics, topicsAndInterests, nlpAnalysis } = data;
  return (
    <div className="app-theme">
      <header className="app-header">
        <button className="icon-button" onClick={onBack}>
          <ArrowLeft size={24} color="#fff" />
        </button>
        <span className="header-title">Профиль: {data.username}</span>
        <div style={{ width: 24 }}></div>
      </header>

      <main className="compact-main">
        <section className="card semantic-search-card">
          <SemanticSearchRow onSearch={onSemanticSearch} />
        </section>
        <div style={{ height: 12 }} />
        <section className="card">
          <div className="compact-row">
            <span className="row-label">
              Пол / Возраст
              <div className="row-sub">
                <ConfidencePill value={Math.min(clamp01(demographics.genderConfidence), clamp01(demographics.ageConfidence))} />
              </div>
            </span>
            <span className="row-value">
              {demographics.gender}, {demographics.age}
            </span>
          </div>
          <div className="compact-row">
            <span className="row-label">
              Занятость
              <div className="row-sub">
                <ConfidencePill value={demographics.occupationConfidence} />
              </div>
            </span>
            <span className="row-value">{demographics.occupation || '—'}</span>
          </div>
          <div className="sep" />
          <TonalityBar tonality={nlpAnalysis.tonality} />
          <EmotionRow emotions={nlpAnalysis.emotions} />
          <div className="sep" />
          <InterestsRow topics={topicsAndInterests} />
          <div className="sep" />
          <KeywordsRow keywords={nlpAnalysis.keywords} />
          <div className="sep" />
          <div className="compact-row">
            <span className="row-label">
              Стиль общения
              <div className="row-sub">
                <ConfidencePill value={nlpAnalysis.communicationStyleConfidence} />
              </div>
            </span>
            <span className="row-value">{nlpAnalysis.communicationStyle || '—'}</span>
          </div>
          <div className="sep" />
          <PatternsRow patterns={nlpAnalysis.speechPatterns} />
        </section>
      </main>
    </div>
  );
}
