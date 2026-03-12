import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import summaryApi from '../services/summaryApi';
import {
  MOCK_REPORT_KPATEL,
  MOCK_REPORT_YASH_PATEL,
  MOCK_REPORT_AMIRTHA,
  MOCK_REPORT_SARAH_KHAN,
  MOCK_REPORT_RAJESH_KUMAR
} from '../data/mockData';
import SummaryBreadcrumb from '../components/SummaryBreadcrumb';
import SummaryMetaBar from '../components/SummaryMetaBar';
import MedicalSummary from '../components/MedicalSummary';
import PlainLanguage from '../components/PlainLanguage';
import Findings from '../components/Findings';
import DoctorNote from '../components/DoctorNote';
import HealthScore from '../components/HealthScore';
import KeyValues from '../components/KeyValues';
import TranslationCard from '../components/TranslationCard';
import TranslatePanel from '../components/TranslatePanel';
import SummaryActions from '../components/SummaryActions';
import '../styles/summary-page.css';

// Map of reportId to mock report data
const MOCK_REPORTS_MAP = {
  'mock_kpatel_001': MOCK_REPORT_KPATEL,
  'kpatel': MOCK_REPORT_KPATEL,
  'k-patel': MOCK_REPORT_KPATEL,
  'kpatel_blood': MOCK_REPORT_KPATEL,

  'mock_yash_001': MOCK_REPORT_YASH_PATEL,
  'yash': MOCK_REPORT_YASH_PATEL,
  'yash-patel': MOCK_REPORT_YASH_PATEL,
  'yash_fasting': MOCK_REPORT_YASH_PATEL,

  'mock_amirtha_001': MOCK_REPORT_AMIRTHA,
  'amirtha': MOCK_REPORT_AMIRTHA,
  'ms-amirtha': MOCK_REPORT_AMIRTHA,
  'amirtha_blood': MOCK_REPORT_AMIRTHA,

  'mock_sarah_001': MOCK_REPORT_SARAH_KHAN,
  'sarah': MOCK_REPORT_SARAH_KHAN,
  'sarah-khan': MOCK_REPORT_SARAH_KHAN,
  'sarah_lipid': MOCK_REPORT_SARAH_KHAN,

  'mock_rajesh_001': MOCK_REPORT_RAJESH_KUMAR,
  'rajesh': MOCK_REPORT_RAJESH_KUMAR,
  'rajesh-kumar': MOCK_REPORT_RAJESH_KUMAR,
  'rajesh_thyroid': MOCK_REPORT_RAJESH_KUMAR,
};

// Function to get mock report by ID
const getMockReportByID = (reportId) => {
  if (!reportId) return MOCK_REPORT_KPATEL;

  const lowerCaseId = reportId.toLowerCase();
  return MOCK_REPORTS_MAP[lowerCaseId] || MOCK_REPORT_KPATEL;
};

const SummaryPage = () => {
  const { reportId } = useParams();
  const [reportData, setReportData] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [toastMessage, setToastMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const ringFillRef = useRef(null);

  // Fetch report data on mount
  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        let data = null;

        const isMockId = !reportId || reportId === 'mock' || MOCK_REPORTS_MAP[reportId?.toLowerCase()];

        if (isMockId) {
          // Known mock ID — use local mock data directly
          data = getMockReportByID(reportId);
        } else {
          // Real report ID — fetch from backend
          try {
            // summaryApi now returns data at the top level (no .data nesting)
            const response = await summaryApi.getReportSummary(reportId, 'en');
            if (response.success && response.medical_summary) {
              data = response;
            } else {
              // Backend returned an error or empty result — fall back to mock
              console.warn('API returned empty/failed summary, using mock for:', reportId);
              data = getMockReportByID(reportId);
            }
          } catch (apiError) {
            console.warn('API unavailable, using mock data for:', reportId);
            data = getMockReportByID(reportId);
          }
        }

        setReportData(data || getMockReportByID(reportId));
      } catch (error) {
        console.error('Error fetching report:', error);
        setReportData(getMockReportByID(reportId));
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [reportId]);

  const handleLanguageChange = (language) => {
    setSelectedLanguage(language);
  };

  // Ensure we always have data (can be used in handlers before render)
  const data = reportData || getMockReportByID(reportId);

  const handleCopyToClipboard = async () => {
    try {
      const content = `
        Report: ${data.metadata.report_name}
        Patient: ${data.metadata.patient_name}
        Date: ${data.metadata.report_date}
        Summary: ${data.medical_summary}
        Health Score: ${data.health_score.score}/${data.health_score.total}
      `;
      navigator.clipboard.writeText(content);
      setToastMessage('Copied to clipboard!');
      setTimeout(() => setToastMessage(''), 3000);
    } catch (error) {
      setToastMessage('Failed to copy');
    }
  };

  const handleDownload = async () => {
    try {
      const content = `ReportEase — AI Medical Summary
Report: ${data.metadata.report_name}
Patient: ${data.metadata.patient_name} | Date: ${data.metadata.report_date}

=== MEDICAL SUMMARY ===
${data.medical_summary}

=== KEY VALUES ===
${data.key_values?.map(v => `${v.label}: ${v.value}`).join('\n')}

=== FINDINGS ===
${data.findings?.map(f => `${f.label}: ${f.value} ${f.unit} (${f.badge})`).join('\n')}

=== DOCTOR'S NOTES ===
${data.doctor_notes}

Generated by ReportEase · reportease.in`;

      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: 'text/plain' }));
      a.download = `ReportEase_${data.metadata.report_name.replace(/\s+/g, '_')}_${Date.now()}.txt`;
      a.click();
      setToastMessage('Report downloaded successfully!');
      setTimeout(() => setToastMessage(''), 3000);
    } catch (error) {
      setToastMessage('Failed to download');
    }
  };

  if (loading) {
    return (
      <div className="summary-wrapper">
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <p>Loading report...</p>
        </div>
      </div>
    );
  }

  // Get translation data if needed
  const translationData = selectedLanguage !== 'en' && data.translations?.[selectedLanguage];

  return (
    <div className="summary-wrapper">
      <div className="page">
        <div className="page-inner">
          {/* Breadcrumb Navigation */}
          <SummaryBreadcrumb reportName={data.metadata.report_name} />

          {/* Meta Information Bar */}
          <SummaryMetaBar
            patientName={data.metadata.patient_name}
            reportDate={data.metadata.report_date}
            reportType={data.metadata.report_type}
            onCopy={handleCopyToClipboard}
            onDownload={handleDownload}
          />

          {/* Main Content Grid */}
          <div className="grid">
            <div className="col-main">
              {/* Medical Summary Card */}
              <MedicalSummary summary={data.medical_summary} />

              {/* Plain Language Explanation */}
              {data.plain_language && (
                <PlainLanguage items={data.plain_language} />
              )}

              {/* Important Findings */}
              {data.findings && (
                <Findings findings={data.findings} />
              )}

              {/* Doctor's Note */}
              {data.doctor_notes && (
                <DoctorNote note={data.doctor_notes} />
              )}

              {/* Translations */}
              {translationData && selectedLanguage !== 'en' && (
                <TranslationCard
                  translation={translationData}
                  language={selectedLanguage}
                />
              )}
            </div>

            <div className="col-side">
              {/* Health Score */}
              {data.health_score && (
                <HealthScore
                  score={data.health_score}
                  ringFillRef={ringFillRef}
                />
              )}

              {/* Key Values */}
              {data.key_values && (
                <KeyValues values={data.key_values} />
              )}

              {/* Language Translation Panel */}
              <TranslatePanel
                selectedLanguage={selectedLanguage}
                onLanguageChange={handleLanguageChange}
              />

              {/* Action Buttons */}
              <SummaryActions
                onCopy={handleCopyToClipboard}
                onDownload={handleDownload}
                reportId={reportId}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Toast Message */}
      {toastMessage && (
        <div className="toast show">
          <svg viewBox="0 0 24 24" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};

export default SummaryPage;
