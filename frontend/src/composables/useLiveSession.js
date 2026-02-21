/**
 * useLiveSession — 라이브 세션 관련 모든 상태 및 로직
 * (입장, 상태 폴링, 펄스, 퀴즈, Q&A, Weak Zone, 노트)
 */
import { ref, computed, watch, nextTick } from 'vue';
import api from '../api/axios';

export function useLiveSession(sttLogs) {
    // --- Live Session State ---
    const liveSessionData = ref(null);
    const liveSessionCode = ref('');
    const livePolling = ref(null);
    const lastSttSeq = ref(0);
    const liveNoteTab = ref('subtitle');
    const myPulse = ref(null);
    const livePulseStats = ref({ understand: 0, confused: 0, total: 0, understand_rate: 0 });

    // --- Live Quiz State ---
    const pendingQuiz = ref(null);
    const quizResult = ref(null);
    const quizAnswering = ref(false);
    const liveNote = ref(null);
    const notePolling = ref(null);
    const quizTimer = ref(0);
    const quizTimerInterval = ref(null);
    const quizTimeLimit = ref(60);

    // --- Weak Zone Alert State ---
    const weakZoneAlerts = ref([]);
    const showWeakZonePopup = ref(false);
    const currentWeakZone = ref(null);

    // --- Live Q&A State ---
    const liveQuestions = ref([]);
    const newQuestionText = ref('');
    const qaOpen = ref(false);

    // --- Computed ---
    const timerPercent = computed(() => {
        if (quizTimeLimit.value <= 0) return 100;
        return Math.max(0, (quizTimer.value / quizTimeLimit.value) * 100);
    });

    // --- Quiz Timer Watch ---
    watch(pendingQuiz, (newQuiz) => {
        if (quizTimerInterval.value) { clearInterval(quizTimerInterval.value); quizTimerInterval.value = null; }
        if (newQuiz) {
            quizTimeLimit.value = newQuiz.time_limit || 60;
            quizTimer.value = newQuiz.remaining_seconds || newQuiz.time_limit || 60;
            quizTimerInterval.value = setInterval(() => {
                quizTimer.value--;
                if (quizTimer.value <= 0) {
                    clearInterval(quizTimerInterval.value);
                    quizTimerInterval.value = null;
                    pendingQuiz.value = null;
                }
            }, 1000);
        }
    });

    // --- Functions ---
    const fetchWeakZoneAlerts = async () => {
        if (!liveSessionData.value || liveSessionData.value.status !== 'LIVE') return;
        try {
            const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/my-alerts/`);
            if (data.alerts && data.alerts.length > 0) {
                weakZoneAlerts.value = data.alerts;
                if (!showWeakZonePopup.value) {
                    currentWeakZone.value = data.alerts[0];
                    showWeakZonePopup.value = true;
                }
            }
        } catch (e) { /* silent */ }
    };

    const resolveWeakZone = async (alertId) => {
        if (!liveSessionData.value) return;
        try {
            await api.post(`/learning/live/${liveSessionData.value.session_id}/my-alerts/${alertId}/resolve/`);
            showWeakZonePopup.value = false;
            currentWeakZone.value = null;
            weakZoneAlerts.value = weakZoneAlerts.value.filter(a => a.id !== alertId);
        } catch (e) { /* silent */ }
    };

    const joinLiveSession = async () => {
        const code = liveSessionCode.value.trim().toUpperCase();
        if (code.length !== 6) { alert('6자리 코드를 입력해주세요.'); return; }
        try {
            const { data } = await api.post('/learning/live/join/', { session_code: code });
            liveSessionData.value = data;
            startLiveStatusPolling();
            return true;
        } catch (e) {
            alert(e.response?.data?.error || '세션 입장 실패');
            return false;
        }
    };

    const sendPulse = async (pulseType) => {
        if (!liveSessionData.value) return;
        try {
            await api.post(`/learning/live/${liveSessionData.value.session_id}/pulse/`, { pulse_type: pulseType });
            myPulse.value = pulseType;
        } catch (e) { console.error('Pulse error:', e); }
    };

    const answerLiveQuiz = async (quizId, answer) => {
        if (!liveSessionData.value || quizAnswering.value) return;
        quizAnswering.value = true;
        try {
            const { data } = await api.post(
                `/learning/live/${liveSessionData.value.session_id}/quiz/${quizId}/answer/`,
                { answer }
            );
            quizResult.value = data;
            pendingQuiz.value = null;
        } catch (e) {
            if (e.response?.status === 409) {
                pendingQuiz.value = null;
            } else {
                alert('응답 실패: ' + (e.response?.data?.error || ''));
            }
        } finally { quizAnswering.value = false; }
    };

    const dismissQuizResult = () => { quizResult.value = null; };

    const fetchLiveQuestions = async () => {
        if (!liveSessionData.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/questions/feed/`);
            liveQuestions.value = data;
        } catch {}
    };

    const askQuestion = async () => {
        const text = newQuestionText.value.trim();
        if (!text || !liveSessionData.value) return;
        try {
            await api.post(`/learning/live/${liveSessionData.value.session_id}/questions/ask/`, {
                question: text,
            });
            newQuestionText.value = '';
            await fetchLiveQuestions();
        } catch (e) {
            alert('질문 등록 실패: ' + (e.response?.data?.error || ''));
        }
    };

    const upvoteQuestion = async (questionId) => {
        if (!liveSessionData.value) return;
        try {
            await api.post(`/learning/live/${liveSessionData.value.session_id}/questions/${questionId}/upvote/`);
            await fetchLiveQuestions();
        } catch {}
    };

    // --- Review & Assessment (loaded after live session ends) ---
    const myReviewRoutes = ref([]);
    const srDueItems = ref([]);

    const fetchMyReviewRoutes = async () => {
        try {
            const { data } = await api.get('/learning/review-routes/my/');
            myReviewRoutes.value = data.routes || [];
        } catch (e) { /* silent */ }
    };

    const completeReviewItem = async (routeId, order) => {
        try {
            const { data } = await api.post(`/learning/review-routes/${routeId}/complete-item/`, { order });
            const route = myReviewRoutes.value.find(r => r.id === routeId);
            if (route) {
                route.completed_items = data.completed_items;
                route.progress = data.progress;
            }
        } catch (e) { /* silent */ }
    };

    const fetchSRDue = async () => {
        try {
            const { data } = await api.get('/learning/spaced-repetition/due/');
            srDueItems.value = data.due_items || [];
        } catch (e) { /* silent */ }
    };

    const completeSR = async (itemId, answer) => {
        try {
            const { data } = await api.post(`/learning/spaced-repetition/${itemId}/complete/`, { answer });
            if (data.is_correct) {
                srDueItems.value = srDueItems.value.filter(i => i.id !== itemId);
            }
            return data;
        } catch (e) { return null; }
    };

    // --- Formative Assessment ---
    const formativeData = ref(null);
    const formativeAnswers = ref({});
    const formativeResult = ref(null);
    const formativeSubmitting = ref(false);

    const fetchFormative = async () => {
        if (!liveSessionData.value) return;
        try {
            const { data } = await api.get(`/learning/formative/${liveSessionData.value.session_id}/`);
            if (data.available && !data.already_submitted) {
                formativeData.value = data;
            } else if (data.already_submitted) {
                formativeResult.value = { score: data.score, total: data.total };
            }
        } catch (e) { /* silent */ }
    };

    const submitFormative = async () => {
        if (!formativeData.value) return;
        formativeSubmitting.value = true;
        try {
            const answers = Object.entries(formativeAnswers.value).map(([qId, answer]) => ({
                question_id: parseInt(qId),
                answer,
            }));
            const { data } = await api.post(`/learning/formative/${formativeData.value.assessment_id}/submit/`, { answers });
            formativeResult.value = data;
            formativeData.value = null;
            await fetchSRDue();
        } catch (e) { /* silent */ }
        formativeSubmitting.value = false;
    };

    // --- Adaptive Content ---
    const myAdaptiveContent = ref([]);
    const myStudentLevel = ref(2);

    const fetchMyContent = async () => {
        if (!liveSessionData.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/my-content/`);
            myAdaptiveContent.value = data.contents || [];
            myStudentLevel.value = data.student_level || 2;
        } catch (e) { /* silent */ }
    };

    // --- Polling ---
    const fetchLiveNote = async () => {
        if (!liveSessionData.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/note/`);
            liveNote.value = data;
            if (data.status === 'DONE' || data.status === 'FAILED') {
                if (notePolling.value) { clearInterval(notePolling.value); notePolling.value = null; }
                if (data.status === 'DONE') {
                    fetchMyReviewRoutes();
                    fetchFormative();
                }
            }
        } catch {}
    };

    const startNotePolling = () => {
        fetchLiveNote();
        notePolling.value = setInterval(fetchLiveNote, 3000);
    };

    const startLiveStatusPolling = () => {
        stopLiveStatusPolling();
        livePolling.value = setInterval(async () => {
            if (!liveSessionData.value) return;
            try {
                const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/status/`);
                liveSessionData.value = { ...liveSessionData.value, ...data };
                if (data.status === 'ENDED') {
                    stopLiveStatusPolling();
                    startNotePolling();
                }
                // 펄스 통계
                try {
                    const pulse = await api.get(`/learning/live/${liveSessionData.value.session_id}/pulse-stats/`);
                    livePulseStats.value = pulse.data;
                } catch {}
                // 미응답 퀴즈 체크
                if (!pendingQuiz.value && !quizResult.value) {
                    try {
                        const qr = await api.get(`/learning/live/${liveSessionData.value.session_id}/quiz/pending/`);
                        if (qr.data.length > 0) {
                            pendingQuiz.value = qr.data[0];
                        }
                    } catch {}
                }
                // Q&A
                if (qaOpen.value) await fetchLiveQuestions();
                // Weak Zone
                await fetchWeakZoneAlerts();
                // STT 자막
                try {
                    const sttRes = await api.get(`/learning/live/${liveSessionData.value.session_id}/stt-feed/?after_seq=${lastSttSeq.value}`);
                    if (sttRes.data.length > 0) {
                        const existingIds = new Set(sttLogs.value.map(l => l.id));
                        for (const log of sttRes.data) {
                            if (!existingIds.has(log.id)) {
                                sttLogs.value.push({
                                    id: log.id,
                                    seq: log.seq,
                                    text_chunk: log.text,
                                    timestamp: log.timestamp,
                                });
                            }
                            if (log.seq > lastSttSeq.value) lastSttSeq.value = log.seq;
                        }
                        nextTick(() => {
                            const el = document.querySelector('.subtitle-scroll');
                            if (el) el.scrollTop = el.scrollHeight;
                        });
                    }
                } catch {}
            } catch {}
        }, 2000);
    };

    const stopLiveStatusPolling = () => {
        if (livePolling.value) { clearInterval(livePolling.value); livePolling.value = null; }
    };

    const leaveLiveSession = () => {
        stopLiveStatusPolling();
        if (notePolling.value) { clearInterval(notePolling.value); notePolling.value = null; }
        liveSessionData.value = null;
        myPulse.value = null;
        pendingQuiz.value = null;
        quizResult.value = null;
        liveNote.value = null;
        liveSessionCode.value = '';
    };

    return {
        // State
        liveSessionData, liveSessionCode, liveNoteTab, myPulse, livePulseStats,
        pendingQuiz, quizResult, quizAnswering, liveNote, quizTimer, quizTimeLimit,
        weakZoneAlerts, showWeakZonePopup, currentWeakZone,
        liveQuestions, newQuestionText, qaOpen,
        myReviewRoutes, srDueItems,
        formativeData, formativeAnswers, formativeResult, formativeSubmitting,
        myAdaptiveContent, myStudentLevel,

        // Computed
        timerPercent,

        // Functions
        joinLiveSession, sendPulse, answerLiveQuiz, dismissQuizResult,
        fetchLiveQuestions, askQuestion, upvoteQuestion,
        startLiveStatusPolling, stopLiveStatusPolling,
        fetchLiveNote, startNotePolling,
        fetchWeakZoneAlerts, resolveWeakZone,
        leaveLiveSession,
        fetchMyReviewRoutes, completeReviewItem, fetchSRDue, completeSR,
        fetchFormative, submitFormative,
        fetchMyContent,
    };
}
