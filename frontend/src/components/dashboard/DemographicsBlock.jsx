import { Briefcase, User } from 'lucide-react';

export default function DemographicsBlock({ demographics }) {
  return (
    <section className="card">
      <div className="info-row">
        <User size={18} className="icon-blue" />
        <span className="info-label">Пол / Возраст:</span>
        <span className="info-value">
          {demographics.gender}, {demographics.age}
        </span>
      </div>
      <div className="info-row">
        <Briefcase size={18} className="icon-blue" />
        <span className="info-label">Занятость:</span>
        <span className="info-value">{demographics.occupation}</span>
      </div>
    </section>
  );
}

