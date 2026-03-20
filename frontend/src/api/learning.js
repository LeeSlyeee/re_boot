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

/**
 * SSE 스트리밍 AI 튜터 질문 — 실시간 토큰 전송
 * @param {number} sessionId
 * @param {string} message
 * @param {Object} callbacks - { onToken, onSources, onDone, onError }
 * @returns {AbortController} 스트리밍 취소용
 */
export const askAITutorStream = (sessionId, message, callbacks) => {
    const controller = new AbortController();
    const token = localStorage.getItem('token');
    const baseURL = api.defaults.baseURL || '';

    fetch(`${baseURL}/learning/chat/sessions/${sessionId}/ask-stream/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message }),
        signal: controller.signal,
    }).then(async (response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));
                    if (data.type === 'token' && callbacks.onToken) {
                        callbacks.onToken(data.content);
                    } else if (data.type === 'sources' && callbacks.onSources) {
                        callbacks.onSources(data.sources);
                    } else if (data.type === 'done' && callbacks.onDone) {
                        callbacks.onDone(data.message_id);
                    } else if (data.type === 'error' && callbacks.onError) {
                        callbacks.onError(data.content);
                    }
                } catch (e) { /* 파싱 에러 무시 */ }
            }
        }
    }).catch((err) => {
        if (err.name !== 'AbortError' && callbacks.onError) {
            callbacks.onError(err.message);
        }
    });

    return controller;
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
