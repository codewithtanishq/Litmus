import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LandingPage } from './pages/LandingPage';
import { BattlePage } from './pages/BattlePage';
import { CheckmatePlaceholder } from './pages/CheckmatePlaceholder';
import { ResultsPlaceholder } from './pages/ResultsPlaceholder';
import './styles/global.css';

export function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/battle" element={<BattlePage />} />
          <Route path="/checkmate" element={<CheckmatePlaceholder />} />
          <Route path="/results" element={<ResultsPlaceholder />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

export default App;
