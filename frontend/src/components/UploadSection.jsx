import { Brain, Upload } from 'lucide-react';

export default function UploadSection({ onDemoLoad, onFileUpload }) {
  return (
    <div className="app-theme center-screen">
      <div className="welcome-container">
        <Brain size={64} className="accent-icon" />
        <h1>A-T</h1>
        <p className="subtitle">Веб-приложение для анализа Telegram‑чатов</p>

        {/* <button className="primary-btn" onClick={onDemoLoad}>
          Анализ профиля (Demo)
        </button> */}

        <label className="secondary-btn">
          <Upload size={20} /> Загрузить JSON из Telegram
          <input type="file" accept=".json" onChange={onFileUpload} style={{ display: 'none' }} />
        </label>
      </div>
    </div>
  );
}

