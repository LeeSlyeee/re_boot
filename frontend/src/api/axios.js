import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000/api', // Django API
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 180000, // 3 minutes timeout
});

// Request Interceptor to add Auth Token
api.interceptors.request.use((config) => {
    // Skip token for auth endpoints to prevent sending invalid tokens
    if (config.url && (config.url.includes('/login/') || config.url.includes('/register/'))) {
        return config;
    }

    const token = localStorage.getItem('token');
    
    // Ensure headers object exists
    if (!config.headers) {
        config.headers = {};
    }

    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    } else {
        // console.warn("No token found in localStorage");
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

export default api;
