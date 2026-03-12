/**
 * Summary API Service - Handles report summaries and translations
 * Always returns data at the top level so callers do not need to unwrap .data
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const getAuthToken = () => localStorage.getItem('authToken');

const _headers = () => {
  const h = { 'Content-Type': 'application/json' };
  const token = getAuthToken();
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
};

/**
 * Get report summary data.
 * Backend returns { success, data: { report_id, metadata, medical_summary, ... } }
 * We flatten data so callers access response.medical_summary directly.
 */
export const getReportSummary = async (reportId, language = 'en') => {
  try {
    const response = await fetch(`${API_BASE_URL}/reports/${reportId}/summary`, {
      method: 'GET',
      headers: _headers(),
    });

    if (!response.ok) {
      console.warn(`Summary endpoint returned ${response.status}, using mock data`);
      return getDefaultMockSummary(reportId);
    }

    const json = await response.json();
    // Backend wraps result in { success, data: {...} } — flatten it
    const data = json.data || json;
    return {
      success: true,
      ...data,
      language,
    };
  } catch (error) {
    console.error('Error fetching report summary:', error);
    return getDefaultMockSummary(reportId);
  }
};

/**
 * Get translated content for a report.
 * Backend returns { success, data: { translated_text, simplified_text, ... } }
 */
export const getReportTranslation = async (reportId, language = 'English') => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/reports/${reportId}/translation?language=${encodeURIComponent(language)}`,
      { method: 'GET', headers: _headers() }
    );

    if (!response.ok) {
      console.warn(`Translation endpoint returned ${response.status}, using mock data`);
      return getDefaultMockTranslation(reportId, language);
    }

    const json = await response.json();
    const data = json.data || json;
    return {
      success: true,
      ...data,
      language,
    };
  } catch (error) {
    console.error('Error fetching translation:', error);
    return getDefaultMockTranslation(reportId, language);
  }
};

export const copySummaryToClipboard = async (reportId) => {
  try {
    const summary = await getReportSummary(reportId);
    const text = `${summary.metadata?.report_name || 'Medical Report'}\n\n${summary.medical_summary || ''}`;
    await navigator.clipboard.writeText(text);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

export const exportReportText = async (reportId) => {
  try {
    const summary = await getReportSummary(reportId);
    const content = `ReportEase — AI Medical Summary\n\nReport: ${summary.metadata?.report_name}\nDate: ${summary.metadata?.report_date}\n\n${summary.medical_summary || ''}\n\nCreated: ${summary.created_at}`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    return { success: true, url, filename: `ReportEase_${reportId}.txt` };
  } catch (error) {
    return { success: false, error: error.message };
  }
};

export const getAvailableLanguages = async () => ({
  success: true,
  languages: { en: 'English', ta: 'Tamil', hi: 'Hindi', kn: 'Kannada' },
  available: { en: true, ta: true, hi: true, kn: true },
});

// ============================================================================
// MOCK FALLBACKS (used when backend is unavailable)
// ============================================================================

const getDefaultMockSummary = (reportId) => ({
  success: false,
  error: 'Backend unavailable — showing sample data',
  report_id: reportId,
  metadata: {
    report_name: 'Blood Test Report — March 2025',
    report_date: '02 March 2025',
    patient_name: 'Priya Sharma',
    report_type: 'Blood Test',
  },
  medical_summary:
    'Your blood test shows slightly low hemoglobin (11.2 g/dL) indicating mild anemia, and borderline high cholesterol (214 mg/dL). Blood glucose levels are normal at 98 mg/dL.',
  original_text: '',
  language: 'English',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

const getDefaultMockTranslation = (reportId, language) => {
  const translations = {
    English: 'Your blood test shows slightly low hemoglobin indicating mild anemia...',
    Tamil: 'உங்கள் இரத்த பரிசோதனை முடிவுகள் லேசான இரத்த சோகை காட்டுகின்றன...',
    Hindi: 'आपके रक्त परीक्षण परिणाम हल्के एनीमिया दिखाते हैं...',
    Kannada: 'ನಿಮ್ಮ ರಕ್ತ ಪರೀಕ್ಷೆಯ ಫಲಿತಾಂಶಗಳು ಸೌಮ್ಯ ರಕ್ತ ಹೀನತೆ ತೋರಿಸುತ್ತವೆ...',
  };

  return {
    success: false,
    error: 'Backend unavailable — showing sample translation',
    report_id: reportId,
    language,
    translated_text: translations[language] || translations.English,
    simplified_text: 'Your blood test results...',
    metadata: {
      report_name: 'Blood Test Report',
      report_date: new Date().toLocaleDateString(),
      patient_name: 'Patient',
      report_type: 'Blood Test',
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
};

export default {
  getReportSummary,
  getReportTranslation,
  copySummaryToClipboard,
  exportReportText,
  getAvailableLanguages,
};
