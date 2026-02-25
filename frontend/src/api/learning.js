/**
 * AI 튜터 챗봇 + 커리큘럼 + LectureNote API 모듈
 */
import api from './axios';

// ═══ AI 튜터 챗봇 ═══
export const getChatSessions = async (lectureId) => {
    const params = lectureId ? { lecture: lectureId } : {};
    const res = await api.get('/learning/chat/sessions/', { params });
    return res.data;
};

export const createChatSession = async (lectureId, title = '') => {
    const res = await api.post('/learning/chat/sessions/', { lecture: lectureId, title });
    return res.data;
};

export const getChatSession = async (sessionId) => {
    const res = await api.get(`/learning/chat/sessions/${sessionId}/`);
    return res.data;
};

export const deleteChatSession = async (sessionId) => {
    await api.delete(`/learning/chat/sessions/${sessionId}/`);
};

export const askAITutor = async (sessionId, message) => {
    const res = await api.post(`/learning/chat/sessions/${sessionId}/ask/`, { message });
    return res.data;
};

// ═══ 커리큘럼 리라우팅 ═══
export const getCurriculums = async () => {
    const res = await api.get('/learning/curriculum/');
    return res.data;
};

export const getCurriculum = async (id) => {
    const res = await api.get(`/learning/curriculum/${id}/`);
    return res.data;
};

export const createCurriculum = async (data) => {
    const res = await api.post('/learning/curriculum/', data);
    return res.data;
};

export const generateCurriculum = async () => {
    const res = await api.post('/learning/curriculum/generate/', {}, { timeout: 120000 });
    return res.data;
};

export const completeItem = async (curriculumId, itemId) => {
    const res = await api.post(`/learning/curriculum/${curriculumId}/complete_item/`, { item_id: itemId });
    return res.data;
};

export const rerouteCurriculum = async (curriculumId) => {
    const res = await api.post(`/learning/curriculum/${curriculumId}/reroute/`);
    return res.data;
};

export const getRerouteHistory = async (curriculumId) => {
    const res = await api.get(`/learning/curriculum/${curriculumId}/history/`);
    return res.data;
};
