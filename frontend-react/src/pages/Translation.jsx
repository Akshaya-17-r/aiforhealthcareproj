import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { LANGS, EN_COMP, LANGUAGE_ORDER } from '../data/translationData';
import summaryApi from '../services/summaryApi';
import {
  MOCK_REPORT_KPATEL, MOCK_REPORT_YASH_PATEL, MOCK_REPORT_AMIRTHA,
  MOCK_REPORT_SARAH_KHAN, MOCK_REPORT_RAJESH_KUMAR
} from '../data/mockData';
import '../styles/translation.css';
import Toast from '../components/Toast';
import MyDetailsModal from '../components/MyDetailsModal';
import MyReportsModal from '../components/MyReportsModal';

const MOCK_REPORTS_MAP = {
  'mock_kpatel_001': MOCK_REPORT_KPATEL, 'kpatel': MOCK_REPORT_KPATEL,
  'k-patel': MOCK_REPORT_KPATEL, 'kpatel_blood': MOCK_REPORT_KPATEL,
  'mock_yash_001': MOCK_REPORT_YASH_PATEL, 'yash': MOCK_REPORT_YASH_PATEL,
  'yash-patel': MOCK_REPORT_YASH_PATEL, 'yash_fasting': MOCK_REPORT_YASH_PATEL,
  'mock_amirtha_001': MOCK_REPORT_AMIRTHA, 'amirtha': MOCK_REPORT_AMIRTHA,
  'ms-amirtha': MOCK_REPORT_AMIRTHA, 'amirtha_blood': MOCK_REPORT_AMIRTHA,
  'mock_sarah_001': MOCK_REPORT_SARAH_KHAN, 'sarah': MOCK_REPORT_SARAH_KHAN,
  'sarah-khan': MOCK_REPORT_SARAH_KHAN, 'sarah_lipid': MOCK_REPORT_SARAH_KHAN,
  'mock_rajesh_001': MOCK_REPORT_RAJESH_KUMAR, 'rajesh': MOCK_REPORT_RAJESH_KUMAR,
  'rajesh-kumar': MOCK_REPORT_RAJESH_KUMAR, 'rajesh_thyroid': MOCK_REPORT_RAJESH_KUMAR,
};

const getMockReportByID = (id) =>
  !id ? MOCK_REPORT_KPATEL : MOCK_REPORTS_MAP[id.toLowerCase()] || MOCK_REPORT_KPATEL;

// Language code → full name for the translation API
const LANG_NAMES = { en: 'English', ta: 'Tamil', hi: 'Hindi', kn: 'Kannada' };

export default function Translation() {
  const { reportId } = useParams();
  const [currentLanguage, setCurrentLanguage] = useState('ta');
  const [toastMessage, setToastMessage] = useState('');
  const [isFading, setIsFading] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showReportsModal, setShowReportsModal] = useState(false);
  const [userName, setUserName] = useState('Guest');
  const [reportData, setReportData] = useState(null);
  const [translatedContent, setTranslatedContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [translationLoading, setTranslationLoading] = useState(false);
  const navigate = useNavigate();
  const contentRef = useRef(null);

  // Fetch base English summary on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        if (reportId) {
          const isMockId = MOCK_REPORTS_MAP[reportId.toLowerCase()];
          if (isMockId) {
            setReportData(getMockReportByID(reportId));
          } else {
            try {
              const summary = await summaryApi.getReportSummary(reportId, 'en');
              setReportData(summary.success ? summary : getMockReportByID(reportId));
            } catch {
              setReportData(getMockReportByID(reportId));
            }
          }
        } else {
          setReportData(getMockReportByID(reportId));
        }
        const stored = localStorage.getItem('userName');
        if (stored) setUserName(stored);
      } catch {
        setReportData(getMockReportByID(reportId));
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [reportId]);

  // Fetch translated content from backend whenever language changes (non-English, real report)
  useEffect(() => {
    const fetchTranslation = async () => {
      if (!reportId || currentLanguage === 'en') {
        setTranslatedContent(null);
        return;
      }
      const isMockId = MOCK_REPORTS_MAP[reportId.toLowerCase()];
      if (isMockId) {
        // For mock reports, use static LANGS data — no backend call
        setTranslatedContent(null);
        return;
      }
      setTranslationLoading(true);
      try {
        const result = await summaryApi.getReportTranslation(reportId, LANG_NAMES[currentLanguage]);
        setTranslatedContent(result.success ? result : null);
      } catch {
        setTranslatedContent(null);
      } finally {
        setTranslationLoading(false);
      }
    };
    fetchTranslation();
  }, [currentLanguage, reportId]);

  const switchLanguage = (langCode) => {
    if (langCode === currentLanguage) return;
    setIsFading(true);
    setTimeout(() => {
      setCurrentLanguage(langCode);
      setIsFading(false);
    }, 160);
  };

  const showToast = (message) => {
    setToastMessage(message);
    setTimeout(() => setToastMessage(''), 2500);
  };

  // Compute the summary text to display in the current language
  const getSummaryText = () => {
    if (currentLanguage === 'en') {
      return reportData?.medical_summary || LANGS['en'].summary;
    }
    // For non-English: prefer real API translation, then mock translation, then static LANGS
    if (translatedContent?.translated_text) return translatedContent.translated_text;
    const mockReport = reportId ? getMockReportByID(reportId) : null;
    if (mockReport?.translations?.[currentLanguage]?.medical_summary) {
      return mockReport.translations[currentLanguage].medical_summary;
    }
    return LANGS[currentLanguage].summary;
  };

  const summaryText = getSummaryText();

  const copyTranslation = async () => {
    const lang = LANGS[currentLanguage];
    const text = `${lang.cardTitle}\n\n${summaryText}\n\n${lang.plain.join('\n')}\n\n${lang.rec}`;
    try {
      await navigator.clipboard.writeText(text);
      showToast('Copied to clipboard');
    } catch {
      showToast('Failed to copy');
    }
  };

  const downloadTranslation = () => {
    const lang = LANGS[currentLanguage];
    const text = `${lang.cardTitle}\n\n${summaryText}\n\n${lang.plain.join('\n')}\n\n${lang.rec}`;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `translation-${currentLanguage}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Downloaded successfully');
  };

  const shareWhatsApp = () => {
    const message = `${LANGS[currentLanguage].cardTitle}\n\n${summaryText}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, '_blank');
    showToast('Opening WhatsApp');
  };

  const goBack = () => navigate(reportId ? `/summary/${reportId}` : '/summary');

  if (loading) {
    return (
      <div className="translation-page">
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <p>Loading translation...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="translation-page">
      {/* Navigation Bar */}
      <nav className="translation-navbar">
        <div className="nav-container">
          <div className="nav-left">
            <button className="back-btn" onClick={goBack}>← Back</button>
          </div>
          <div className="nav-right">
            <span className="user-name">{userName}</span>
            <button className="user-icon-btn" onClick={() => setShowDetailsModal(true)}>👤</button>
          </div>
        </div>
      </nav>

      <div className="translation-wrapper">
        {/* Breadcrumb */}
        <div className="breadcrumb">
          <span>Home</span>
          <span className="separator">›</span>
          <span>Translation</span>
        </div>

        {/* Meta Bar */}
        <div className="meta-bar">
          <div className="meta-left">
            <h1>{reportData?.metadata?.report_name || 'Medical Report Summary'}</h1>
            <p>{reportData?.metadata?.patient_name || 'Patient Report'} • {reportData?.metadata?.report_type || 'Analysis'}</p>
          </div>
          <div className="meta-actions">
            <button className="action-btn copy-btn" onClick={copyTranslation} title="Copy to clipboard">
              Copy
            </button>
            <button className="action-btn download-btn" onClick={downloadTranslation} title="Download">
              Download
            </button>
            <button className="action-btn whatsapp-btn" onClick={shareWhatsApp} title="Share on WhatsApp">
              Share
            </button>
          </div>
        </div>

        {/* Language Tabs */}
        <div className="language-tabs">
          {LANGUAGE_ORDER.map(code => {
            const lang = LANGS[code];
            return (
              <button
                key={code}
                className={`lang-tab ${currentLanguage === code ? 'active' : ''}`}
                onClick={() => switchLanguage(code)}
                title={lang.name}
              >
                <span className="tab-flag">{lang.flag}</span>
                <span className="tab-name">{lang.native}</span>
              </button>
            );
          })}
        </div>

        <div className="main-layout">
          {/* Main Content */}
          <div className="main-column">
            <div className={`fade-content ${isFading ? 'fading' : ''}`} ref={contentRef}>
              <div className="translation-card">
                <div className="card-header">
                  <div className="header-left">
                    <h2 className="card-title">{LANGS[currentLanguage].cardTitle}</h2>
                    <p className="powered-by">{LANGS[currentLanguage].powered}</p>
                  </div>
                  <span className="ai-badge">{LANGS[currentLanguage].aiBadge}</span>
                </div>

                {/* Summary Section */}
                <div className="section">
                  <h3 className="section-title">Summary</h3>
                  {translationLoading ? (
                    <p className="section-text" style={{ color: '#9aaa9a' }}>Translating...</p>
                  ) : (
                    <p className="section-text">{summaryText}</p>
                  )}
                </div>

                {/* Plain Language Section */}
                <div className="section">
                  <h3 className="section-title">What Does This Mean?</h3>
                  <ul className="plain-list">
                    {LANGS[currentLanguage].plain.map((item, idx) => (
                      <li key={idx} className="plain-item">{item}</li>
                    ))}
                  </ul>
                </div>

                {/* Doctor Recommendation */}
                <div className="section doctor-section">
                  <h3 className="section-title">Doctor's Recommendation</h3>
                  <p className="section-text">{LANGS[currentLanguage].rec}</p>
                </div>
              </div>

              {/* Comparison Table */}
              <div className="comparison-card">
                <h3 className="card-title">Comparison Table</h3>
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th>English (Original)</th>
                      <th>{LANGS[currentLanguage].name} (Translation)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {EN_COMP.map((eng, idx) => (
                      <tr key={idx}>
                        <td className="eng-term">{eng}</td>
                        <td className="trans-term">{LANGS[currentLanguage].comp[idx]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <aside className="sidebar">
            <div className="sidebar-card language-info-card">
              <h4 className="sidebar-card-title">Language Info</h4>
              <div className="info-item">
                <span className="info-label">Language</span>
                <span className="info-value">{LANGS[currentLanguage].name}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Script</span>
                <span className="info-value">{LANGS[currentLanguage].script}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Speakers</span>
                <span className="info-value">{LANGS[currentLanguage].speakers}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Region</span>
                <span className="info-value">{LANGS[currentLanguage].region}</span>
              </div>
            </div>

            <div className="sidebar-card quality-card">
              <h4 className="sidebar-card-title">Translation Quality</h4>
              {LANGS[currentLanguage].quality.map((item, idx) => (
                <div key={idx} className="quality-item">
                  <div className="quality-header">
                    <span className="quality-label">{item.l}</span>
                    <span className="quality-percent">{item.p}%</span>
                  </div>
                  <div className="quality-bar">
                    <div className="quality-fill" style={{ width: `${item.p}%` }}></div>
                  </div>
                </div>
              ))}
            </div>

            <div className="sidebar-card language-chips-card">
              <h4 className="sidebar-card-title">All Languages</h4>
              <div className="chips-grid">
                {LANGUAGE_ORDER.map(code => (
                  <div key={code} className={`chip ${currentLanguage === code ? 'active' : ''}`}>
                    <span className="chip-flag">{LANGS[code].flag}</span>
                    <span className="chip-name">{LANGS[code].name}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="sidebar-card export-card">
              <h4 className="sidebar-card-title">Export &amp; Share</h4>
              <button className="export-btn" onClick={copyTranslation}>Copy Translation</button>
              <button className="export-btn" onClick={downloadTranslation}>Download as TXT</button>
              <button className="export-btn" onClick={shareWhatsApp}>Share on WhatsApp</button>
            </div>

            <div className="sidebar-card actions-card">
              <h4 className="sidebar-card-title">Quick Actions</h4>
              <button className="action-link" onClick={goBack}>Back to Summary</button>
              <button className="action-link" onClick={() => navigate('/upload')}>Analyze Another</button>
              <button className="action-link" onClick={() => setShowReportsModal(true)}>My Reports</button>
              <button className="action-link" onClick={() => setShowDetailsModal(true)}>My Details</button>
            </div>
          </aside>
        </div>
      </div>

      <MyDetailsModal isOpen={showDetailsModal} onClose={() => setShowDetailsModal(false)} />
      <MyReportsModal isOpen={showReportsModal} onClose={() => setShowReportsModal(false)} />
      {toastMessage && <Toast message={toastMessage} />}
    </div>
  );
}
