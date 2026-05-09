import { Activity } from 'lucide-react';

export default function PatternsBlock({ patterns }) {
  return (
    <>
      <h2 className="section-title">Устойчивые паттерны речи</h2>
      <section className="card">
        <ul className="patterns-list">
          {patterns.map((pattern, index) => (
            <li key={index}>
              <Activity size={14} className="list-bullet-icon" />
              <span>{pattern}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

