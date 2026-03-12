import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import MyDetailsModal from './components/MyDetailsModal';
import MyReportsModal from './components/MyReportsModal';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import AISummary from './pages/AISummary';
import SummaryPage from './pages/SummaryPage';
import Translation from './pages/Translation';
import HealthInsights from './pages/HealthInsights';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import './styles/global.css';
import './styles/navbar.css';
import './styles/dropdown.css';
import './styles/modal.css';
import './styles/reports-modal.css';
import './styles/footer.css';
import './styles/language-selector.css';
import './styles/report-card.css';
import './styles/summary-page.css';
import './styles/summary-navbar.css';
import './styles/translation.css';
import './styles/homepage.css';
import './styles/upload.css';
import './styles/auth.css';

function AppContent() {
  const { user } = useAuth();

  // Modal state lives here so Navbar (and any page) can trigger the same modals
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showReportsModal, setShowReportsModal] = useState(false);
  const [userName, setUserName] = useState('');

  useEffect(() => {
    // Seed anonymous userId if not present
    if (!localStorage.getItem('userId')) {
      localStorage.setItem('userId', `user_${Date.now()}`);
    }
    // Pick up stored name
    const stored = localStorage.getItem('userName');
    if (stored) setUserName(stored);
  }, []);

  // Keep userName in sync when user logs in
  useEffect(() => {
    if (user?.name) {
      setUserName(user.name);
      localStorage.setItem('userName', user.name);
    }
  }, [user]);

  const handleNameUpdate = (name) => {
    setUserName(name);
    localStorage.setItem('userName', name);
  };

  return (
    <div className="app">
      <Navbar
        onDetailsOpen={() => setShowDetailsModal(true)}
        onReportsOpen={() => setShowReportsModal(true)}
        userName={userName}
      />

      <Routes>
        <Route path="/" element={<HomePage onNameUpdate={handleNameUpdate} />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/summary" element={<AISummary />} />
        <Route path="/summary/:reportId" element={<SummaryPage />} />
        <Route path="/translate" element={<Translation />} />
        <Route path="/translation/:reportId" element={<Translation />} />
        <Route path="/insights" element={<HealthInsights />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Routes>

      <Footer />

      {/* App-level modals — triggered by Navbar on any page */}
      <MyDetailsModal
        isOpen={showDetailsModal}
        onClose={() => setShowDetailsModal(false)}
        onNameUpdate={handleNameUpdate}
      />
      <MyReportsModal
        isOpen={showReportsModal}
        onClose={() => setShowReportsModal(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}
