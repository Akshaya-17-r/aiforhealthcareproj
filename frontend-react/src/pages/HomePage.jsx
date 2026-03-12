import React, { useEffect, useState } from 'react';
import Footer from '../components/Footer';
import '../styles/home.css';

export default function HomePage({ onNameUpdate }) {
  const [userName, setUserName] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('userName');
    if (stored) setUserName(stored);
  }, []);

  const handleNameUpdate = (name) => {
    setUserName(name);
    if (onNameUpdate) onNameUpdate(name);
    localStorage.setItem('userName', name);
  };

  return (
    <div className="homepage">

      {/* HERO */}
      <section className="hero" id="upload">
        <h1>
          Your Diagnosis, <em>Decoded.</em>
          <br />
          Your Health, Understood.
        </h1>
        <p>Clinical reports rewritten in plain language — so patients leave informed, not confused.</p>
        <a className="hero-btn" href="/upload">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload Your Report
        </a>
      </section>

      {/* FEATURES */}
      <section className="features" id="features">
        <div className="section-tag">What We Do</div>
        <h2 className="section-title">Three Things. Done Right.</h2>
        <div className="cards">
          <div className="card">
            <div className="card-icon">
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="11" y1="8" x2="11" y2="14" />
                <line x1="8" y1="11" x2="14" y2="11" />
              </svg>
            </div>
            <h3>AI Summarization</h3>
            <p>Extracts what matters — diagnoses, values, findings — without the noise.</p>
          </div>
          <div className="card">
            <div className="card-icon">
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <h3>Plain Language</h3>
            <p>No medical degree needed. We rewrite your report so anyone can understand it.</p>
          </div>
          <div className="card">
            <div className="card-icon">
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              </svg>
            </div>
            <h3>Regional Translation</h3>
            <p>Read your results in Tamil, Hindi, or Kannada — your language, your health.</p>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="how" id="how">
        <div className="section-tag">The Process</div>
        <h2 className="section-title">Four Steps to Clarity</h2>
        <div className="steps">
          <div className="step">
            <div className="step-circle">
              <span className="step-num">1</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="#BDCBB7" strokeWidth="2" strokeLinecap="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <h4>Upload</h4>
            <p>PDF or image, any format</p>
          </div>
          <div className="step-line"></div>
          <div className="step">
            <div className="step-circle">
              <span className="step-num">2</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="#BDCBB7" strokeWidth="2" strokeLinecap="round">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <path d="M8 21h8M12 17v4" />
              </svg>
            </div>
            <h4>AI Reads It</h4>
            <p>Extracts key findings</p>
          </div>
          <div className="step-line"></div>
          <div className="step">
            <div className="step-circle">
              <span className="step-num">3</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="#BDCBB7" strokeWidth="2" strokeLinecap="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <h4>Simplified</h4>
            <p>Clear, plain explanation</p>
          </div>
          <div className="step-line"></div>
          <div className="step">
            <div className="step-circle">
              <span className="step-num">4</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="#BDCBB7" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
              </svg>
            </div>
            <h4>Translated</h4>
            <p>In your language</p>
          </div>
        </div>
      </section>

      {/* LANGUAGES */}
      <section className="languages" id="about">
        <div className="section-tag">Languages</div>
        <h2 className="section-title">Speak the Same Language as Your Patient</h2>
        <div className="lang-chips">
          <div className="chip"><div className="flag">🇮🇳</div><div><strong>Tamil</strong><span>தமிழ்</span></div></div>
          <div className="chip"><div className="flag">🇮🇳</div><div><strong>Hindi</strong><span>हिन्दी</span></div></div>
          <div className="chip"><div className="flag">🇮🇳</div><div><strong>Kannada</strong><span>ಕನ್ನಡ</span></div></div>
          <div className="chip"><div className="flag">🌐</div><div><strong>English</strong><span>Default</span></div></div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta">
        <h2>Stop Guessing.<br />Start <em>Knowing.</em></h2>
        <p>Upload your report. Get answers your doctor forgot to explain.</p>
        <a className="cta-btn" href="/upload">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Analyze Your Report Now
        </a>
      </section>

      <Footer />
    </div>
  );
}
