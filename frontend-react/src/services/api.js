/**
 * API Service - Helper functions for API calls
 * Base URL is set from environment variables or defaults to localhost
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const getAuthToken = () => localStorage.getItem('authToken');

const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const token = getAuthToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({ message: `HTTP Error: ${response.status}` }));
  if (!response.ok) {
    throw new Error(data.detail || data.message || `HTTP Error: ${response.status}`);
  }
  return data;
};

export const saveUserDetails = async (userDetails) =>
  apiRequest('/users/details', { method: 'POST', body: JSON.stringify(userDetails) });

export const getUserDetails = async () =>
  apiRequest('/users/details', { method: 'GET' });

/**
 * Fetch reports for the current authenticated user.
 * Backend endpoint: GET /users/{user_id}/reports  (not /reports)
 */
export const fetchUserReports = async () => {
  const token = getAuthToken();
  if (!token) throw new Error('Not authenticated');

  let userId;
  try {
    userId = JSON.parse(atob(token.split('.')[1])).sub;
  } catch {
    throw new Error('Invalid auth token');
  }

  return apiRequest(`/users/${userId}/reports`, { method: 'GET' });
};

export const uploadReport = async (file, metadata = {}) => {
  const formData = new FormData();
  formData.append('file', file);
  Object.entries(metadata).forEach(([k, v]) => formData.append(k, v));

  const headers = {};
  const token = getAuthToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}/upload-report`, {
    method: 'POST',
    headers,
    body: formData,
  });

  const data = await response.json().catch(() => ({ message: `HTTP Error: ${response.status}` }));
  if (!response.ok) {
    throw new Error(data.detail || data.message || `Upload failed: ${response.status}`);
  }
  return data;
};

export const getReportAnalysis = async (reportId, language = 'en') =>
  apiRequest(`/reports/${reportId}/summary?language=${language}`, { method: 'GET' });

export const deleteReport = async (reportId) =>
  apiRequest(`/reports/${reportId}`, { method: 'DELETE' });

export const getReportById = async (reportId) =>
  apiRequest(`/reports/${reportId}`, { method: 'GET' });

export const updateReport = async (reportId, updates) =>
  apiRequest(`/reports/${reportId}`, { method: 'PUT', body: JSON.stringify(updates) });

/**
 * Login — backend expects Form data (email, password), not JSON
 */
export const loginUser = async (email, password) => {
  const formData = new FormData();
  formData.append('email', email);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json().catch(() => ({ message: `HTTP Error: ${response.status}` }));
  if (!response.ok) {
    throw new Error(data.detail || data.message || `HTTP Error: ${response.status}`);
  }
  if (data.token) localStorage.setItem('authToken', data.token);
  return data;
};

export const logoutUser = () => {
  localStorage.removeItem('authToken');
  localStorage.removeItem('userName');
};

export const registerUser = async (userData) => {
  const response = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
  if (response.token) localStorage.setItem('authToken', response.token);
  return response;
};

export const verifyToken = async () => {
  try {
    return await apiRequest('/auth/verify', { method: 'POST' });
  } catch (error) {
    logoutUser();
    throw error;
  }
};

export default {
  saveUserDetails, getUserDetails, fetchUserReports, uploadReport,
  getReportAnalysis, deleteReport, getReportById, updateReport,
  loginUser, logoutUser, registerUser, verifyToken,
};
