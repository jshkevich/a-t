import { Hash } from 'lucide-react';

export default function KeywordsBlock({ keywords }) {
  return (
    <>
      <h2 className="section-title">Ключевые слова (Лексикон)</h2>
      <section className="card">
        <div className="tags-container">
          {keywords.map((word, index) => (
            <span key={index} className="tag tag-keyword">
              <Hash size={12} /> {word}
            </span>
          ))}
        </div>
      </section>
    </>
  );
}

