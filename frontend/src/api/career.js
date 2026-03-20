import api from './axios';

export const generatePortfolio = async (type, category = null) => {
    const payload = { type };
    if (category) payload.category = category;
    const response = await api.post('/career/portfolios/generate/', payload);
    return response.data;
};

export const getPortfolios = async () => {
    const response = await api.get('/career/portfolios/');
    return response.data;
};
