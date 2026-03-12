import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import summaryApi from '../services/summaryApi';
import '../styles/insights.css';

// Badges considered abnormal/concerning
const ABNORMAL_BADGES = new Set([
  'critical', 'elevated', 'high', 'low', 'impaired', 'borderline',
  'diabetic', 'very high', 'abnormal', 'deficient', 'poor',
]);

const badgeToType = (badge) =>
  ABNORMAL_BADGES.has((badge || '').toLowerCase()) ? 'warning' : 'success';

const findingToInsight = (finding, idx) => ({
  id: idx,
  type: badgeToType(finding.badge),
  title: `${finding.label}: ${finding.value} ${finding.unit}`.trim(),
  description: `Result: ${finding.badge || 'See report'}`,
  recommendation: finding.badge && badgeToType(finding.badge) === 'warning'
    ? 'Consult your doctor about this result.'
    : 'Value is within the acceptable range.',
});

const sampleInsights = [
  {
    id: 1, type: 'warning', title: 'Possible Iron Deficiency',
    description: 'Low haemoglobin and MCV levels suggest iron deficiency anaemia.',
    recommendation: 'Consider iron supplementation and dietary changes.',
  },
  {
    id: 2, type: 'warning', title: 'Slightly Elevated Cholesterol',
    description: 'Total and LDL cholesterol levels are above optimal range.',
    recommendation: 'Increase physical activity and reduce saturated fat intake.',
  },
  {
    id: 3, type: 'success', title: 'Normal Blood Sugar',
    description: 'Fasting glucose level is within healthy range.',
    recommendation: 'Maintain current diet and exercise habits.',
  },
  {
    id: 4, type: 'success', title: 'Healthy Immune System',
    description: 'White blood cell count indicates normal immune function.',
    recommendation: 'Continue maintaining good hygiene and sleep patterns.',
  },
];

export default function HealthInsights() {
  const navigate = useNavigate();
  const [insights, setInsights] = useState([]);
  const [reportId, setReportId] = useState(null);
  const [patientName, setPatientName] = useState('');
  const [loading, setLoading] = useState(true);
  const [usingRealData, setUsingRealData] = useState(false);

  useEffect(() => {
    const loadInsights = async () => {
      setLoading(true);
      const lastId = localStorage.getItem('lastReportId');

      if (!lastId) {
        setInsights(sampleInsights);
        setLoading(false);
        return;
      }

      setReportId(lastId);

      try {
        const report = await summaryApi.getReportSummary(lastId, 'en');
        if (report.success && report.findings && report.findings.length > 0) {
          setInsights(report.findings.map(findingToInsight));
          setPatientName(report.metadata?.patient_name || '');
          setUsingRealData(true);
        } else if (report.success && report.medical_summary) {
          // We have a real report but no structured findings — build a single summary card
          setInsights([{
            id: 0,
            type: 'success',
            title: 'AI Summary Available',
            description: report.medical_summary.slice(0, 180) + (report.medical_summary.length > 180 ? '...' : ''),
            recommendation: 'View the full summary for details.',
          }]);
          setPatientName(report.metadata?.patient_name || '');
          setUsingRealData(true);
        } else {
          setInsights(sampleInsights);
        }
      } catch {
        setInsights(sampleInsights);
      } finally {
        setLoading(false);
      }
    };

    loadInsights();
  }, []);

  if (loading) {
    return <div className="insights-page"><p style={{ padding: '2rem', textAlign: 'center' }}>Loading...</p></div>;
  }

  return (
    <div className="insights-page">
      <div className="insights-container">
        <div className="breadcrumb">
          <Link to="/">Home</Link> / <Link to="/upload">Upload</Link> / <span>Health Insights</span>
        </div>

        <h1>Your Health Insights</h1>
        <p className="subtitle">
          {usingRealData && patientName
            ? `AI-extracted insights for ${patientName} from your latest report.`
            : 'AI-extracted insights from your medical report to help you understand your health better.'}
        </p>

        {!usingRealData && (
          <div style={{ background: '#f0f4ee', border: '1px solid #c8d8c8', borderRadius: '8px', padding: '.75rem 1rem', marginBottom: '1.25rem', fontSize: '.85rem', color: '#4a7c59' }}>
            Showing sample data. Upload a medical report to see your personalised insights.
          </div>
        )}

        <div className="insights-grid">
          {insights.map((insight) => (
            <div key={insight.id} className={`insight-card ${insight.type}`}>
              <div className="insight-header">
                <div className={`insight-badge ${insight.type}`}>
                  {insight.type === 'warning' ? '!' : 'OK'}
                </div>
                <h3>{insight.title}</h3>
              </div>
              <p className="insight-description">{insight.description}</p>
              <div className="insight-footer">
                <strong>Recommendation:</strong> {insight.recommendation}
              </div>
            </div>
          ))}
        </div>

        <div className="insights-actions">
          {reportId && (
            <button className="btn-secondary" onClick={() => navigate(`/summary/${reportId}`)}>
              View Full Summary
            </button>
          )}
          {reportId && (
            <button className="btn-secondary" onClick={() => navigate(`/translation/${reportId}`)}>
              View Translation
            </button>
          )}
          <Link to="/upload" className="btn-primary">Upload Another Report</Link>
        </div>
      </div>
    </div>
  );
}
