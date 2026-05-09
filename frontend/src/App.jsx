import React, { useState } from 'react';
import './App.css';
import { analyzeProfile, getApiBaseUrl, semanticSearch, telegramSemanticSearch } from './api/analyzeClient.js';
import NotificationBanner from './components/NotificationBanner.jsx';
import ParticipantsList from './components/ParticipantsList.jsx';
import ProfileDashboard from './components/ProfileDashboard.jsx';
import UploadSection from './components/UploadSection.jsx';
import { mockProfileData } from './constants/mockProfileData.js';
import { getParticipants, getUserMessages } from './utils/chat.js';

function App() {
  const [status, setStatus] = useState('idle');
  const [data, setData] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [rawChat, setRawChat] = useState(null);
  const [analyzedMessages, setAnalyzedMessages] = useState([]);
  const [error, setError] = useState('');

  const handleDemoLoad = () => {
    setError('');
    setStatus('loading');
    setTimeout(() => {
      setData(mockProfileData);
      setStatus('report');
    }, 800);
  };

  const handleFileUpload = (event) => {
    setError('');
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target.result);
        if (!json.messages || !Array.isArray(json.messages)) {
          throw new Error('Неверный формат: отсутствует массив messages');
        }

        const usersList = getParticipants(json);

        if (usersList.length === 0) {
          setError('В этом файле не найдено текстовых сообщений с отправителями.');
          return;
        }

        setParticipants(usersList);
        setRawChat(json);
        setStatus('picking_user');
      } catch (err) {
        setError('Ошибка в формате файла Telegram JSON. Убедитесь, что это корректный дамп.');
        console.error(err);
      }
    };
    reader.readAsText(file);
  };

  const analyzeSelectedUser = async (userId, userName) => {
    setError('');
    setStatus('loading');

    const userMessages = getUserMessages(rawChat, userId);

    if (userMessages.length === 0) {
      setError('У этого пользователя нет текстовых сообщений.');
      setStatus('picking_user');
      return;
    }

    try {
      const result = await analyzeProfile(userName, userMessages);
      setAnalyzedMessages(userMessages);
      setData(result);
      setStatus('report');
    } catch (err) {
      setError(`Ошибка связи с сервером (${getApiBaseUrl()}). Убедитесь, что Python-бэкенд запущен.`);
      setStatus('picking_user');
      console.error(err);
    }
  };

  if (status === 'idle') {
    return (
      <>
        <NotificationBanner message={error} />
        <UploadSection onDemoLoad={handleDemoLoad} onFileUpload={handleFileUpload} />
      </>
    );
  }

  if (status === 'picking_user') {
    return (
      <>
        <NotificationBanner message={error} />
        <ParticipantsList
          participants={participants}
          onSelect={analyzeSelectedUser}
          onSemanticSearch={(query, topUsers, perUserK, minScore) => telegramSemanticSearch(rawChat, query, topUsers, perUserK, minScore)}
          onCancel={() => setStatus('idle')}
        />
      </>
    );
  }

  if (status === 'loading') {
    return (
      <div className="app-theme center-screen">
        <div className="spinner"></div>
        <p className="loading-text">Синтез семантического профиля...</p>
      </div>
    );
  }

  return (
    <ProfileDashboard
      data={data}
      onSemanticSearch={(query, topK, minScore) => semanticSearch(analyzedMessages, query, topK, minScore)}
      onBack={() => {
        setStatus('idle');
        setData(null);
        setAnalyzedMessages([]);
        setError('');
      }}
    />
  );
}

export default App;

