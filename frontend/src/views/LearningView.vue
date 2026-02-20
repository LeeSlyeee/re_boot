<script setup>
import { ref, nextTick, computed, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router'; // useRoute added

// Debug Refs
const debugLastChunkSize = ref(0);
const debugLastStatus = ref('Init');
const debugLastResponse = ref('-');
import { Mic, Square, Pause, FileText, MonitorPlay, Users, Youtube, RefreshCw, Bot, Play, List, Plus, Lock, Download, PenLine } from 'lucide-vue-next';
import { AudioRecorder } from '../api/audioRecorder';
import api from '../api/axios';
import ChecklistPanel from '../components/ChecklistPanel.vue';

const router = useRouter();
const route = useRoute(); // Route access

// --- State Variables ---
const mode = ref(null); 
const youtubeUrl = ref('');
const watchHistory = ref([]); 
const isLoadingSession = ref(true); 
const isUrlSubmitted = ref(false); 
const pendingSessionId = ref(null); 
const isCompletedSession = ref(false); 

// --- Live Session State ---
const liveSessionData = ref(null);
const liveSessionCode = ref('');
const livePolling = ref(null);
const myPulse = ref(null); // 'UNDERSTAND' | 'CONFUSED' | null
const livePulseStats = ref({ understand: 0, confused: 0, total: 0, understand_rate: 0 });

// --- Live Quiz State ---
const pendingQuiz = ref(null);
const quizResult = ref(null);
const quizAnswering = ref(false);
const liveNote = ref(null);
const notePolling = ref(null);

const joinLiveSession = async () => {
    const code = liveSessionCode.value.trim().toUpperCase();
    if (code.length !== 6) { alert('6자리 코드를 입력해주세요.'); return; }
    try {
        const { data } = await api.post('/learning/live/join/', { session_code: code });
        liveSessionData.value = data;
        mode.value = 'live';
        startLiveStatusPolling();
    } catch (e) {
        alert(e.response?.data?.error || '세션 입장 실패');
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
            // 이미 응답함
            pendingQuiz.value = null;
        } else {
            alert('응답 실패: ' + (e.response?.data?.error || ''));
        }
    } finally { quizAnswering.value = false; }
};

const dismissQuizResult = () => { quizResult.value = null; };

const startLiveStatusPolling = () => {
    stopLiveStatusPolling();
    livePolling.value = setInterval(async () => {
        if (!liveSessionData.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/status/`);
            liveSessionData.value = { ...liveSessionData.value, ...data };
            if (data.status === 'ENDED') {
                stopLiveStatusPolling();
                // 노트 폴링 시작
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
                        pendingQuiz.value = qr.data[0]; // 가장 최신 1개
                    }
                } catch {}
            }
        } catch {}
    }, 5000);
};

const stopLiveStatusPolling = () => {
    if (livePolling.value) { clearInterval(livePolling.value); livePolling.value = null; }
};

const fetchLiveNote = async () => {
    if (!liveSessionData.value) return;
    try {
        const { data } = await api.get(`/learning/live/${liveSessionData.value.session_id}/note/`);
        liveNote.value = data;
        if (data.status === 'DONE' || data.status === 'FAILED') {
            if (notePolling.value) { clearInterval(notePolling.value); notePolling.value = null; }
        }
    } catch {}
};

const startNotePolling = () => {
    fetchLiveNote();
    notePolling.value = setInterval(fetchLiveNote, 3000);
};

const renderMarkdown = (text) => {
    if (!text) return '';
    return text
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/\n/g, '<br/>');
};

const leaveLiveSession = () => {
    stopLiveStatusPolling();
    if (notePolling.value) { clearInterval(notePolling.value); notePolling.value = null; }
    liveSessionData.value = null;
    myPulse.value = null;
    pendingQuiz.value = null;
    quizResult.value = null;
    liveNote.value = null;
    mode.value = null;
    liveSessionCode.value = '';
};

// --- Lecture Mode State ---
const currentLectureId = ref(null);
const sessions = ref([]); // Renamed from lectureSessions
const missedSessions = ref([]); // [New] Missed classes by others
const showLectureSidebar = ref(false); // This might become obsolete with the new UI, but keeping for now

const fetchLectureSessions = async (lectureId) => {
    try {
        const res = await api.get(`/learning/sessions/lectures/${lectureId}/`);
        sessions.value = res.data;
        
        // [New] Dynamic Re-routing Analysis
        analyzeChecklist(lectureId);
        
    } catch (e) {
        if (e.response?.status === 401) {
            alert("로그인이 필요합니다.");
            router.push('/login');
            // Stop further execution to prevent cascading errors
            throw e; 
        }
        console.error("Failed to load sessions", e);
    }
};

// [New] Dynamic Re-routing State
const recoveryStatus = ref(null);
const recoveryRecommendation = ref(null);
const showRecoveryModal = ref(false);
const isGeneratingRecovery = ref(false);
const recoveryPlanContent = ref('');

const analyzeChecklist = async (lectureId) => {
    try {
        console.log(`🔍 Analyzing Checklist for Lecture: ${lectureId}`);
        const res = await api.get(`/learning/checklist/analyze/?lecture_id=${lectureId}`);
        
        recoveryStatus.value = res.data.status;
        recoveryRecommendation.value = res.data.recommendation;
        
        if (recoveryStatus.value === 'critical' || recoveryStatus.value === 'warning') {
            console.log("🚨 Re-routing Suggested:", recoveryRecommendation.value);
        }
    } catch (e) {
        console.error("Analysis Failed", e);
    }
};

const executeRecoveryPlan = async () => {
    // Phase 2: Open Compressed Course
    if (!currentLectureId.value) return;
    
    isGeneratingRecovery.value = true;
    showRecoveryModal.value = true; // Open modal first (showing loading state)
    
    try {
        const res = await api.post(`/learning/checklist/recovery_plan/`, {
             lecture_id: currentLectureId.value
        });
        recoveryPlanContent.value = res.data.recovery_plan;
    } catch (e) {
        alert("복구 플랜 생성에 실패했습니다.");
        showRecoveryModal.value = false;
    } finally {
        isGeneratingRecovery.value = false;
    }
};

const fetchMissedSessions = async (lectureId) => {
    try {
        const res = await api.get(`/learning/sessions/lectures/${lectureId}/missed/`);
        missedSessions.value = res.data;
    } catch (e) {
        console.error("Failed to fetch missed sessions", e);
    }
};

const openSharedSession = async (missed) => {
    if (!missed.representative_session_id) return;
    
    // Load shared session details
    // We can reuse fetchSessionDetails but need to handle "Shared" state
    try {
        isLoadingSession.value = true;
        const res = await api.get(`/learning/sessions/${missed.representative_session_id}/`);
        const sessionData = res.data;
        
        // Set Shared View State
        sessionId.value = sessionData.id; // For RAG to work
        
        // Fetch logs separately
        try {
            const logRes = await api.get(`/learning/sessions/${sessionId.value}/logs/`);
            sttLogs.value = logRes.data || [];
        } catch (logErr) {
            console.error("Failed to fetch logs for shared session", logErr);
            sttLogs.value = [];
        }

        sessionSummary.value = sessionData.latest_summary || "# [공유된 학습 노트]\n\n아직 요약이 생성되지 않았습니다.";
        youtubeUrl.value = sessionData.youtube_url || '';
        
        isSharedView.value = true;
        isCompletedSession.value = true; // [FIX] Treat as completed/read-only
        currentClassTitle.value = `[보충] ${new Date(missed.date).toLocaleDateString()} 수업 (공유됨)`; 
        
        // Switch to appropriate Mode
        if (sessionData.youtube_url) {
             mode.value = 'youtube';
             isUrlSubmitted.value = true; // [FIX] Prevent URL input overlay
        } else {
             mode.value = 'offline';
             isUrlSubmitted.value = true; // Treat as submitted for consistency
        }
        
    } catch (e) {
        alert("공유 데이터를 불러오는데 실패했습니다.");
    } finally {
        isLoadingSession.value = false;
    }
};

const loadSessionFromSidebar = (session) => {
    // 세션 로드
    resumeSessionById(session.id);
};

const startNewClassSession = () => {
    // 수업 모드에서 '새 수업 시작' -> 오프라인(마이크/시스템) 모드로 전환
    // currentLectureId는 유지되므로 startRecording 시 자동으로 연동됨
    selectMode('offline');
};

// --- State Management ---
const isRecording = ref(false);
const sttLogs = ref([]); 
const recorder = ref(null);
const logsContainer = ref(null);
const sessionId = ref(null);
const nextSequenceOrder = ref(1); // [FIX] Top-level ref for sequence tracking

// Quiz State
const quizData = ref(null);
const showQuiz = ref(false);
const quizAnswers = ref({});
const quizResult = ref(null);
const isGeneratingQuiz = ref(false);
const isSubmittingQuiz = ref(false);

// --- RAG Chat State ---
const isChatOpen = ref(false);
const chatMessages = ref([
    { role: 'ai', text: '안녕하세요! 수업 중 궁금한 점이 있으면 언제든 물어보세요. 😊' }
]);
const chatInput = ref('');
const isChatLoading = ref(false);
const chatScrollRef = ref(null);

const toggleChat = () => {
    isChatOpen.value = !isChatOpen.value;
    if (isChatOpen.value) scrollToChatBottom();
};

const scrollToChatBottom = async () => {
    await nextTick();
    if (chatScrollRef.value) {
        chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight;
    }
};

const sendChatMessage = async () => {
    if (!chatInput.value.trim() || isChatLoading.value) return;

    const userText = chatInput.value;
    chatMessages.value.push({ role: 'user', text: userText });
    chatInput.value = '';
    scrollToChatBottom();

    isChatLoading.value = true;
    try {
        const res = await api.post('/learning/rag/ask/', {
            q: userText,
            session_id: sessionId.value,
            lecture_id: currentLectureId.value,
            // 라이브 세션 중이면 자동으로 교수자에게 익명 전달
            live_session_id: liveSessionData.value?.session_id || null,
        });

        chatMessages.value.push({ role: 'ai', text: res.data.answer });
    } catch (e) {
        console.error("Chat Error:", e);
        chatMessages.value.push({ role: 'ai', text: " 죄송합니다. 답변을 가져오는 중 오류가 발생했습니다." });
    } finally {
        isChatLoading.value = false;
        scrollToChatBottom();
    }
};

// --- Join Class Logic ---
const showJoinModal = ref(false);
const joinCode = ref('');
const availableLectures = ref([]);
const selectedLectureId = ref(null);
const currentClassTitle = ref(null); 
const isSharedView = ref(false); // [New] Is viewing shared content?

const myLectures = ref([]); // [New] My Enrolled Lectures

const fetchMyLectures = async () => {
    try {
        const res = await api.get('/learning/lectures/my/');
        myLectures.value = res.data;
    } catch (e) {
        console.error("Failed to fetch my lectures", e);
    }
};

const fetchAvailableLectures = async () => {
    // Legacy: Unused now
    try {
        const res = await api.get('/learning/lectures/public/');
        availableLectures.value = res.data;
    } catch (e) {
        console.error("Failed to fetch public lectures", e);
    }
};

const openJoinModal = () => {
    showJoinModal.value = true;
    joinCode.value = '';
    selectedLectureId.value = null;
    fetchMyLectures(); // [FIX] Show my enrolled lectures
};
const closeJoinModal = () => {
    showJoinModal.value = false;
};

const selectLecture = async (lecture) => {
    // [Security Fix] Prevent accessing unenrolled lectures
    if (!lecture.is_enrolled) {
        alert("이 클래스를 수강하려면 [입장 코드]를 입력해야 합니다.\n상단의 '클래스 참여하기' 버튼을 이용해주세요.");
        selectedLectureId.value = lecture.id;
        // Optionally pre-fill or focus join input
        return;
    }
    
    // [UX Improvement] Remove native confirm() to prevent flaky behavior.
    // Directly proceed with selection.
    
    try {
        currentClassTitle.value = lecture.title;
        currentLectureId.value = lecture.id;
        
        // Fetch sessions first
        await fetchLectureSessions(lecture.id);
        
        // [New] Fetch missed sessions
        await fetchMissedSessions(lecture.id);
        
        // Only close modal and switch mode upon success
        showJoinModal.value = false;
        mode.value = 'lecture';
        
    } catch (e) {
        console.error("Lecture Selection Failed:", e);
        if (e.response && e.response.status === 401) {
            alert("로그인이 필요한 기능입니다.");
            router.push('/login');
        } else {
            alert("수업을 불러오는데 실패했습니다. (서버 오류)");
        }
    }
};

const joinClass = async () => {
    if (!joinCode.value || joinCode.value.length < 6) return;
    
    try {
        const res = await api.post('/learning/enroll/', { access_code: joinCode.value });
        
        // 1. 성공 알림 및 모달 닫기
        alert(`'${res.data.title}' 클래스 입장 완료! 수업을 시작합니다.`);
        closeJoinModal();

        // 2. 클래스 정보 설정 및 오프라인 모드 진입
        currentClassTitle.value = res.data.title;
        selectMode('offline');

    } catch (e) {
        console.error(e);
        const msg = e.response?.data?.error || e.response?.data?.message || "코드가 올바르지 않거나 이미 가입된 클래스입니다.";
        alert(msg);
    }
};

// --- 1. 진입 로직 ---
onMounted(async () => {
    try {
        console.log("🚀 LearningView Mounted.");
        
        // [NEW] Check for Lecture Mode (from Dashboard)
        const queryLectureId = route.query.lectureId;
        const querySessionId = route.query.sessionId;
        const savedSessionId = localStorage.getItem('currentSessionId');

        if (queryLectureId) {
             console.log(`ℹ️ Opening Lecture Mode: ${queryLectureId}`);
             currentLectureId.value = queryLectureId;
             await fetchLectureSessions(queryLectureId);
             await fetchMissedSessions(queryLectureId); // Fetch missed sessions when entering lecture mode
             
             // [FIX] Ensure analysis runs on entry
             analyzeChecklist(queryLectureId);
             
             mode.value = 'lecture';
             // Don't auto-resume session unless user picks one
        } else if (querySessionId) {
             console.log(`ℹ️ Resuming Session from Query: ${querySessionId}`);
             await resumeSessionById(querySessionId);
             // [TODO] If resuming session, we might want to analyze its parent lecture too
             // But for now, analysis is main feature of Lecture List View
        } else if (savedSessionId) {
            // [UX 개선] 미완료 세션이 있어도 자동 복원하지 않음
            // → 모드 선택 화면에서 "이전 학습 이어하기" 카드를 보여주고
            //   사용자가 직접 선택하거나, 새로운 학습을 시작할 수 있도록 함
            pendingSessionId.value = savedSessionId;
            mode.value = null; // 모드 선택 화면 표시
        } else {
            // [FIX] 저장된 세션이 없으면 전체 상태 클린 리셋
            // → 이전 학습 완료 후 재진입 시 모드 선택 화면이 뜨도록 보장
            mode.value = null;
            sessionId.value = null;
            pendingSessionId.value = null;
            isUrlSubmitted.value = false;
            isCompletedSession.value = false;
            sttLogs.value = [];
            youtubeUrl.value = '';
        }
        
        // Load History
        const history = localStorage.getItem('watchHistory');
        if (history) watchHistory.value = JSON.parse(history);

    } finally {
        isLoadingSession.value = false;
    }
});

// --- Helper Functions ---
// --- State Management (Additions) ---
const sessionSummary = ref('');
const activeTab = ref('stt');
const isGeneratingSummary = ref(false);

// ── Note Feature ──
const showNoteEditor = ref(false);
const noteContent = ref('');
const isSavingNote = ref(false);

const toggleNoteEditor = async () => {
    showNoteEditor.value = !showNoteEditor.value;
    if (showNoteEditor.value && sessionId.value) {
        // 기존 노트 로드
        try {
            const res = await api.get(`/learning/sessions/${sessionId.value}/note/`);
            noteContent.value = res.data.note || '';
        } catch (e) {
            console.error('노트 로드 실패', e);
        }
    }
};

const saveNote = async () => {
    if (!sessionId.value || !noteContent.value.trim()) return;
    isSavingNote.value = true;
    try {
        const res = await api.post(`/learning/sessions/${sessionId.value}/note/`, {
            note: noteContent.value
        });
        // 요약본 갱신 (메모가 포함된 새 내용)
        if (res.data.content) {
            sessionSummary.value = res.data.content;
        }
        alert('✅ 메모가 저장되었습니다.');
    } catch (e) {
        console.error('노트 저장 실패', e);
        alert('메모 저장에 실패했습니다.');
    } finally {
        isSavingNote.value = false;
    }
};

// ── PDF Export ──
const exportPdf = () => {
    if (!sessionId.value) return;
    // 직접 새 창에서 열어서 브라우저 인쇄→PDF 가능
    const token = localStorage.getItem('token');
    const url = `${api.defaults.baseURL}/learning/sessions/${sessionId.value}/export-pdf/`;
    // API 호출 후 HTML 다운로드
    api.get(`/learning/sessions/${sessionId.value}/export-pdf/`, {
        responseType: 'blob'
    }).then(res => {
        const blob = new Blob([res.data], { type: 'text/html' });
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `ReBootNote_${sessionId.value}.html`;
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
    }).catch(e => {
        console.error('PDF 내보내기 실패', e);
        alert('내보내기에 실패했습니다.');
    });
};

const generateSummary = async () => {
    if (!sessionId.value) return;
    
    isGeneratingSummary.value = true;
    try {
        // Force regeneration
        const res = await api.post(`/learning/sessions/${sessionId.value}/summarize/`);
        console.log("Summary Response:", res);

        if (res.data && res.data.content_text) {
            console.log("✅ Summary Generated:", res.data.content_text.length, "chars");
            sessionSummary.value = res.data.content_text;
            activeTab.value = 'summary'; // Switch to summary tab
            // Alert removed
        } else {
            console.warn("⚠️ Summary response empty or invalid:", res.data);
            alert("서버에서 요약 내용을 받지 못했습니다.");
        }
    } catch (e) {
        console.error("Summary Generation Failed:", e);
        if (e.response && e.response.status === 400) {
            alert("⚠️ 요약할 자막 내용이 없습니다. (수업 내용을 먼저 녹음해주세요)");
        } else {
            alert("요약 생성에 실패했습니다. (서버 오류)");
        }
    } finally {
        isGeneratingSummary.value = false;
    }
};

const resumeSession = async (isAutoRestore = false) => {
    // pendingSessionId가 없으면 로컬 스토리지에서 가져오기 (Auto Restore 시)
    const targetSessionId = pendingSessionId.value || localStorage.getItem('currentSessionId');
    if (!targetSessionId) return;
    
    isLoadingSession.value = true;
    try {
        const savedUrl = localStorage.getItem('currentYoutubeUrl');
        
        // 1. DB 확인
        const sessionRes = await api.get(`/learning/sessions/${targetSessionId}/`);
        
        // [FIX] 자동 복구(Auto Restore)인데 이미 완료된 수업이다? -> 복구 안 함 (새판 짜기)
        if (isAutoRestore && sessionRes.data.is_completed) {
            console.log("ℹ️ Auto-restore skipped: Session is already completed.");
            // 로컬 스토리지 청소 -> 사용자에게 '새로운 학습 선택' 기회 제공
            localStorage.removeItem('currentSessionId');
            localStorage.removeItem('currentYoutubeUrl');
            pendingSessionId.value = null;
            sessionId.value = null; // Ensure clean state
            return;
        }

        // 수동 복구이거나, 아직 완료 안 된 세션이면 -> 진행
        sessionId.value = targetSessionId;

        // 저장된 요약본이 있으면 로드
        if (sessionRes.data.latest_summary) {
            sessionSummary.value = sessionRes.data.latest_summary;
        }

        if (sessionRes.data.is_completed) {
            console.log("ℹ️ This session is completed. Entering Review Mode.");
            isCompletedSession.value = true;
            // [FIX] 요약본이 있을 때만 요약 탭을 기본으로 보여줌, 없으면 자막(STT) 탭
            if (sessionSummary.value && sessionSummary.value.trim().length > 0) {
                activeTab.value = 'summary';
            } else {
                activeTab.value = 'stt';
            }
        } else {
            isCompletedSession.value = false;
            activeTab.value = 'stt';
        }

        // [FIX] 우선순위 로직 수정
        // 1. Lecture(수업) 정보가 있으면 -> 무조건 Offline/Hybrid 모드
        if (sessionRes.data.lecture) {
            mode.value = 'offline';
             // (선택) Lecture Title 복구 로직이 필요하다면 여기서 API 호출 추가 가능
             // 현재는 간단히 오프라인 모드로 고정
             if (sessionRes.data.youtube_url) {
                 youtubeUrl.value = sessionRes.data.youtube_url;
                 localStorage.setItem('currentYoutubeUrl', youtubeUrl.value);
             }
             isUrlSubmitted.value = !!sessionRes.data.youtube_url;
        } 
        // 2. 유튜브 URL만 있으면 -> Youtube 모드
        else if (sessionRes.data.youtube_url) {
            youtubeUrl.value = sessionRes.data.youtube_url;
            mode.value = 'youtube';
            isUrlSubmitted.value = true;
            localStorage.setItem('currentYoutubeUrl', youtubeUrl.value);
        } 
        // 3. 그 외 (localStorage fallback)
        else {
             if (savedUrl) {
                youtubeUrl.value = savedUrl;
                mode.value = 'youtube';
                isUrlSubmitted.value = true; 
            } else {
                const restoredMode = localStorage.getItem('restoredMode');
                mode.value = restoredMode || 'universal';
            }
        }
        
        // 2. 로그 복구
        const logRes = await api.get(`/learning/sessions/${targetSessionId}/logs/`);
        if (logRes.data && Array.isArray(logRes.data)) {
            sttLogs.value = logRes.data;
        }
        
    } catch(e) {
        console.error("Resume Failed", e);
        
        // [FIX] 보안 강화: 내 세션이 아니거나(403), 없는 세션(404)이면 즉시 격리
        if (e.response && (e.response.status === 403 || e.response.status === 404)) {
            console.warn("⚠️ Unauthorized or Invalid Session detected. Clearing storage.");
            localStorage.removeItem('currentSessionId');
            localStorage.removeItem('currentYoutubeUrl');
            localStorage.removeItem('restoredMode');
            mode.value = null;
            sessionId.value = null;
            pendingSessionId.value = null;
        } else {
            // 그 외 오류(네트워크 등)는 조용히 실패 처리
            localStorage.removeItem('currentSessionId');
            pendingSessionId.value = null;
        }
    } finally {
        isLoadingSession.value = false;
    }
};

const resumeSessionById = async (id) => {
    console.log(`Open Session: ${id}`);
    pendingSessionId.value = id;
    localStorage.setItem('currentSessionId', id); 
    await resumeSession(false);
};

const addToHistory = (url) => {
    const existingIdx = watchHistory.value.indexOf(url);
    if (existingIdx > -1) watchHistory.value.splice(existingIdx, 1);
    watchHistory.value.unshift(url);
    if (watchHistory.value.length > 5) watchHistory.value.pop();
    localStorage.setItem('watchHistory', JSON.stringify(watchHistory.value));
};

const youtubeEmbedUrl = computed(() => {
    if (!youtubeUrl.value) return '';
    let url = youtubeUrl.value;
    let videoId = '';
    
    if (url.includes('v=')) {
        videoId = url.split('v=')[1].split('&')[0];
    } else if (url.includes('youtu.be/')) {
        videoId = url.split('youtu.be/')[1].split('?')[0];
    } else if (url.includes('embed/')) {
        videoId = url.split('embed/')[1].split('?')[0];
    } else if (url.includes('shorts/')) {
        videoId = url.split('shorts/')[1].split('?')[0];
    }

    return videoId ? `https://www.youtube.com/embed/${videoId}` : '';
});

const selectMode = (selectedMode) => {
    // [CHANGE] 새 모드 선택 시 기존 대기 세션 정보 파기 (Confirm 제거)
    if (pendingSessionId.value) {
        // User explicitly chose a new mode, so we discard the pending/restorable session.
        localStorage.removeItem('currentSessionId');
        localStorage.removeItem('currentYoutubeUrl');
        localStorage.removeItem('restoredMode');
        pendingSessionId.value = null;
    }
    mode.value = selectedMode;
};

// [FIX] URL 제출 로직 개선
const submitYoutube = () => {
    if (!youtubeEmbedUrl.value) {
        alert("올바른 유튜브 링크를 입력해주세요 (예: https://youtube.com/watch?v=...)");
        return;
    }
    
    // 1. 여기서 확실하게 플래그를 올려서 오버레이를 닫음
    isUrlSubmitted.value = true;
    
    // Save Local
    localStorage.setItem('currentYoutubeUrl', youtubeUrl.value);
    addToHistory(youtubeUrl.value);
    
    // Update Backend
    if (sessionId.value) {
        let urlToSave = youtubeUrl.value.trim();
        if (!urlToSave.startsWith('http')) urlToSave = 'https://' + urlToSave;

        api.post(`/learning/sessions/${sessionId.value}/update-url/`, {
            youtube_url: urlToSave
        }).then(() => {
            console.log("✅ URL Saved to Backend");
        }).catch(err => {
            console.error("URL Save Failed:", err);
            alert("저장 실패 (서버 오류)");
            isUrlSubmitted.value = false; // 실패 시 다시 열어줌
        });
    }
};

// --- Recording Logic ---
watch(sttLogs, async () => {
    await nextTick();
    scrollToBottom();
}, { deep: true });

const startRecording = async () => {
    // [FIX] 완료된 세션(복습 모드)에서는 녹음 불가
    if (isCompletedSession.value) {
        alert("이 수업은 이미 완료되어 복습 모드로 실행 중입니다. (추가 녹음 불가)");
        return;
    }

    if (!sessionId.value) {
        try {
            console.log("DEBUG: Creating Session. Lecture ID:", currentLectureId.value);
            const response = await api.post('/learning/sessions/', { 
                section: null, 
                session_order: 1,
                lecture: currentLectureId.value || null, // Link to current lecture if valid
                youtube_url: (youtubeUrl.value && !youtubeUrl.value.startsWith('http')) 
                             ? 'https://' + youtubeUrl.value 
                             : (youtubeUrl.value || null)
            });
            sessionId.value = response.data.id;
            localStorage.setItem('currentSessionId', sessionId.value);
            console.log("🆕 Session Created:", sessionId.value);
        } catch (e) {
            console.error("Session Create Error:", e);
            if (e.response && e.response.status === 401) {
                alert("세션을 시작하려면 로그인이 필요합니다.");
                router.push('/login');
            } else {
                alert("세션 생성 실패. 다시 시도해주세요.");
            }
            return;
        }
    }

    isRecording.value = true;
    nextSequenceOrder.value = sttLogs.value.length + 1; // Sync with current logs
    recorder.value = new AudioRecorder(handleAudioData);
    
    try {
        // [FIX] 영상 강의(하이브리드) 모드면 무조건 시스템 오디오(탭 오디오) 녹음
        if (mode.value === 'offline' && !youtubeEmbedUrl.value) {
             await recorder.value.startMic(3000);
        } else {
             // 그 외 (유튜브 모드, 유니버설 모드, 오프라인+영상 모드) -> 시스템 오디오 사용
             await recorder.value.startSystemAudio(3000);
        }
    } catch (err) {
        console.error("Rec Error:", err);
        isRecording.value = false;
    }
};

const stopRecording = () => {
    isRecording.value = false;
    if (recorder.value) {
        recorder.value.stop();
        recorder.value = null;
    }
};

const processingCount = ref(0);
const isProcessingAudio = computed(() => processingCount.value > 0);

const handleAudioData = async (audioBlob) => {
    if (audioBlob.size < 1000) {
        return;
    }

    // [FIX] Detect correct file extension relative to MimeType
    let ext = 'webm';
    if (audioBlob.type.includes('mp4')) ext = 'mp4';
    else if (audioBlob.type.includes('ogg')) ext = 'ogg';
    else if (audioBlob.type.includes('wav')) ext = 'wav';
    
    // Capture and Increment Sequence
    const currentSeq = nextSequenceOrder.value;
    nextSequenceOrder.value++;

    // Debug Update
    debugLastChunkSize.value = audioBlob.size;
    debugLastStatus.value = `Sending #${currentSeq}...`;

    console.log(`🎤 Uploading chunk #${currentSeq}: ${audioBlob.size} bytes, type: ${audioBlob.type}`);
    processingCount.value++; 
    scrollToBottom(); 

    const formData = new FormData();
    formData.append('audio_file', audioBlob, `chunk.${ext}`);
    formData.append('sequence_order', currentSeq);

    try {
        const { data } = await api.post(`/learning/sessions/${sessionId.value}/audio/`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        console.log(`✅ Chunk #${currentSeq} Response:`, data);
        debugLastStatus.value = `Success #${currentSeq}`;
        debugLastResponse.value = data.text ? data.text.substring(0, 10) + '...' : 'No Text';

        if (data.text) {
             const newLog = {
                id: data.id || Date.now(),
                sequence_order: currentSeq, // Use local tracked sequence
                text_chunk: data.text,
                timestamp: new Date().toLocaleTimeString()
            };
            sttLogs.value.push(newLog);
            scrollToBottom();
        } else if (data.status === 'silence_skipped') {
            console.log(`Silence skipped for #${currentSeq} (Reason: ${data.reason})`);
            debugLastResponse.value = `Skipped: ${data.reason}`;
        }
    } catch (e) { 
        console.error(`STT Error for #${currentSeq}:`, e);
        debugLastStatus.value = `Error #${currentSeq}`;
        debugLastResponse.value = e.message;
    } finally {
        processingCount.value--; // Decrement counter
    }
};

const scrollToBottom = async () => {
    await nextTick();
    if (logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
    }
};

const startNewSession = () => {
    // [UX Improvement] Remove confirm dialog. 
    // If user clicks "New Learning", they intend to reset.
    if (isRecording.value) stopRecording();
    
    // Reset State
    mode.value = null;
    sessionId.value = null;
    pendingSessionId.value = null;
    sttLogs.value = [];
    youtubeUrl.value = '';
    currentLectureId.value = null;
    currentClassTitle.value = null;
    
    isCompletedSession.value = false;
    isUrlSubmitted.value = false;
    sessionSummary.value = '';
    isSharedView.value = false; // Reset shared view flag
    
    // Clear Storage
    localStorage.removeItem('currentSessionId');
    localStorage.removeItem('currentYoutubeUrl');
    localStorage.removeItem('restoredMode');
};

const loadQuiz = async () => {
    isGeneratingQuiz.value = true;
    try {
        const { data } = await api.post('/learning/assessment/generate-daily-quiz/', {
            session_id: sessionId.value 
        });
        quizData.value = data; 
        showQuiz.value = true;
    } catch (e) {
        alert("퀴즈 생성 실패: " + (e.response?.data?.error || "알 수 없는 오류"));
    } finally {
        isGeneratingQuiz.value = false;
    }
};

const endSession = async () => {
    if (!confirm('수업을 완료하시겠습니까? (AI 요약 및 퀴즈 생성)')) return;
    stopRecording();
    isGeneratingQuiz.value = true;

    if (sessionId.value) {
        // [NEW] 1. AI 요약 생성 요청
        try {
            console.log("📝 Generating Summary...");
            await api.post(`/learning/sessions/${sessionId.value}/summarize/`);
            console.log("✅ Summary Generated");
        } catch(e) {
            console.error("Summary Generation Failed:", e);
        }

        // 2. 세션 종료 처리
        try { await api.post(`/learning/sessions/${sessionId.value}/end/`); } catch(e) {}
        
        // [FIX] 세션 종료 시 로컬 스토리지 + Vue 상태 모두 정리
        localStorage.removeItem('currentSessionId');
        localStorage.removeItem('currentYoutubeUrl');
        localStorage.removeItem('restoredMode');
        
        // Vue 상태 초기화 (퀴즈 끝나고 재진입 시 모드 선택 화면 보장)
        sessionId.value = null;
        pendingSessionId.value = null;
    }

    // 3. 퀴즈 생성 요청
    await loadQuiz();
};

const startVideoLecture = async () => {
    const url = prompt("학습할 유튜브 영상 URL을 입력하세요:");
    if (!url) return;
    
    // 1. Update State (Stay in Offline Mode)
    youtubeUrl.value = url;
    isUrlSubmitted.value = true;
    localStorage.setItem('currentYoutubeUrl', url);

    // 2. Update Backend (if session exists)
    if (sessionId.value) {
         try {
            await api.post(`/learning/sessions/${sessionId.value}/update-url/`, {
                youtube_url: url
            });
            console.log("✅ Session converted to Video Mode (Hybrid)");
         } catch(e) { console.error("Failed to update session URL", e); }
    }
};

const submitQuiz = async () => {
    if (!quizData.value || isSubmittingQuiz.value) return;
    isSubmittingQuiz.value = true;
    try {
        const { data } = await api.post(`/learning/assessment/${quizData.value.id}/submit/`, {
            answers: quizAnswers.value
        });
        quizResult.value = data;
    } catch (e) {
        alert("제출 실패: " + (e.response?.data?.error || "서버 오류"));
    } finally {
        isSubmittingQuiz.value = false;
    }
};

const formatTime = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
};

const openSessionReview = (id) => {
    resumeSessionById(id);
};
</script>

<template>
  <div class="learning-view">
    
    <!-- ✅ LOADING STATE -->
    <div v-if="isLoadingSession" class="loading-overlay">
        <div class="glass-panel" style="padding: 40px; text-align: center;">
             <div class="spinner"></div>
            <p style="font-size: 16px; margin-top: 20px; color: #888;">학습 기록을 확인 중입니다...</p>
        </div>
    </div>

    <!-- ✅ MAIN CONTENT -->
    <template v-else>
        
        <!-- [FIX] 1. Mode Selection Modal -->
        <!-- youtubeEmbedUrl이 있어도 isUrlSubmitted가 false면 계속 떠 있음 (버튼 클릭 유도) -->
        <div v-if="!mode || (mode === 'youtube' && !isUrlSubmitted) || (mode === 'live' && !liveSessionData)" class="mode-overlay">
            <div class="glass-panel mode-card">
                <!-- Select Button Group -->
                <div v-if="!mode">
                    <h2 class="text-headline">오늘의 학습 방식은?</h2>
                    
                    <!-- [NEW] Resume Option -->
                    <div v-if="pendingSessionId" class="resume-section" @click="resumeSession">
                        <div class="resume-card glass-panel">
                             <div class="icon-box"><FileText size="24" /></div>
                             <div class="info">
                                 <h3>이전 학습 이어하기</h3>
                                 <p>저장된 세션이 있습니다. 클릭하여 계속하세요.</p>
                             </div>
                             <div class="arrow">→</div>
                        </div>
                    </div>

                    <div class="mode-grid">
                        <!-- Row 1: Offline Options -->
                        <div class="mode-item special" @click="openJoinModal">
                            <Users size="36" class="icon" /> <h3>클래스 참여</h3>
                            <p class="desc">정규 수업 듣기</p>
                        </div>
                        <div class="mode-item" @click="selectMode('offline')">
                            <Mic size="36" class="icon" /> <h3>현장 강의(1회용)</h3>
                            <p class="desc">단발성 특강 녹음</p>
                        </div>

                        <!-- Row 2: Online Options -->
                        <div class="mode-item" @click="selectMode('youtube')">
                            <Youtube size="36" class="icon" /> <h3>유튜브 학습</h3>
                            <p class="desc">영상 보며 학습</p>
                        </div>
                        <div class="mode-item" @click="selectMode('universal')">
                            <MonitorPlay size="36" class="icon" /> <h3>모든 인강</h3>
                            <p class="desc">PC 소리 캡처</p>
                        </div>

                        <!-- Row 3: 라이브 세션 -->
                        <div class="mode-item live-mode" @click="selectMode('live')" style="grid-column: 1 / -1;">
                            <span style="font-size:36px;">🟢</span> <h3>라이브 세션 참여</h3>
                            <p class="desc">교수자가 발급한 6자리 코드로 실시간 수업 참여</p>
                        </div>
                    </div>
                </div>

                <!-- Step 2: 라이브 세션 코드 입력 -->
                <div v-else-if="mode === 'live' && !liveSessionData">
                    <div class="back-link" @click="mode = null">← 뒤로가기</div>
                    <h2 class="text-headline">라이브 세션 입장</h2>
                    <p style="text-align:center; color:#aaa; margin-bottom:20px;">교수자가 알려준 6자리 코드를 입력하세요.</p>
                    <div class="input-group">
                        <input type="text" v-model="liveSessionCode" placeholder="코드 입력 (예: A3F2K9)" maxlength="6" 
                            style="text-align:center; font-size:24px; letter-spacing:8px; font-weight:700; text-transform:uppercase;" 
                            @keyup.enter="joinLiveSession" />
                        <button class="btn btn-primary" @click="joinLiveSession">입장하기</button>
                    </div>
                </div>

                <!-- Step 2: Input URL -->
                <div v-else-if="mode === 'youtube'">
                    <div class="back-link" @click="mode = null">← 뒤로가기</div>
                    <h2 class="text-headline">유튜브 링크 입력</h2>
                    <div class="input-group">
                        <input type="text" v-model="youtubeUrl" placeholder="https://youtube.com..." @keyup.enter="submitYoutube">
                        <!-- '시작' 버튼을 눌러야만 submitYoutube -> isUrlSubmitted=true -> 오버레이 닫힘 -->
                        <button class="btn btn-primary" @click="submitYoutube">시작</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══ LIVE SESSION VIEW ═══ -->
        <div v-if="mode === 'live' && liveSessionData" class="live-session-view">
            <div class="glass-panel live-info-panel">
                <div class="live-header">
                    <h2>🟢 {{ liveSessionData.title }}</h2>
                    <span class="live-badge" :class="liveSessionData.status">
                        {{ liveSessionData.status === 'LIVE' ? '진행 중' : liveSessionData.status === 'WAITING' ? '대기 중' : '종료됨' }}
                    </span>
                </div>
                <p class="session-code-small">세션 코드: <strong>{{ liveSessionData.session_code }}</strong></p>
                
                <!-- 세션 종료 + 통합 노트 -->
                <div v-if="liveSessionData.status === 'ENDED'" class="session-ended-notice">
                    <p v-if="!liveNote">📋 수업이 종료되었습니다. 통합 노트를 생성하고 있습니다...</p>
                    <div v-else-if="liveNote.status === 'PENDING'" class="note-loading">
                        <p>📝 AI가 통합 노트를 작성하고 있습니다... 잠시만 기다려주세요.</p>
                    </div>
                    <div v-else-if="liveNote.status === 'DONE'" class="note-content">
                        <h3>📚 통합 노트</h3>
                        <div class="note-stats" v-if="liveNote.stats">
                            <span>⏱ {{ liveNote.stats.duration_minutes }}분</span>
                            <span>👥 {{ liveNote.stats.total_participants }}명</span>
                            <span>📊 이해도 {{ liveNote.stats.understand_rate }}%</span>
                        </div>
                        <div class="note-body" v-html="renderMarkdown(liveNote.content)"></div>
                    </div>
                    <button class="btn btn-secondary" @click="leaveLiveSession" style="margin-top:16px;">나가기</button>
                </div>
            </div>

            <!-- 이해도 펄스 플로팅 버튼 (LIVE일 때만) -->
            <div v-if="liveSessionData.status === 'LIVE'" class="pulse-floating">
                <button class="pulse-btn understand" :class="{ active: myPulse === 'UNDERSTAND' }" @click="sendPulse('UNDERSTAND')">
                    ✅ 이해했어요
                </button>
                <button class="pulse-btn confused" :class="{ active: myPulse === 'CONFUSED' }" @click="sendPulse('CONFUSED')">
                    ❓ 잘 모르겠어요
                </button>
            </div>

            <!-- 퀴즈 팝업 모달 -->
            <div v-if="pendingQuiz" class="quiz-modal-overlay">
                <div class="quiz-modal">
                    <h3>📝 체크포인트 퀴즈!</h3>
                    <p class="quiz-question">{{ pendingQuiz.question_text }}</p>
                    <div class="quiz-options">
                        <button v-for="(opt, idx) in pendingQuiz.options" :key="idx"
                            class="quiz-option-btn"
                            :disabled="quizAnswering"
                            @click="answerLiveQuiz(pendingQuiz.id, opt)">
                            {{ opt }}
                        </button>
                    </div>
                </div>
            </div>

            <!-- 퀴즈 결과 표시 -->
            <div v-if="quizResult" class="quiz-modal-overlay">
                <div class="quiz-modal result">
                    <h3>{{ quizResult.is_correct ? '🎉 정답!' : '😅 오답...' }}</h3>
                    <p><strong>내 답:</strong> {{ quizResult.your_answer }}</p>
                    <p><strong>정답:</strong> {{ quizResult.correct_answer }}</p>
                    <p v-if="quizResult.explanation" class="quiz-explanation">💡 {{ quizResult.explanation }}</p>
                    <button class="btn btn-primary" @click="dismissQuizResult">확인</button>
                </div>
            </div>

            <button v-if="liveSessionData.status !== 'ENDED'" class="btn btn-secondary" style="margin-top:20px;" @click="leaveLiveSession">
                ← 나가기
            </button>
        </div>

        <!-- [NEW] Lecture List View -->
        <div v-if="mode === 'lecture'" class="lecture-mode-grid">
             <div class="glass-panel session-list-panel">
                <div class="lecture-info-header">
                <h2>🏫 {{ currentClassTitle || '수업 목록' }}</h2>
                <div class="header-actions" style="display:flex; gap:10px;">
                    <button class="btn btn-primary small" @click="startNewClassSession">
                        <MonitorPlay size="14" style="margin-right:4px;"/> 새 수업 시작
                    </button>
                    <button class="btn btn-control secondary small" @click="router.push('/dashboard')">나가기</button>
                </div>
            </div>
            
            <div class="session-list-wrapper">
                <!-- [NEW] Dynamic Re-routing Alert -->
                <div v-if="recoveryStatus === 'critical' || recoveryStatus === 'warning'" class="recovery-banner" :class="recoveryStatus">
                    <div class="banner-content">
                        <h3>{{ recoveryRecommendation?.title }}</h3>
                        <p>{{ recoveryRecommendation?.message }}</p>
                    </div>
                    <button class="btn-recovery" @click="executeRecoveryPlan">
                        {{ recoveryRecommendation?.action }} →
                    </button>
                </div>

                <!-- Missed Sessions Section -->
                <div v-if="missedSessions.length > 0" class="missed-section">
                    <h3 style="color: #ff9f0a; font-size: 16px; margin-bottom: 10px;">🚨 놓친 수업 (보충 학습)</h3>
                    <div v-for="missed in missedSessions" :key="missed.date" 
                         class="session-card-row glass-panel missed-card"
                         @click="openSharedSession(missed)">
                        <div class="card-left">
                            <div class="status-badge missed">MISSING</div>
                            <div class="card-text">
                                <h3>{{ missed.title }}</h3>
                                <span class="date">{{ missed.peer_count }}명의 동료가 수강함</span>
                            </div>
                        </div>
                         <div class="card-right">
                            <span class="action-text">따라잡기 →</span>
                        </div>
                    </div>
                </div>

                <!-- Regular Sessions -->
                <div v-if="sessions.length === 0 && missedSessions.length === 0" class="empty-state-large">
                    아직 수강한 기록이 없습니다.<br>
                    '새 수업 시작' 버튼을 눌러보세요!
                </div>
                
                <div v-for="session in sessions" :key="session.id" 
                     class="session-card-row"
                     @click="openSessionReview(session.id)">
                    <div class="card-left">
                        <div class="status-badge" :class="{done: session.is_completed}">
                            {{ session.is_completed ? 'COMPLETED' : 'ONGOING' }}
                        </div>
                        <div class="card-text">
                            <h3>{{ session.title }}</h3>
                            <span class="date">{{ formatTime(session.created_at) }}</span>
                        </div>
                    </div>
                    <div class="card-right">
                        <span class="action-text">복습하기 →</span>
                    </div>
                </div>
            </div>
            </div> <!-- End session-list-panel -->

            <div class="checklist-column">
                 <ChecklistPanel :lectureId="currentLectureId" />
            </div>
        </div> <!-- End lecture-mode-grid -->

        <!-- 2. Actual Learning Interface -->
        <div v-if="mode" class="container" :class="{'layout-vertical': mode === 'youtube', 'layout-split': mode === 'offline' || mode === 'universal'}">
            
            <!-- [FIX] Review Header (Youtube Mode) - 상태별 분기 추가 -->
            <header v-if="mode === 'youtube'" class="review-header glass-panel">
                 <div class="header-left">
                     <div class="status-badge header-badge" :class="{done: isCompletedSession, active: isRecording}">
                        {{ isCompletedSession ? '✅ 학습 완료 (복습 모드)' : (isRecording ? '🔴 AI 기록 중' : 'Ready (학습 준비)') }}
                     </div>
                     <span class="session-id-text">🔄 세션 연결됨 (ID: {{sessionId}})</span>
                 </div>
                 
                 <div class="header-actions" style="display:flex; gap:8px;">
                     <!-- 1. 학습 진행 중 (녹음 제어) -->
                     <template v-if="!isCompletedSession">
                         <button class="btn btn-control" :class="{'btn-danger': isRecording}" style="height:36px; font-size:13px;" @click="isRecording ? stopRecording() : startRecording()">
                             <component :is="isRecording ? Square : Mic" size="14" style="margin-right:4px;" /> 
                             {{ isRecording ? '기록 중지' : '학습 시작' }}
                         </button>
                         <button class="btn btn-control secondary" style="height:36px; font-size:13px;" @click="endSession">
                             학습 완료
                         </button>
                     </template>

                     <!-- 2. 학습 완료 (복습/퀴즈) -->
                     <template v-else>
                         <button class="btn btn-primary" style="height:36px; font-size:13px;" @click="loadQuiz">
                             ✍️ 퀴즈 풀기
                         </button>
                         <button class="btn btn-control secondary" style="height:36px; font-size:13px;" @click="startNewSession">
                             <Plus size="14" style="margin-right:4px;" /> 새 학습
                         </button>
                     </template>
                     
                     <button class="btn btn-control secondary" style="height:36px; font-size:13px;" @click="router.push('/dashboard')">나가기</button>
                 </div>
            </header>

            <!-- A. Youtube Player (New Vertical Layout) -->
            <section v-if="mode === 'youtube'" class="video-section">
                <!-- Use youtubeEmbedUrl -->
                <iframe :src="youtubeEmbedUrl" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>
            </section>
            
            <!-- B. Offline / Universal Header (Legacy) -->
            <section v-if="mode === 'offline' || mode === 'universal'" class="offline-header glass-panel">
                 <div class="header-content">
                    <div class="status-indicator">
                        <div class="pulse-dot" :class="{ active: isRecording, completed: isCompletedSession }"></div>
                        <div>
                            <h2 v-if="isCompletedSession">✅ 학습 완료 (복습 모드)</h2>
                            <h2 v-else>
                                <span v-if="currentClassTitle" style="display:block; font-size:14px; color:var(--color-primary); margin-bottom:4px;">
                                    🏫 {{ currentClassTitle }}
                                </span>
                                {{ isRecording ? '녹음 중 - AI 기록 중' : '수업 준비 완료' }}
                            </h2>
                            <p v-if="sessionId" style="font-size:12px; color: var(--color-accent); margin-top:4px;">🔄 세션 연결됨 (ID: {{sessionId}})</p>
                        </div>
                    </div>
                    <div class="controls inline">
                        <template v-if="!isCompletedSession">
                            <button class="btn btn-control" @click="isRecording ? stopRecording() : startRecording()">
                                <component :is="isRecording ? Square : Mic" /> {{ isRecording ? '종료' : '시작' }}
                            </button>
                            <button class="btn btn-control" @click="startVideoLecture">
                                <MonitorPlay size="18" /> 영상강의시작
                            </button>
                            <button class="btn btn-control secondary" @click="endSession">완료</button>
                            <button class="btn btn-control secondary" @click="startNewSession" title="새로운 학습 시작">
                                <Plus size="18" />
                            </button>
                        </template>
                        <template v-else>
                            <button class="btn btn-primary" @click="loadQuiz" style="margin-right: 8px;">
                                ✍️ 퀴즈 풀기
                            </button>
                            <button class="btn btn-control secondary" @click="startNewSession" style="margin-right: 8px;">
                                <Plus size="18" style="margin-right:4px;"/> 새 학습
                            </button>
                            <button class="btn btn-control secondary" @click="router.push('/dashboard')">나가기</button>
                        </template>
                    </div>
                 </div>
            </section>

            <!-- C. Hybrid Embedded Video (Offline Mode) -->
            <section v-if="(mode === 'offline' || mode === 'universal') && youtubeEmbedUrl" class="embedded-video-area">
                <div class="video-container" style="border-radius: 8px;">
                    <iframe :src="youtubeEmbedUrl" frameborder="0" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>
                </div>
            </section>

            <!-- D. Common Note Area (Vertical for Youtube, Split for others) -->
            <section class="note-area glass-panel" :class="{'full-width': mode === 'youtube', 'full-height': mode !== 'youtube'}">
                <div class="tab-header">
                    <span :class="{active: activeTab==='stt'}" @click="activeTab='stt'">실시간 자막</span>
                    <span :class="{active: activeTab==='summary'}" @click="activeTab='summary'">AI 학습노트</span>
                </div>
                
                <!-- 1. STT View -->
                <div v-show="activeTab === 'stt'" class="stt-container" ref="logsContainer">
                    <div v-if="sttLogs.length === 0" class="empty-state"><p>AI가 내용을 받아적습니다.</p></div>
                    <div v-for="log in sttLogs" :key="log.id" class="stt-bubble">
                        <span class="time">{{ log.timestamp }}</span>
                        <p>{{ log.text_chunk }}</p>
                    </div>
                    <!-- Processing Indicator -->
                    <div v-if="isProcessingAudio" class="stt-bubble processing">
                        <span class="typing-dots">AI가 내용을 듣고 있습니다...</span>
                    </div>
                </div>

                <!-- 2. AI Summary View -->
                <div v-show="activeTab === 'summary'" class="summary-container">
                    <div v-if="!sessionSummary" class="empty-state-summary">
                        <Bot class="icon-bot" /> 
                        <p>아직 요약된 내용이 없거나,<br>생성되지 않았습니다.</p>
                        <button class="btn btn-accent action-btn" @click="generateSummary" :disabled="isGeneratingSummary">
                            <RefreshCw v-if="isGeneratingSummary" class="spin-anim" />
                            <span v-else>AI 요약 생성하기</span>
                        </button>
                    </div>
                    <div v-else class="summary-content">
                        <div class="summary-actions">
                            <button class="btn-text small" @click="generateSummary" :disabled="isGeneratingSummary">
                                <RefreshCw size="14" :class="{'spin-anim': isGeneratingSummary}" /> 요약 다시 생성
                            </button>
                            <button class="btn-text small" @click="exportPdf" title="학습 노트 다운로드">
                                <Download size="14" /> PDF 내보내기
                            </button>
                            <button class="btn-text small" @click="toggleNoteEditor" :class="{ active: showNoteEditor }">
                                <PenLine size="14" /> 메모 {{ showNoteEditor ? '닫기' : '추가' }}
                            </button>
                        </div>
                        <div class="markdown-text">{{ sessionSummary }}</div>
                        
                        <!-- Note Editor -->
                        <div v-if="showNoteEditor" class="note-editor">
                            <h4>📌 나의 메모</h4>
                            <textarea 
                                v-model="noteContent" 
                                placeholder="이 수업에 대한 메모를 남겨보세요... (코드, 의문점, 추가 정리 등)"
                                rows="5"
                            ></textarea>
                            <button class="btn btn-accent" @click="saveNote" :disabled="isSavingNote || !noteContent.trim()">
                                {{ isSavingNote ? '저장 중...' : '💾 메모 저장' }}
                            </button>
                        </div>
                    </div>
                </div>
            </section>

        </div>

        <!-- 3. Quiz Overlays -->
        <div v-if="isGeneratingQuiz" class="quiz-overlay">
            <div class="glass-panel" style="padding:40px; text-align:center;">
                <p>퀴즈 생성 중...</p>
                <div class="spinner" style="margin:20px auto;"></div>
            </div>
        </div>
        
        <div v-if="showQuiz" class="quiz-overlay">
             <div class="glass-panel quiz-card">
                <div v-if="quizResult" class="result-view">
                    <h2 class="text-headline">{{ quizResult.score >= 80 ? '🎉 통과!' : '💪 재도전!' }}</h2>
                    <div class="score-display"><span class="score">{{quizResult.score}}</span> / 100</div>
                    
                    <!-- [NEW] Review Note -->
                    <div v-if="quizResult.review_note" class="review-note-section">
                        <h3>💡 AI 맞춤 해설 (오답 노트)</h3>
                        <div class="markdown-text">{{ quizResult.review_note }}</div>
                    </div>

                    <button class="btn btn-primary" @click="router.push('/dashboard')">나가기</button>
                </div>
                <div v-else-if="quizData">
                    <div class="quiz-header"><h2>오늘의 퀴즈</h2></div>
                    <div class="questions-list">
                        <div v-for="(q, idx) in quizData.questions" :key="q.id" class="question-item">
                            <p class="q-title">Q{{idx+1}}. {{q.question_text}}</p>
                            <div class="options-group">
                                <label v-for="opt in q.options" :key="opt" class="option-label">
                                    <input type="radio" :name="q.id" :value="opt" v-model="quizAnswers[q.id]"> {{opt}}
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="quiz-footer">
                        <button 
                            class="btn btn-primary btn-full" 
                            @click="submitQuiz" 
                            :disabled="isSubmittingQuiz"
                        >
                            <span v-if="isSubmittingQuiz" class="submit-spinner-wrap">
                                <span class="spinner-small"></span>
                                AI가 채점 중...
                            </span>
                            <span v-else>제출</span>
                        </button>
                        <button class="btn btn-secondary btn-full" style="margin-top:10px" @click="showQuiz=false" :disabled="isSubmittingQuiz">닫기</button>
                    </div>
                </div>
             </div>
        </div>

    <!-- [NEW] Recovery Plan Modal -->
    <div v-if="showRecoveryModal" class="modal-overlay" @click.self="showRecoveryModal = false">
        <div class="modal-card wide-modal">
            <h2>🚀 {{ recoveryRecommendation?.title || '압축 복구 플랜' }}</h2>
            
            <div class="modal-body-split" style="text-align:left; display:block;">
                <div v-if="isGeneratingRecovery" class="loading-state" style="padding:40px;">
                    <div class="spinner"></div>
                    <p style="margin-top:20px; color:#aaa;">AI가 놓친 핵심 개념을 요약하고 있습니다...</p>
                </div>
                
                <div v-else class="markdown-text" style="max-height: 500px; overflow-y:auto; padding-right:10px;">
                    {{ recoveryPlanContent }}
                </div>
            </div>
            
            <div class="modal-footer" style="margin-top:20px; display:flex; justify-content:flex-end; gap:10px;">
                <button class="btn btn-primary" @click="showRecoveryModal = false">확인 (학습 완료)</button>
                <button class="btn btn-text" @click="showRecoveryModal = false">닫기</button>
            </div>
        </div>
    </div>

    <!-- Join Class Modal (Copied from Dashboard) -->
    <div v-if="showJoinModal" class="modal-overlay" @click.self="closeJoinModal">
        <div class="modal-card wide-modal">
            <h2>클래스 참여</h2>
            
            <div class="modal-body-split">
                <!-- Left: Verification Code -->
                <div class="input-section">
                    <p class="sub-text">강사님에게 전달받은<br>6자리 코드를 입력해주세요.</p>
                    <input type="text" v-model="joinCode" maxlength="6" class="code-input" placeholder="CODE" @keyup.enter="joinClass" />
                    <button class="btn btn-primary full-width" @click="joinClass">입장하기</button>
                    <button class="btn btn-text full-width" @click="closeJoinModal" style="margin-top:10px">취소</button>
                </div>

                <!-- Right Separator -->
                <div class="list-section">
                    <h3>내 수강 목록 (My Courses)</h3>
                    <div class="lecture-list">
                        <div v-for="lec in myLectures" :key="lec.id" class="lecture-item" :class="{'selected': selectedLectureId === lec.id}" @click="selectLecture(lec)">
                            <div class="lec-info">
                                <span class="lec-title">{{ lec.title }}</span>
                                <span class="lec-instructor">{{ lec.instructor_name }} 강사님</span>
                            </div>
                            <div class="badge-enrolled">학습 하기 →</div>
                        </div>
                        <div v-if="myLectures.length === 0" class="empty-list">
                            아직 수강 중인 클래스가 없습니다.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- [NEW] RAG Chat Floating Button & Window -->
    <div v-if="mode" class="chat-wrapper">
        <!-- Floating Button -->
        <div class="chat-floating-btn" @click="toggleChat">
            <Bot size="32" v-if="!isChatOpen" />
            <span v-else style="font-size:24px; font-weight:bold;">×</span>
        </div>
        
        <!-- Chat Window -->
        <div v-if="isChatOpen" class="chat-window glass-panel">
            <div class="chat-header">
                <h3><Bot size="18" /> AI 튜터</h3>
                <span class="status-dot green"></span>
            </div>
            
            <div class="chat-body" ref="chatScrollRef">
                <div v-for="(msg, idx) in chatMessages" :key="idx" 
                     class="chat-bubble" :class="msg.role">
                    {{ msg.text }}
                </div>
                <!-- Loading Indicator -->
                <div v-if="isChatLoading" class="chat-bubble ai">
                    <span class="typing-dots">...생각 중...</span>
                </div>
            </div>
            
            <div class="chat-footer">
                <input type="text" v-model="chatInput" 
                       placeholder="궁금한 내용을 물어보세요..." 
                       @keyup.enter="sendChatMessage" 
                       :disabled="isChatLoading" />
                <button @click="sendChatMessage" :disabled="isChatLoading || !chatInput.trim()">
                    전송
                </button>
            </div>
        </div>
    </div>

    </template> <!-- END MAIN CONTENT -->

    <!-- [DEBUG PANEL] -->
    <div v-if="mode" class="debug-panel">
        <div><strong>STT Debugger</strong></div>
        <div>Last Chunk: {{ debugLastChunkSize }} bytes</div>
        <div>Last Status: {{ debugLastStatus }}</div>
        <div>Last Response: {{ debugLastResponse }}</div>
        <div>Recorder State: {{ isRecording ? 'ON' : 'OFF' }}</div>
    </div>

  </div>
</template>

<style scoped lang="scss">
/* Existing clean styles preserved */
.learning-view {
    padding-top: calc(var(--header-height) + 10px);
    min-height: 100vh; height: auto; overflow-y: auto; /* Allow full page scroll */
    padding-left: 20px; padding-right: 20px;
    padding-bottom: 50px;
}
.loading-overlay {
    position: fixed; top:0; left:0; width:100%; height:100%;
    background: rgba(0,0,0,0.9); z-index: 5000;
    display: flex; align-items: center; justify-content: center;
}
.spinner {
    width: 40px; height: 40px; border: 4px solid #333;
    border-top-color: var(--color-accent); border-radius: 50%;
    animation: spin 1s linear infinite; margin: 0 auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Reused Layouts */
.layout-grid {
    display: grid; grid-template-columns: 75% 25%; gap: 24px;
    min-height: calc(100vh - 80px); height: auto; padding-bottom: 20px;
}
.layout-split {
    display: flex; flex-direction: column; gap: 24px;
    min-height: calc(100vh - 100px); height: auto; max-width: 1000px; margin: 0 auto;
}
.screen-area { display: flex; flex-direction: column; height: 100%; }
.video-container {
    flex: 1; background: black; border-radius: 12px; overflow: hidden;
    position: relative; display: flex; align-items: center; justify-content: center;
    iframe { width: 100%; height: 100%; border: none; }
}
.note-area {
    background: rgba(28,28,30,0.75); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px;
    display: flex; flex-direction: column; padding: 24px;
    min-height: 600px; height: auto; /* Increased height > 500px */
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
    .logs-container {
        flex: 1; min-height: 0; 
        overflow-y: auto; padding: 10px;
        background: #000; border-radius: 8px;
        scroll-behavior: smooth;
        margin-bottom: 20px; /* 공간 확보 */
        display: flex; flex-direction: column;
        
        /* 스크롤바 커스터마이징 */
        &::-webkit-scrollbar { width: 8px; }
        &::-webkit-scrollbar-thumb { background: #444; border-radius: 4px; }
        &::-webkit-scrollbar-track { background: #222; }
    }
    
    .stt-log {
        margin-bottom: 12px; font-size: 15px; line-height: 1.6; color: rgba(255,255,255,0.9);
        padding: 8px 12px; background: rgba(255,255,255,0.05); border-radius: 8px;
        border-left: 3px solid var(--color-accent);
        animation: fadeIn 0.3s ease-out;
    }
    .stt-log:last-child {
        margin-bottom: 20px; /* 마지막 아이템 여백 */
        border-color: #4CAF50; /* 최신 로그 강조 */
        background: rgba(76, 175, 80, 0.1);
    }

.embedded-video-area {
    flex: 0 0 400px; /* Fixed height for video */
    background: black;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    display: flex;
}

.offline-header { padding: 24px; flex: 0 0 auto; }
.header-content { display: flex; justify-content: space-between; align-items: center; }
.controls { margin-top: 16px; display: flex; gap: 12px; justify-content: center; }
.controls.inline { margin-top: 0; }
.btn-control {
    background: white; color: black; height: 48px; border-radius: 24px;
    display: flex; align-items: center; padding: 0 24px; gap: 8px; border: none; cursor: pointer;
    &.secondary { background: rgba(255,255,255,0.1); color: white; }
    &:hover { transform: scale(1.05); }
}

/* Recording Indicator */
.status-indicator { display: flex; align-items: center; }
.pulse-dot {
    width: 12px; height: 12px; border-radius: 50%; background: #666;
    margin-right: 12px;
    
    &.active { background: #ff3b30; box-shadow: 0 0 10px rgba(255,59,48,0.5); animation: pulse 1.5s infinite; }
    &.completed { background: #abffae; box-shadow: 0 0 10px rgba(76, 175, 80, 0.5); animation: none; }
}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

/* Mode Overlay — 네비바(48px) 아래부터 시작하여 헤더 클릭 가능 유지 */
.mode-overlay {
    position: fixed; top: var(--header-height, 48px); left: 0;
    width: 100vw; height: calc(100vh - var(--header-height, 48px));
    background: rgba(0,0,0,0.85); z-index: 900;
    display: flex; align-items: center; justify-content: center;
}
.mode-card { width: 620px; padding: 40px; text-align: center; }
.mode-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 32px;
}
.mode-item {
    padding: 24px 16px; background: rgba(255,255,255,0.05);
    border-radius: 16px; cursor: pointer; transition: all 0.2s;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 12px;
    
    .icon { color: #ccc; transition: color 0.2s; }
    h3 { font-size: 16px; font-weight: 600; margin: 0; }
    .desc { font-size: 12px; color: #888; margin: 0; }
    
    &:hover { 
        background: rgba(255,255,255,0.1); transform: translateY(-3px); 
        .icon { color: white; }
    }
    
    &.special {
        background: rgba(79, 172, 254, 0.1); border: 1px solid rgba(79, 172, 254, 0.3);
        .icon { color: #4facfe; }
        &:hover { background: rgba(79, 172, 254, 0.2); border-color: #4facfe; }
    }
}

/* Resume Card Styles */
.resume-section { margin-top: 24px; margin-bottom: 24px; cursor: pointer; }
.resume-card {
    display: flex; align-items: center; gap: 16px; padding: 20px;
    background: rgba(79, 172, 254, 0.1); border: 1px solid rgba(79, 172, 254, 0.3);
    transition: all 0.2s;
    
    &:hover { background: rgba(79, 172, 254, 0.2); transform: scale(1.02); }
    
    .icon-box { color: #4facfe; }
    .info { flex: 1; text-align: left; h3 { font-size: 16px; font-weight: 600; margin-bottom: 4px; } p { font-size: 13px; color: #ccc; } }
    .arrow { color: #4facfe; font-weight: bold; }
}
.input-group { display: flex; gap: 12px; margin-top: 24px; input { flex: 1; padding: 12px; background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); color: white; border-radius: 8px;} }
.back-link { cursor: pointer; color: #888; text-align: left; margin-bottom: 10px; &:hover { color: white; } }

/* Quiz */
.quiz-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.9); z-index: 4000; display: flex; align-items: center; justify-content: center;
}
.quiz-card { 
    width: 600px; max-height: 90vh; overflow-y: auto; 
    background: rgba(28, 28, 30, 0.75); backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
    border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 20px;
    padding: 0; 
}
.quiz-header { text-align: center; padding: 20px; }
.questions-list { padding: 20px; display: flex; flex-direction: column; gap: 30px; }
.question-item { .q-title { font-weight: bold; margin-bottom: 10px; } }
.options-group { display: flex; flex-direction: column; gap: 8px; }
.quiz-footer { padding: 20px; }
.quiz-footer button:disabled { opacity: 0.6; cursor: not-allowed; }
.submit-spinner-wrap {
    display: inline-flex; align-items: center; gap: 8px;
}
.spinner-small {
    width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white; border-radius: 50%;
    animation: spin 0.8s linear infinite; display: inline-block;
}

/* Review Note */
.review-note-section {
    background: rgba(255, 149, 0, 0.1); 
    border: 1px solid rgba(255, 149, 0, 0.3);
    border-radius: 12px;
    padding: 20px;
    margin: 20px 0;
    text-align: left;
}
.review-note-section h3 {
    margin-top: 0;
    color: #ff9f0a;
    font-size: 16px;
    margin-bottom: 12px;
}
.btn-full { width: 100%; height: 48px; }
.result-view { text-align: center; padding: 40px; .score-display { font-size: 60px; font-weight: bold; margin: 20px 0; color: var(--color-accent); } }

/* Join Class Link */
.join-class-link { margin-top: 30px; color: #888; font-size: 14px; }
.join-class-link span { cursor: pointer; text-decoration: underline; transition: color 0.2s; }
.join-class-link span:hover { color: var(--color-accent); }

/* Modal Styles */
/* .modal-overlay is already defined for quiz, sharing same style */
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.8); z-index: 5000; /* Higher than mode-overlay(3000) */
    display: flex; align-items: center; justify-content: center;
}
.modal-card.wide-modal {
    background: rgba(28, 28, 30, 0.75); backdrop-filter: blur(30px); -webkit-backdrop-filter: blur(30px);
    padding: 32px; border-radius: 24px; 
    width: 800px; max-width: 95vw;
    text-align: center; border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 24px 64px rgba(0,0,0,0.4);
    z-index: 5001; /* Ensure content is on top */
}
.modal-body-split {
    display: flex; gap: 30px; margin-top: 30px; text-align: left;
}
.input-section { flex: 1; padding-right: 20px; display: flex; flex-direction: column; justify-content: center; }
.list-section { flex: 1.2; border-left: 1px solid #333; padding-left: 30px; max-height: 400px; overflow-y: auto; color: white; }

.sub-text { color: #888; margin-bottom: 24px; font-size: 14px; text-align: center; }
.code-input {
    width: 100%; padding: 16px; font-size: 24px; letter-spacing: 4px; text-align: center;
    background: #000; border: 1px solid #444; border-radius: 8px; color: var(--color-accent);
    margin-bottom: 24px; text-transform: uppercase;
    &:focus { border-color: var(--color-accent); outline: none; }
}
.full-width { width: 100%; }

/* Hybrid Tabs */
.tab-header {
    display: flex; gap: 20px; border-bottom: 1px solid #333; padding: 0 20px; margin-bottom: 10px;
}
.tab-header span {
    padding: 15px 5px; cursor: pointer; color: #888; font-weight: 500; font-size: 14px;
    border-bottom: 2px solid transparent; transition: all 0.2s;
}
.tab-header span:hover { color: white; }
.tab-header span.active { color: var(--color-accent); border-bottom-color: var(--color-accent); }

/* Summary View */
.summary-container {
    padding: 20px; min-height: 550px; /* Increased height */ color: #ddd; line-height: 1.6;
}
.empty-state-summary {
    height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: #666; text-align: center; gap: 16px;
}
.icon-bot { color: #444; width: 48px; height: 48px; }

.summary-actions {
    display: flex; justify-content: flex-end; gap: 6px; margin-bottom: 16px; flex-wrap: wrap;
}
.btn-text.active { color: #4facfe; background: rgba(79,172,254,0.1); border-radius: 6px; }

.note-editor {
    margin-top: 20px; padding: 16px; background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
}
.note-editor h4 { margin: 0 0 10px; font-size: 15px; color: #ddd; }
.note-editor textarea {
    width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px; color: #e0e0e0; padding: 12px; font-size: 14px;
    resize: vertical; min-height: 100px; outline: none; font-family: inherit;
}
.note-editor textarea:focus { border-color: #4facfe; }
.note-editor .btn { margin-top: 10px; }

.markdown-text {
    white-space: pre-wrap; font-size: 15px; color: #e0e0e0;
}

/* Animations */
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spin-anim { animation: spin 1s linear infinite; }
.btn-accent:disabled { opacity: 0.7; cursor: not-allowed; }
.lecture-item {
    background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    padding: 16px; border-radius: 12px; cursor: pointer;
    display: flex; justify-content: space-between; align-items: center;
    transition: all 0.2s;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    
    &:hover { background: rgba(255, 255, 255, 0.08); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.2); }
    &.selected { border-color: var(--color-accent); background: rgba(79, 172, 254, 0.15); }
}
.lec-info { display: flex; flex-direction: column; gap: 4px; }
.lec-title { color: white; font-weight: bold; font-size: 15px; }
.lec-instructor { color: #888; font-size: 13px; }
.action-arrow { color: var(--color-accent); font-size: 18px; opacity: 0; transition: opacity 0.2s; }
.lecture-item:hover .action-arrow { opacity: 1; }
.empty-list { color: #666; text-align: center; padding: 20px; font-size: 14px; }

/* Enrolled Badge */
.badge-enrolled {
    font-size: 11px; font-weight: bold; color: #4facfe;
    background: rgba(79, 172, 254, 0.15); padding: 4px 8px; border-radius: 4px;
    border: 1px solid rgba(79, 172, 254, 0.3);
}
/* Lecture Mode Styles */
.lecture-mode-grid {
    display: grid; grid-template-columns: 2fr 1fr; gap: 24px;
    max-width: 1200px; margin: 40px auto; padding: 0 30px;
    align-items: start;
}
.session-list-panel {
    padding: 30px; min-height: 500px; border-radius: 16px;
}
.checklist-column {
    position: sticky; top: 100px; /* Sticky sidebar */
}

@media (max-width: 900px) {
    .lecture-mode-grid { grid-template-columns: 1fr; }
    .checklist-column { position: static; order: -1; margin-bottom: 20px; }
}

/* Legacy container removed */
.lecture-view-container-legacy {
    max-width: 800px; margin: 40px auto; padding: 30px; min-height: 500px;
}
.lecture-info-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 15px;
    h2 { font-size: 24px; color: var(--color-primary); }
}
/* Session Wrapper */
.session-list-wrapper { display: flex; flex-direction: column; gap: 15px; }

/* Dynamic Re-routing Banner */
.recovery-banner {
    padding: 20px; border-radius: 12px;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px;
    animation: slideDown 0.5s ease;
}
.recovery-banner.critical {
    background: rgba(255, 59, 48, 0.15);
    border: 1px solid rgba(255, 59, 48, 0.4);
}
.recovery-banner.warning {
    background: rgba(255, 149, 0, 0.15);
    border: 1px solid rgba(255, 149, 0, 0.4);
}

.banner-content h3 { margin: 0 0 5px 0; font-size: 16px; font-weight: bold; }
.banner-content p { margin: 0; font-size: 14px; opacity: 0.8; }
.recovery-banner.critical h3 { color: #ff3b30; }
.recovery-banner.critical p { color: #ffcccc; }
.recovery-banner.warning h3 { color: #ff9f0a; }
.recovery-banner.warning p { color: #ffe0b2; }

.btn-recovery {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white; padding: 10px 20px; border-radius: 8px;
    cursor: pointer; transition: all 0.2s; font-weight: bold;
}
.recovery-banner.critical .btn-recovery:hover { background: #ff3b30; border-color: #ff3b30; }
.recovery-banner.warning .btn-recovery:hover { background: #ff9f0a; border-color: #ff9f0a; }

@keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

.session-card-row {
    display: flex; justify-content: space-between; align-items: center;
    background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    padding: 20px; border-radius: 16px; cursor: pointer; transition: all 0.2s;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);

    &:hover { 
        background: rgba(255, 255, 255, 0.08); 
        transform: translateY(-2px); 
        border-color: var(--color-accent); 
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    }
}
.card-left { display: flex; align-items: center; gap: 15px; }
.status-badge {
    padding: 4px 10px; border-radius: 20px; font-size: 12px; background: #444; color: #aaa;
    &.done { background: rgba(79, 172, 254, 0.2); color: var(--color-accent); border: 1px solid var(--color-accent); }
    &.missed { background: rgba(255, 159, 10, 0.2); color: #ff9f0a; border: 1px solid #ff9f0a; }
}
.missed-card {
    border: 1px dashed rgba(255, 159, 10, 0.5);
    &:hover { border-color: #ff9f0a; background: rgba(255, 159, 10, 0.1); }
}
.card-text h3 { margin: 0; font-size: 18px; color: white; }
.card-text .date { font-size: 13px; color: #888; }
.card-right .action-text { color: var(--color-accent); font-size: 14px; font-weight: 500; }
.empty-state-large { text-align: center; color: #666; font-size: 18px; padding: 50px; }

/* Layout Vertical (New Review Mode) */
.layout-vertical {
    display: flex; flex-direction: column; gap: 16px;
    min-height: calc(100vh - 80px); height: auto;
    max-width: 1200px; margin: 0 auto;
    padding-bottom: 50px;
}

.review-header {
    flex: 0 0 auto;
    display: flex; justify-content: space-between; align-items: center;
    padding: 16px 24px;
    background: rgba(28, 28, 30, 0.65); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.header-left { display: flex; align-items: center; gap: 16px; }
.session-id-text { color: var(--color-accent); font-size: 13px; }

.video-section {
    flex: 0 0 auto;
    width: 100%;
    aspect-ratio: 16 / 9;
    max-height: 55vh; /* Limit height to allow notes to be visible */
    background: black;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.video-section iframe { width: 100%; height: 100%; border:none; }

.note-area.full-width {
    flex: 1; /* Take remaining space */
    width: 100%;
}

/* Override Status Badge for Header */
.status-badge.header-badge {
    font-size: 15px; padding: 6px 12px;
    background: rgba(76, 175, 80, 0.15); color: #4CAF50; border: 1px solid rgba(76, 175, 80, 0.3);
    
    &.active {
        background: rgba(255, 59, 48, 0.15); color: #ff3b30; border-color: rgba(255, 59, 48, 0.3);
        animation: pulse 1.5s infinite;
    }
}

.btn-danger {
    background: rgba(255, 59, 48, 0.2) !important; color: #ff3b30 !important; border: 1px solid rgba(255, 59, 48, 0.5) !important;
}

.btn-text.highlight {
    color: var(--color-accent); font-weight: bold; border: 1px solid var(--color-accent);
    padding: 8px 16px; border-radius: 8px; background: rgba(79, 172, 254, 0.1);
    transition: all 0.2s; display: inline-block;
}
.session-card-row:hover .btn-text.highlight {
    background: var(--color-accent); color: white;
}

/* Chat CSS - Premium Glassmorphism */
.chat-floating-btn {
    position: fixed; bottom: 30px; right: 30px;
    width: 64px; height: 64px; border-radius: 50%;
    background: linear-gradient(135deg, #00C6FF, #0072FF);
    box-shadow: 0 8px 32px rgba(0, 114, 255, 0.4);
    display: flex; justify-content: center; align-items: center;
    cursor: pointer; z-index: 1000;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    color: white; border: 2px solid rgba(255,255,255,0.1);
}
.chat-floating-btn:hover { 
    transform: scale(1.1) rotate(5deg); 
    box-shadow: 0 12px 40px rgba(0, 114, 255, 0.6);
}

.chat-window {
    position: fixed; bottom: 110px; right: 30px;
    width: 380px; height: 600px;
    background: rgba(28, 28, 30, 0.65); /* More transparent */
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex; flex-direction: column;
    box-shadow: 0 20px 50px rgba(0,0,0,0.5);
    z-index: 1000; overflow: hidden;
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideUp {
    from { opacity: 0; transform: translateY(20px) scale(0.95); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

.chat-header {
    background: rgba(255, 255, 255, 0.05); 
    padding: 18px 20px; 
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    display: flex; justify-content: space-between; align-items: center;
}
.chat-header h3 { 
    margin: 0; font-size: 16px; font-weight: 600; 
    color: white; display: flex; align-items: center; gap: 10px; 
    letter-spacing: -0.5px;
}
.status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #4CAF50; box-shadow: 0 0 10px #4CAF50;
}

.chat-body { 
    flex: 1; padding: 20px; 
    overflow-y: auto; 
    display: flex; flex-direction: column; gap: 14px; 
    background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.2) 100%);
}

.chat-bubble {
    max-width: 85%; padding: 12px 16px; border-radius: 16px; 
    font-size: 14px; line-height: 1.5; color: rgba(255,255,255,0.9);
    word-break: break-word; white-space: pre-wrap;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    animation: fadeIn 0.3s ease;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.chat-bubble.ai { 
    background: rgba(50, 50, 50, 0.8); 
    align-self: flex-start; 
    border-bottom-left-radius: 4px; 
    border: 1px solid rgba(255,255,255,0.05);
}
.chat-bubble.user { 
    background: linear-gradient(135deg, #0072FF, #00C6FF); 
    align-self: flex-end; 
    border-bottom-right-radius: 4px; 
    color: white; font-weight: 500;
}

.chat-footer { 
    padding: 16px; 
    border-top: 1px solid rgba(255, 255, 255, 0.05); 
    display: flex; gap: 10px; 
    background: rgba(30, 30, 32, 0.95);
}
.chat-footer input {
    flex: 1; 
    background: rgba(0,0,0,0.3); 
    border: 1px solid rgba(255,255,255,0.1); 
    color: white; padding: 12px 16px; border-radius: 12px; 
    outline: none; transition: all 0.2s; font-size: 14px;
}
.chat-footer input:focus {
    background: rgba(0,0,0,0.5); border-color: #0072FF;
}

.chat-footer button {
    background: #0072FF; color: white; border: none; padding: 0 20px;
    border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 14px;
    transition: all 0.2s;
}
.chat-footer button:hover:not(:disabled) { background: #0088FF; transform: translateY(-1px); }
.chat-footer button:disabled { opacity: 0.5; cursor: not-allowed; background: #333; }

/* Processing Indicator Styles */
.stt-bubble.processing {
    background: rgba(255, 255, 255, 0.05);
    border: 1px dashed rgba(255, 255, 255, 0.2);
    color: #888;
    align-self: center; /* Center if container is flex col */
    width: 100%;
    text-align: center;
}

.typing-dots::after {
    content: ' .';
    animation: dots 1.5s steps(5, end) infinite;
}

@keyframes dots {
    0%, 20% { content: ' .'; }
    40% { content: ' ..'; }
    60% { content: ' ...'; }
    80%, 100% { content: ''; }
}
</style>

<!-- Add debug panel styles -->
<style scoped> 
.debug-panel {
    position: fixed; bottom: 10px; left: 10px;
    background: rgba(0,0,0,0.8); color: lime;
    padding: 10px; border-radius: 8px; font-size: 11px;
    font-family: monospace; z-index: 9999;
    max-width: 400px;
}

/* ── Live Session (학습자) ── */
.live-session-view { padding: 20px 0; }
.live-info-panel { padding: 24px; margin-bottom: 20px; }
.live-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.live-header h2 { margin: 0; font-size: 20px; }
.live-badge {
    padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
}
.live-badge.LIVE { background: #fee2e2; color: #991b1b; animation: pulse-live 2s infinite; }
.live-badge.WAITING { background: #fef3c7; color: #92400e; }
.live-badge.ENDED { background: #e5e7eb; color: #6b7280; }
@keyframes pulse-live { 0%,100% { opacity:1; } 50% { opacity:0.7; } }

.session-code-small { color: #888; font-size: 13px; margin: 0; }
.session-ended-notice {
    margin-top: 16px; padding: 16px; background: #f0fdf4; border-radius: 8px;
    text-align: center;
}
.session-ended-notice p { margin: 0 0 12px; font-size: 14px; }

.pulse-floating {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 16px; z-index: 800;
}
.pulse-btn {
    padding: 16px 28px; border-radius: 50px; font-size: 16px; font-weight: 700;
    border: 2px solid transparent; cursor: pointer; transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.pulse-btn.understand {
    background: #f0fdf4; color: #166534; border-color: #22c55e;
}
.pulse-btn.understand.active {
    background: #22c55e; color: white; transform: scale(1.05);
}
.pulse-btn.confused {
    background: #fef2f2; color: #991b1b; border-color: #ef4444;
}
.pulse-btn.confused.active {
    background: #ef4444; color: white; transform: scale(1.05);
}

.mode-item.live-mode {
    background: linear-gradient(135deg, #f0fdf4, #ecfdf5) !important;
    border: 1px solid #22c55e33 !important;
}

/* ── Quiz Modal (학습자) ── */
.quiz-modal-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6); display: flex; align-items: center;
    justify-content: center; z-index: 900;
}
.quiz-modal {
    background: white; border-radius: 16px; padding: 32px;
    max-width: 480px; width: 90%; text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    animation: quiz-pop 0.3s ease-out;
}
@keyframes quiz-pop { from { transform: scale(0.8); opacity:0; } to { transform: scale(1); opacity:1; } }

.quiz-modal h3 { font-size: 22px; margin: 0 0 16px; }
.quiz-question { font-size: 15px; color: #333; margin-bottom: 20px; line-height: 1.6; }
.quiz-options { display: flex; flex-direction: column; gap: 10px; }
.quiz-option-btn {
    padding: 14px 20px; border: 2px solid #e5e7eb; border-radius: 12px;
    font-size: 14px; cursor: pointer; transition: all 0.2s;
    background: white; text-align: left;
}
.quiz-option-btn:hover { border-color: #3b82f6; background: #eff6ff; }
.quiz-option-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.quiz-modal.result h3 { font-size: 28px; }
.quiz-explanation { color: #1e40af; background: #eff6ff; padding: 12px; border-radius: 8px; font-size: 13px; margin: 12px 0; }

/* ── Live Note ── */
.note-loading { text-align: center; padding: 20px; }
.note-loading p { color: #6b7280; animation: pulse-live 2s infinite; }
.note-content h3 { margin: 0 0 12px; font-size: 18px; }
.note-stats { display: flex; gap: 16px; margin-bottom: 16px; }
.note-stats span {
    padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
    background: #f0f9ff; color: #0369a1;
}
.note-body {
    padding: 16px; background: white; border-radius: 12px; border: 1px solid #e5e7eb;
    font-size: 14px; line-height: 1.8; max-height: 600px; overflow-y: auto;
}
.note-body h2 { font-size: 18px; margin: 16px 0 8px; color: #1e293b; }
.note-body h3 { font-size: 15px; margin: 12px 0 6px; color: #334155; }
.note-body h4 { font-size: 14px; margin: 10px 0 4px; color: #475569; }
.note-body li { margin-left: 16px; }
.note-body strong { color: #1e40af; }
</style>
