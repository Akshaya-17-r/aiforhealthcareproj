import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { saveUserDetails } from '../services/api';

const MyDetailsModal = ({ isOpen, onClose, onNameUpdate }) => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    firstName: '', lastName: '', age: '', height: '', weight: '',
    gender: 'male', email: '', phone: '',
  });
  const [bmi, setBmi] = useState(null);
  const [bmiCategory, setBmiCategory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const calcBmi = (height, weight) => {
    const h = parseFloat(height) / 100;
    const w = parseFloat(weight);
    if (h > 0 && w > 0) {
      const val = w / (h * h);
      setBmi(val.toFixed(1));
      if (val < 18.5) setBmiCategory('Underweight');
      else if (val < 25) setBmiCategory('Normal weight');
      else if (val < 30) setBmiCategory('Overweight');
      else setBmiCategory('Obese');
    } else {
      setBmi(null);
      setBmiCategory('');
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    const updated = { ...formData, [name]: value };
    setFormData(updated);
    setError('');
    if (name === 'height' || name === 'weight') {
      calcBmi(
        name === 'height' ? value : formData.height,
        name === 'weight' ? value : formData.weight
      );
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await saveUserDetails(formData);
      setSuccess('Details saved successfully!');
      if (onNameUpdate && formData.firstName) {
        onNameUpdate(`${formData.firstName} ${formData.lastName}`.trim());
      }
      setTimeout(() => { onClose(); setSuccess(''); }, 2000);
    } catch (err) {
      setError(err.message || 'Failed to save details');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-content">
        <div className="modal-header">
          <h2 className="modal-title">My Details</h2>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        {!isAuthenticated ? (
          <div style={{ padding: '1.5rem', textAlign: 'center' }}>
            <p style={{ marginBottom: '1rem', color: '#6b7c6b' }}>
              Sign in to save and manage your personal details.
            </p>
            <button
              className="form-submit-btn"
              onClick={() => { onClose(); navigate('/login'); }}
            >
              Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="details-form">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="firstName">First Name</label>
                <input id="firstName" type="text" name="firstName" value={formData.firstName}
                  onChange={handleChange} placeholder="John" required />
              </div>
              <div className="form-group">
                <label htmlFor="lastName">Last Name</label>
                <input id="lastName" type="text" name="lastName" value={formData.lastName}
                  onChange={handleChange} placeholder="Doe" required />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="age">Age</label>
                <input id="age" type="number" name="age" value={formData.age}
                  onChange={handleChange} placeholder="30" min="1" max="150" required />
              </div>
              <div className="form-group">
                <label htmlFor="gender">Gender</label>
                <select id="gender" name="gender" value={formData.gender} onChange={handleChange}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="height">Height (cm)</label>
                <input id="height" type="number" name="height" value={formData.height}
                  onChange={handleChange} placeholder="170" min="50" max="300" step="0.1" />
              </div>
              <div className="form-group">
                <label htmlFor="weight">Weight (kg)</label>
                <input id="weight" type="number" name="weight" value={formData.weight}
                  onChange={handleChange} placeholder="70" min="10" max="500" step="0.1" />
              </div>
            </div>

            {bmi && (
              <div className="bmi-result">
                <div className="bmi-display">
                  <span className="bmi-label">BMI:</span>
                  <span className="bmi-value">{bmi}</span>
                  <span className="bmi-category">{bmiCategory}</span>
                </div>
                <div className="bmi-scale">
                  <div className="bmi-scale-item underweight">Underweight: &lt;18.5</div>
                  <div className="bmi-scale-item normal">Normal: 18.5–25</div>
                  <div className="bmi-scale-item overweight">Overweight: 25–30</div>
                  <div className="bmi-scale-item obese">Obese: &gt;30</div>
                </div>
              </div>
            )}

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input id="email" type="email" name="email" value={formData.email}
                  onChange={handleChange} placeholder="john@example.com" required />
              </div>
              <div className="form-group">
                <label htmlFor="phone">Phone</label>
                <input id="phone" type="tel" name="phone" value={formData.phone}
                  onChange={handleChange} placeholder="+91 99999 00000" />
              </div>
            </div>

            {error && <div className="form-error">{error}</div>}
            {success && <div className="form-success">{success}</div>}

            <button type="submit" className="form-submit-btn" disabled={loading}>
              {loading ? 'Saving...' : 'Save Details'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default MyDetailsModal;
