export const mockProfileData = {
  username: 'Александр (Demo)',
  demographics: {
    age: '20-25 (оценка)',
    gender: 'Мужской',
    occupation: 'Разработчик / IT-специалист',
    ageConfidence: 0.62,
    genderConfidence: 0.78,
    occupationConfidence: 0.7,
  },
  topicsAndInterests: [
    { name: 'Программирование', confidence: 0.92 },
    { name: 'Видеоигры', confidence: 0.74 },
    { name: 'Наука и Технологии', confidence: 0.55 },
    { name: 'Кино и Аниме', confidence: 0.41 },
  ],
  nlpAnalysis: {
    tonality: {
      positive: 45,
      neutral: 40,
      negative: 15,
      confidence: 0.45,
    },
    emotions: [
      { label: 'радость', percentage: 28, confidence: 0.86 },
      { label: 'интерес', percentage: 22, confidence: 0.74 },
      { label: 'спокойствие', percentage: 18, confidence: 0.66 },
      { label: 'удивление', percentage: 12, confidence: 0.61 },
      { label: 'раздражение', percentage: 10, confidence: 0.58 },
      { label: 'грусть', percentage: 10, confidence: 0.55 },
    ],
    communicationStyle:
      'Сбалансированный, склонный к аналитическому изложению. Доминирующая эмоция: «интерес» (22%).',
    communicationStyleConfidence: 0.58,
    speechPatterns: [
      { pattern: 'Разбивает сложные мысли на списки или абзацы', confidence: 0.42 },
      { pattern: "Связка: 'если' + 'тогда'", confidence: 0.81 },
      { pattern: 'Начинает контраргументы с логических конструкций', confidence: 0.37 },
    ],
    keywords: [
      { keyword: 'баг', confidence: 0.66 },
      { keyword: 'релиз', confidence: 0.58 },
      { keyword: 'фича', confidence: 0.52 },
      { keyword: 'код', confidence: 1.0 },
      { keyword: 'дедлайн', confidence: 0.44 },
    ],
  },
};
