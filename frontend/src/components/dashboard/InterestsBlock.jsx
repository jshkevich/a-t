export default function InterestsBlock({ topics }) {
  return (
    <>
      <h2 className="section-title">Тематика и интересы</h2>
      <section className="card">
        <div className="tags-container">
          {topics.map((topic, index) => (
            <span key={index} className="tag tag-interest">
              {topic}
            </span>
          ))}
        </div>
      </section>
    </>
  );
}

