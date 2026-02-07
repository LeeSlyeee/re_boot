<script setup>
import { ref, nextTick, computed, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router'; // useRoute added
import { Mic, Square, Pause, FileText, MonitorPlay, Users, Youtube, RefreshCw, Bot, Play, List, Plus } from 'lucide-vue-next'; // Play, List added
import { AudioRecorder } from '../api/audioRecorder';
import api from '../api/axios';

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

// --- Lecture Mode State ---
const currentLectureId = ref(null);
const lectureSessions = ref([]);
const showLectureSidebar = ref(false);

const fetchLectureSessions = async (lectureId) => {
    try {
        // [FIX] Correct Endpoint: sessions/lectures/{id}
        const res = await api.get(`/learning/sessions/lectures/${lectureId}/`);
        lectureSessions.value = res.data;
        showLectureSidebar.value = true;
    } catch (e) {
        console.error("Failed to fetch lecture sessions", e);
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

// Quiz State
const quizData = ref(null);
const showQuiz = ref(false);
const quizAnswers = ref({});
const quizResult = ref(null);
const isGeneratingQuiz = ref(false);

// --- Join Class Logic ---
const showJoinModal = ref(false);
const joinCode = ref('');
const availableLectures = ref([]);
const selectedLectureId = ref(null);
const currentClassTitle = ref(null); 

const fetchAvailableLectures = async () => {
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
    fetchAvailableLectures();
};
const closeJoinModal = () => {
    showJoinModal.value = false;
};

const selectLecture = (lecture) => {
    // [TEST MODE] 모든 클래스 즉시 입장 허용 (강사 부재 상황 가정)
    // 원래는 lecture.is_enrolled 확인해야 함
    if (confirm(`'${lecture.title}' 수업을 임시로 수강하시겠습니까?`)) {
        currentClassTitle.value = lecture.title;
        showJoinModal.value = false;
        
        currentLectureId.value = lecture.id;
        fetchLectureSessions(lecture.id);
        mode.value = 'lecture'; 
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
        const savedSessionId = localStorage.getItem('currentSessionId');

        if (queryLectureId) {
             console.log(`ℹ️ Opening Lecture Mode: ${queryLectureId}`);
             currentLectureId.value = queryLectureId;
             await fetchLectureSessions(queryLectureId);
             mode.value = 'lecture';
             // Don't auto-resume session unless user picks one
        } else if (savedSessionId) {
            // [CHANGE] 자동 복구 시도 (isAutoRestore=true)
            await resumeSession(true); 
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
        // 복구 실패 시 조용히 실패 처리 (삭제)
        localStorage.removeItem('currentSessionId');
        pendingSessionId.value = null;
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
    // [CHANGE] 새 모드 선택 시 기존 대기 세션 정보 파기
    if (pendingSessionId.value) {
        if(confirm("이전 학습 기록을 무시하고 새로 시작하시겠습니까?")) {
            localStorage.removeItem('currentSessionId');
            localStorage.removeItem('currentYoutubeUrl');
            localStorage.removeItem('restoredMode');
            pendingSessionId.value = null;
        } else {
            return;
        }
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
                lecture: currentLectureId.value || null, // [FIX] Link to current lecture if valid
                youtube_url: (youtubeUrl.value && !youtubeUrl.value.startsWith('http')) 
                             ? 'https://' + youtubeUrl.value 
                             : (youtubeUrl.value || null)
            });
            sessionId.value = response.data.id;
            localStorage.setItem('currentSessionId', sessionId.value);
            console.log("🆕 Session Created:", sessionId.value);
        } catch (e) {
            console.error("Session Create Error:", e);
            alert("세션 생성 실패. 로그인을 확인해주세요.");
            return;
        }
    }

    isRecording.value = true;
    recorder.value = new AudioRecorder(handleAudioData);
    
    try {
        // [FIX] 영상 강의(하이브리드) 모드면 무조건 시스템 오디오(탭 오디오) 녹음
        // 오프라인 모드 & 영상 없음 -> 마이크 사용
        if (mode.value === 'offline' && !youtubeEmbedUrl.value) {
             await recorder.value.startMic(5000);
        } else {
             // 그 외 (유튜브 모드, 유니버설 모드, 오프라인+영상 모드) -> 시스템 오디오 사용
             alert("📢 [중요] 팝업에서 '현재 탭(Chrome 탭)'을 선택하고, \n반드시 '오디오 공유'를 체크해주세요!");
             await recorder.value.startSystemAudio(5000);
        }
    } catch (err) {
        console.error("Rec Error:", err);
        isRecording.value = false;
        alert("녹음 시작 실패: 마이크/시스템 오디오 권한을 확인해주세요.");
    }
};

const stopRecording = () => {
    isRecording.value = false;
    if (recorder.value) recorder.value.stop();
};

const handleAudioData = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'chunk.webm');
    formData.append('sequence_order', sttLogs.value.length + 1);

    try {
        const { data } = await api.post(`/learning/sessions/${sessionId.value}/audio/`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        if (data.text) {
             const newLog = {
                id: data.id || Date.now(),
                sequence_order: sttLogs.value.length + 1,
                text_chunk: data.text,
                timestamp: new Date().toLocaleTimeString()
            };
            sttLogs.value.push(newLog);
            scrollToBottom();
        }
    } catch (e) { console.error("STT Error:", e); }
};

const scrollToBottom = async () => {
    await nextTick();
    if (logsContainer.value) {
        logsContainer.value.scrollTo({ top: logsContainer.value.scrollHeight, behavior: 'smooth' });
    }
};

const startNewSession = () => {
    if (confirm('현재 학습을 종료하고, 새로운 학습을 시작하시겠습니까?')) {
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
        
        // Clear Storage
        localStorage.removeItem('currentSessionId');
        localStorage.removeItem('currentYoutubeUrl');
        localStorage.removeItem('restoredMode');
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
        
        // [FIX] 세션 종료 시 로컬 스토리지 정리
        localStorage.removeItem('currentSessionId');
        localStorage.removeItem('currentYoutubeUrl');
    }

    // 3. 퀴즈 생성 요청
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
    if (!quizData.value) return;
    try {
        const { data } = await api.post(`/learning/assessment/${quizData.value.id}/submit/`, {
            answers: quizAnswers.value
        });
        quizResult.value = data;
    } catch (e) { alert("제출 실패"); }
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
        <div v-if="!mode || (mode === 'youtube' && !isUrlSubmitted)" class="mode-overlay">
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

        <!-- [NEW] Lecture List View -->
        <div v-if="mode === 'lecture'" class="lecture-view-container glass-panel">
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
                <div v-if="lectureSessions.length === 0" class="empty-state-large">
                    <p>등록된 수업 기록이 없습니다.</p>
                </div>
                
                <div v-for="sess in lectureSessions" :key="sess.id" class="session-card-row" @click="loadSessionFromSidebar(sess)">
                    <div class="card-left">
                        <div class="status-badge" :class="{done: sess.is_completed}">
                            {{ sess.is_completed ? '완료' : '진행중' }}
                        </div>
                        <div class="card-text">
                            <h3>{{ sess.title }}</h3>
                            <span class="date">{{ sess.session_date }}</span>
                        </div>
                    </div>
                    <div class="card-right">
                        <span class="btn-text highlight">
                            {{ sess.is_completed ? '📝 복습하기' : '▶ 이어하기' }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2. Actual Learning Interface -->
        <div v-if="mode" class="container" :class="{'layout-vertical': mode === 'youtube', 'layout-split': mode === 'offline' || mode === 'universal'}">
            
            <!-- [NEW] Review Header (Only in Youtube Mode) -->
            <header v-if="mode === 'youtube'" class="review-header glass-panel">
                 <div class="header-left">
                     <div class="status-badge header-badge">✅ 학습 완료 (복습 모드)</div>
                     <span class="session-id-text">🔄 세션 연결됨 (ID: {{sessionId}})</span>
                 </div>
                 <button class="btn btn-control secondary" style="height:36px; font-size:13px; margin-right:8px;" @click="startNewSession">
                     <Plus size="14" style="margin-right:4px;" /> 새 학습
                 </button>
                 <button class="btn btn-control secondary" style="height:36px; font-size:13px;" @click="router.push('/dashboard')">나가기</button>
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
                        </div>
                        <div class="markdown-text">{{ sessionSummary }}</div>
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
                        <button class="btn btn-primary btn-full" @click="submitQuiz">제출</button>
                        <button class="btn btn-secondary btn-full" style="margin-top:10px" @click="showQuiz=false">닫기</button>
                    </div>
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
                    <h3>현재 개설된 클래스</h3>
                    <div class="lecture-list">
                        <div v-for="lec in availableLectures" :key="lec.id" class="lecture-item" :class="{'selected': selectedLectureId === lec.id}" @click="selectLecture(lec)">
                            <div class="lec-info">
                                <span class="lec-title">{{ lec.title }}</span>
                                <span class="lec-instructor">{{ lec.instructor_name }} 강사님</span>
                            </div>
                            <div v-if="lec.is_enrolled" class="badge-enrolled">바로 입장 →</div>
                            <span v-else class="action-arrow">→</span>
                        </div>
                        <div v-if="availableLectures.length === 0" class="empty-list">
                            진행 중인 클래스가 없습니다.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    </template> <!-- END MAIN CONTENT -->
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
    background: rgba(28,28,30,0.95); display: flex; flex-direction: column; padding: 24px;
    min-height: 600px; height: auto; /* Increased height > 500px */
}
.stt-container { flex: 1; min-height: 550px; /* overflow-y aligned with parent */ padding-right: 10px; }
.stt-bubble { margin-bottom: 16px; p { line-height:1.5; } .time { font-size:11px; color:#666; } }

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

/* Mode Overlay */
.mode-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.85); z-index: 3000;
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
.input-group { display: flex; gap: 12px; margin-top: 24px; input { flex: 1; padding: 12px; background: #222; border: 1px solid #444; color: white; border-radius: 8px;} }
.back-link { cursor: pointer; color: #888; text-align: left; margin-bottom: 10px; &:hover { color: white; } }

/* Quiz */
.quiz-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.9); z-index: 4000; display: flex; align-items: center; justify-content: center;
}
.quiz-card { width: 600px; max-height: 90vh; overflow-y: auto; background: #1c1c1e; padding: 0; }
.quiz-header { text-align: center; padding: 20px; }
.questions-list { padding: 20px; display: flex; flex-direction: column; gap: 30px; }
.question-item { .q-title { font-weight: bold; margin-bottom: 10px; } }
.options-group { display: flex; flex-direction: column; gap: 8px; }
.quiz-footer { padding: 20px; }
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
    background: #1c1c1e; padding: 32px; border-radius: 16px; 
    width: 800px; max-width: 95vw;
    text-align: center; border: 1px solid #333;
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
    display: flex; justify-content: flex-end; margin-bottom: 16px;
}
.markdown-text {
    white-space: pre-wrap; font-size: 15px; color: #e0e0e0;
}

/* Animations */
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spin-anim { animation: spin 1s linear infinite; }
.btn-accent:disabled { opacity: 0.7; cursor: not-allowed; }
.lecture-item {
    background: #2c2c2e; padding: 16px; border-radius: 8px; cursor: pointer;
    display: flex; justify-content: space-between; align-items: center;
    transition: all 0.2s;
    border: 1px solid transparent;
    &:hover { background: #3a3a3c; }
    &.selected { border-color: var(--color-accent); background: rgba(79, 172, 254, 0.1); }
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
.lecture-view-container {
    max-width: 800px; margin: 40px auto; padding: 30px; min-height: 500px;
}
.lecture-info-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 15px;
    h2 { font-size: 24px; color: var(--color-primary); }
}
.session-list-wrapper { display: flex; flex-direction: column; gap: 15px; }
.session-card-row {
    display: flex; justify-content: space-between; align-items: center;
    background: #2c2c2e; padding: 20px; border-radius: 12px; cursor: pointer; transition: all 0.2s;
    border: 1px solid transparent;

    &:hover { background: #3a3a3c; transform: translateY(-2px); border-color: var(--color-accent); }
}
.card-left { display: flex; align-items: center; gap: 15px; }
.status-badge {
    padding: 4px 10px; border-radius: 20px; font-size: 12px; background: #444; color: #aaa;
    &.done { background: rgba(79, 172, 254, 0.2); color: var(--color-accent); border: 1px solid var(--color-accent); }
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
    background: #1c1c1e; border: 1px solid #333; border-radius: 12px;
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
    border: 1px solid #333;
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
}

.btn-text.highlight {
    color: var(--color-accent); font-weight: bold; border: 1px solid var(--color-accent);
    padding: 8px 16px; border-radius: 8px; background: rgba(79, 172, 254, 0.1);
    transition: all 0.2s; display: inline-block;
}
.session-card-row:hover .btn-text.highlight {
    background: var(--color-accent); color: white;
}
</style>
