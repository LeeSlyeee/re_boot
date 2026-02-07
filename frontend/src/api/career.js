import api from './axios';

export const generatePortfolio = async (type) => {
    const response = await api.post('/career/portfolios/generate/', { type });
    return response.data;
};

export const getPortfolios = async () => {
    const response = await api.get('/career/portfolios/');
    return response.data;
};
