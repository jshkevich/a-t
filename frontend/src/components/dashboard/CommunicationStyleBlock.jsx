import { MessageSquare } from 'lucide-react';

export default function CommunicationStyleBlock({ communicationStyle }) {
  return (
    <>
      <h2 className="section-title">Стиль коммуникации</h2>
      <section className="card text-block">
        <MessageSquare size={18} className="icon-inline" />
        {communicationStyle}
      </section>
    </>
  );
}

