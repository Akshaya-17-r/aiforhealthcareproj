import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchUserReports } from '../services/api';

const MyReportsModal = ({ isOpen, onClose }) => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && isAuthenticated) loadReports();
  }, [isOpen, isAuthenticated]);

  const loadReports = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchUserReports();
      // Backend returns { success, reports: [...] }
      const list = data.reports || data;
      setReports(Array.isArray(list) ? list : []);
    } catch (err) {
      setError(err.message || 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const handleViewReport = (report) => {
    const id = report._id || report.id || report.report_id;
    if (id) {
      onClose();
      navigate(`/summary/${id}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-content">
        <div className="modal-header">
          <h2 className="modal-title">My Reports</h2>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="reports-list">
          {!isAuthenticated ? (
            <div className="empty-state" style={{ textAlign: 'center', padding: '1.5rem' }}>
              <p style={{ marginBottom: '1rem', color: '#6b7c6b' }}>
                Sign in to view your uploaded reports.
              </p>
              <button
                className="retry-btn"
                onClick={() => { onClose(); navigate('/login'); }}
              >
                Sign In
              </button>
            </div>
          ) : loading ? (
            <div className="loading-state"><p>Loading reports...</p></div>
          ) : error ? (
            <div className="error-state">
              <p>Error: {error}</p>
              <button onClick={loadReports} className="retry-btn">Retry</button>
            </div>
          ) : reports.length === 0 ? (
            <div className="empty-state">
              <p>No reports yet</p>
              <p className="empty-subtitle">Upload your first medical report to get started</p>
            </div>
          ) : (
            reports.map((report) => {
              const id = report._id || report.id || report.report_id;
              const name = report.metadata?.report_name || report.file_name || 'Unnamed Report';
              const date = report.created_at || report.uploadedAt;
              const type = report.metadata?.report_type || report.testType;
              return (
                <div key={id} className="report-item">
                  <div className="report-info">
                    <h3 className="report-name">{name}</h3>
                    <p className="report-date">{formatDate(date)}</p>
                    {type && <p className="report-type">Type: {type}</p>}
                  </div>
                  <div className="report-actions">
                    <span className="status-badge completed">Analysed</span>
                    <button className="view-btn" onClick={() => handleViewReport(report)}>
                      View
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default MyReportsModal;
