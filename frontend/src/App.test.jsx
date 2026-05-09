import { fireEvent, render, screen } from '@testing-library/react';

import App from './App.jsx';

describe('App smoke tests', () => {
  it('renders start screen', () => {
    render(<App />);
    expect(screen.getByText('Семантический Профайлер')).toBeInTheDocument();
  });

  it('shows demo profile after click', async () => {
    render(<App />);
    fireEvent.click(screen.getByText('Анализ профиля (Demo)'));
    expect(await screen.findByText(/Профиль:/)).toBeInTheDocument();
  });
});

