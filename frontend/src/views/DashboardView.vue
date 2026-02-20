<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { BookOpen, Trophy, Clock, PlayCircle, BarChart2, Trash2, Youtube as YoutubeIcon, MonitorPlay, Users } from 'lucide-vue-next'; // Users added
import api from '../api/axios';

const router = useRouter();
const userName = ref('학습자'); 
const recentSessions = ref([]);
const watchHistory = ref([]);
const myLectures = ref([]); // [New] My Enrolled Lectures
const stats = ref({
    totalHours: 0,
    finishedSessions: 0,
    quizScore: 0,
    todayHours: 0,
    attendanceRate: 0,
    attendedDays: 0,
    totalClassDays: 0
});

// --- Join Class State ---
const showJoinModal = ref(false);
const joinCode = ref('');
const availableLectures = ref([]);
const selectedLectureId = ref(null);

const dailyProgress = computed(() => {
    const goal = 6.33; 
    const current = stats.value.todayHours || 0;
    const pct = (current / goal) * 100;
    return Math.min(Math.round(pct), 100); 
});

const uniqueHistory = computed(() => {
    const seenIds = new Set();
    const result = [];
    
    // Reverse array to show newest first if not already sorted?
    // Actually API returns sorted. But filter forward.
    watchHistory.value.forEach(item => {
        let id;
        if (typeof item === 'string') {
            id = item;
        } else {
            // Use sessionId if available (even if 0), otherwise fallback to url
            // Be careful with 0 being falsy in JS check
            if (item.sessionId !== undefined && item.sessionId !== null) {
                id = item.sessionId;
            } else {
                id = item.url;
            }
        }
        
        // If still no ID (e.g. empty url and no sessionId), skip
        if (!id) return;

        if (!seenIds.has(id)) {
            seenIds.add(id);
            result.push(item);
        }
    });
    return result;
});

const fetchAvailableLectures = async () => {
    try {
        const res = await api.get('/learning/lectures/public/');
        availableLectures.value = res.data;
    } catch (e) { console.error("Failed to fetch lectures", e); }
};

const fetchMyLectures = async () => {
    try {
        const res = await api.get('/learning/lectures/my/');
        myLectures.value = res.data;
    } catch (e) { console.error("Failed to fetch my lectures", e); }
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

const joinClass = async () => {
    if (!joinCode.value || joinCode.value.length < 6) return;
    try {
        const res = await api.post('/learning/enroll/', { access_code: joinCode.value });
        alert(`'${res.data.title}' 클래스 입장 완료!`);
        closeJoinModal();
        // [FIX] 바로 해당 강의실로 이동
        router.push({ path: '/learning', query: { lectureId: res.data.lecture_id } });
    } catch (e) {
        alert(e.response?.data?.error || "코드가 올바르지 않거나 이미 가입된 클래스입니다.");
    }
};

const selectLecture = (lecture) => {
    // 대시보드에서는 클릭 시 바로 입장하지 않고 코드 입력을 유도하거나,
    // 이미 등록된 경우 바로가기를 제공해야 함.
    if (lecture.is_enrolled) {
        // 이미 등록됨 -> LearningView로 이동 (세션 시작은 LearningView에서)
        // [FIX] lectureId를 전달하여 해당 클래스의 수업 목록을 로드하도록 유도
        router.push({ path: '/learning', query: { lectureId: lecture.id } });
    } else {
        // 코드 입력창에 포커스?
        alert("입장 코드를 입력하여 수강 신청해주세요.");
    }
};

onMounted(async () => {
    // 1. Get User Info
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    if (user.username) userName.value = user.username;

    // 2. Fetch History
    try {
        const { data } = await api.get('/learning/sessions/history/');
        
        if (data && Array.isArray(data)) {
            watchHistory.value = data; 
            localStorage.setItem('watchHistory', JSON.stringify(data)); 
        }
    } catch (e) { console.error("Failed to load history:", e); }
    
    // 3. Fetch Stats
    try {
        const { data } = await api.get('/learning/sessions/stats/');
        if (data)  stats.value = data;
    } catch (e) { console.error("Failed to load stats:", e); }
    
    // 4. Fetch My Lectures
    fetchMyLectures();

    // 5. Phase 2-3: 간격 반복 due 항목 로드
    fetchSRDue();
    // 6. Phase 3: 교수자 메시지 로드
    fetchMyMessages();
    // 7. 스킬블록 로드
    fetchSkillBlocks();
    fetchInterviewData();
});

// --- Phase 2-3: Spaced Repetition ---
const srDueItems = ref([]);
const srAnswering = ref(null); // 현재 답변 중인 SR item
const srResult = ref(null);

const fetchSRDue = async () => {
    try {
        const { data } = await api.get('/learning/spaced-repetition/due/');
        srDueItems.value = data.due_items || [];
    } catch (e) { /* silent */ }
};

const startSRQuiz = (item) => {
    srAnswering.value = item;
    srResult.value = null;
};

const submitSRAnswer = async (itemId, answer) => {
    try {
        const { data } = await api.post(`/learning/spaced-repetition/${itemId}/complete/`, { answer });
        srResult.value = data;
        if (data.is_correct) {
            setTimeout(() => {
                srDueItems.value = srDueItems.value.filter(i => i.id !== itemId);
                srAnswering.value = null;
                srResult.value = null;
            }, 2000);
        }
    } catch (e) { /* silent */ }
};

const closeSRQuiz = () => {
    srAnswering.value = null;
    srResult.value = null;
};

// --- Phase 3: 교수자 메시지 ---
const myMessages = ref([]);
const unreadCount = ref(0);

const fetchMyMessages = async () => {
    try {
        const { data } = await api.get('/learning/messages/my/');
        myMessages.value = data.messages || [];
        unreadCount.value = data.unread_count || 0;
    } catch (e) { /* silent */ }
};

const markRead = async (msgId) => {
    try {
        await api.post('/learning/messages/my/', { message_id: msgId });
        const msg = myMessages.value.find(m => m.id === msgId);
        if (msg) msg.is_read = true;
        unreadCount.value = myMessages.value.filter(m => !m.is_read).length;
    } catch (e) { /* silent */ }
};

// --- 스킬블록 ---
const skillBlocks = ref(null);
const interviewData = ref(null);

const fetchSkillBlocks = async () => {
    try {
        const { data } = await api.get('/learning/skill-blocks/my/');
        skillBlocks.value = data;
    } catch (e) { /* silent */ }
};

const fetchInterviewData = async () => {
    try {
        const { data } = await api.get('/learning/skill-blocks/interview-data/');
        interviewData.value = data;
    } catch (e) { /* silent */ }
};

const syncSkillBlocks = async (lectureId) => {
    try {
        await api.post(`/learning/skill-blocks/sync/${lectureId}/`);
        await fetchSkillBlocks();
        await fetchInterviewData();
    } catch (e) { /* silent */ }
};

const startLearning = () => {
    router.push('/learning');
};

const getThumbnail = (url) => {
    if (!url) return null;
    let videoId = null;
    try {
        if (url.includes('v=')) videoId = url.split('v=')[1].split('&')[0];
        else if (url.includes('youtu.be/')) videoId = url.split('youtu.be/')[1].split('?')[0];
        else if (url.includes('embed/')) videoId = url.split('embed/')[1].split('?')[0];
    } catch (e) {}
    return videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : null;
};

const deleteHistory = async (sessionId) => {
    if (!sessionId) return;
    if (!confirm('이 학습 기록을 삭제하시겠습니까?')) return;
    try {
        await api.delete(`/learning/sessions/${sessionId}/`);
        watchHistory.value = watchHistory.value.filter(item => item.sessionId !== sessionId);
    } catch (e) {}
};

const goToLearning = (item) => {
    // 1. Session ID (Backend Item)
    if (item.sessionId) {
        const videoUrl = item.url || null; // null if offline
        const isUrl = videoUrl && videoUrl.startsWith('http');
        
        localStorage.setItem('currentSessionId', item.sessionId);
        localStorage.setItem('currentYoutubeUrl', videoUrl || '');
        localStorage.setItem('restoredMode', isUrl ? 'youtube' : 'offline'); // Default to offline if no URL
        
        // [FIX] Pass sessionId query to force resume in LearningView
        router.push({ path: '/learning', query: { sessionId: item.sessionId } });

    } 
    // 2. Legacy String URL
    else if (typeof item === 'string') {
        localStorage.setItem('currentYoutubeUrl', item);
        localStorage.removeItem('restoredMode'); 
        router.push('/learning');
    }
};

const continueLearning = () => {
    if (uniqueHistory.value && uniqueHistory.value.length > 0) {
        goToLearning(uniqueHistory.value[0]);
    } else {
        startLearning();
    }
};
</script>

<template>
    <div class="dashboard-view">
        <div class="container">
            <!-- Header -->
            <header class="dashboard-header">
                <h1 class="text-headline">안녕하세요, <span class="highlight">{{ userName }}</span>님! 👋</h1>
                <p class="subtitle">오늘도 새로운 지식을 쌓아볼까요?</p>
            </header>

            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card glass-panel">
                    <div class="icon-box blue"><Clock /></div>
                    <div class="stat-info">
                        <h3>총 학습 시간</h3>
                        <p class="value">
                            <span v-if="stats.totalHoursInt > 0">{{ stats.totalHoursInt }}시간 </span>
                            <span>{{ stats.totalMinutesInt || 0 }}분</span>
                        </p>
                    </div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="icon-box purple"><BookOpen /></div>
                    <div class="stat-info">
                        <h3>완료한 수업</h3>
                        <p class="value">{{ stats.finishedSessions }}개</p>
                    </div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="icon-box green"><Trophy /></div>
                    <div class="stat-info">
                        <h3>최근 퀴즈 점수</h3>
                        <p class="value">{{ stats.quizScore }}점</p>
                    </div>
                </div>
                <div class="stat-card glass-panel">
                    <div class="icon-box orange"><BarChart2 /></div>
                    <div class="stat-info">
                        <h3>출석률</h3>
                        <p class="value">{{ stats.attendanceRate }}%</p>
                        <p class="sub-value" v-if="stats.totalClassDays > 0">{{ stats.attendedDays }} / {{ stats.totalClassDays }}일</p>
                    </div>
                </div>
            </div>

            <!-- Main Content Stack -->
            <div class="dashboard-main">
                
                <!-- 1. Today's Goal -->
                <section class="task-section glass-panel">
                    <div class="section-header">
                        <h2>오늘의 목표</h2>
                    </div>
                <div class="task-grid">
                    <div class="daily-task-card">
                        <div class="progress-ring" :style="{ background: `conic-gradient(var(--color-accent) ${dailyProgress}%, #333 ${dailyProgress}% 100%)` }">
                            <span class="percentage">{{ dailyProgress }}%</span>
                        </div>
                        <div class="task-info">
                            <h3>일일 퀘스트 진행중</h3>
                            <p>{{ stats.todayHours }}시간 / 6.3시간 (목표)</p>
                        </div>
                        <button class="btn btn-accent value-btn" @click="continueLearning">이어서 하기</button>
                    </div>
                        
                    <div class="analysis-card clickable" @click="openJoinModal">
                        <h3>🏫 클래스 참여하기</h3>
                        <p class="desc">강사님께 전달받은 입장 코드를 입력하여<br>새로운 클래스에 참여하세요.</p>
                    </div>
                </div>
                </section>

                <!-- Phase 2-3: 간격 반복 알림 -->
                <!-- Phase 3: 교수자 메시지 -->
                <!-- 스킬블록 -->
                <section v-if="skillBlocks || interviewData" class="skillblock-section glass-panel mt-section">
                    <div class="sr-header">
                        <h2>🏆 스킬블록</h2>
                    </div>

                    <!-- 인터뷰 멘트 -->
                    <div v-if="interviewData" class="sb-interview-card">
                        <div class="sb-level-badge">
                            <span class="sb-level-emoji">{{ interviewData.emoji }}</span>
                            <span class="sb-level-name">{{ interviewData.level_name }}</span>
                        </div>
                        <p class="sb-hint">{{ interviewData.interview_hint }}</p>
                        <div class="sb-counts">
                            <span class="sb-earned">✅ {{ interviewData.earned_count }}개 획득</span>
                            <span class="sb-remaining">🔲 {{ interviewData.remaining_count }}개 남음</span>
                        </div>
                    </div>

                    <!-- 블록 그리드 -->
                    <div v-if="skillBlocks && skillBlocks.categories" class="sb-categories">
                        <div v-for="(cat, catName) in skillBlocks.categories" :key="catName" class="sb-category">
                            <h4 class="sb-cat-title">{{ catName }}</h4>
                            <div class="sb-blocks-row">
                                <div v-for="b in [...cat.earned, ...cat.remaining]" :key="b.id"
                                    class="sb-block" :class="{ 'sb-earned': b.is_earned, 'sb-remaining': !b.is_earned }">
                                    <span class="sb-emoji">{{ b.emoji }}</span>
                                    <span class="sb-name">{{ b.skill_name }}</span>
                                    <span class="sb-score">{{ b.total_score }}점</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 갭 맵 비교 -->
                    <div v-if="skillBlocks && skillBlocks.gap_map" class="sb-gap-compare">
                        <div class="sb-gap-item"><span class="sb-gap-label">보유 ✅</span><span class="sb-gap-val">{{ skillBlocks.gap_map.owned }}</span></div>
                        <div class="sb-gap-item"><span class="sb-gap-label">학습중 🔄</span><span class="sb-gap-val">{{ skillBlocks.gap_map.learning }}</span></div>
                        <div class="sb-gap-item"><span class="sb-gap-label">미보유 🔲</span><span class="sb-gap-val">{{ skillBlocks.gap_map.gap }}</span></div>
                    </div>
                </section>

                <!-- Phase 3: 교수자 메시지 -->
                <section v-if="myMessages.length > 0" class="msg-section glass-panel mt-section">
                    <div class="sr-header">
                        <h2>📩 교수자 메시지 <span v-if="unreadCount > 0" class="sr-badge">{{ unreadCount }}</span></h2>
                    </div>
                    <div v-for="msg in myMessages" :key="msg.id" class="msg-card" :class="{ 'msg-unread': !msg.is_read }" @click="markRead(msg.id)">
                        <div class="msg-card-header">
                            <span class="msg-type-tag">{{ msg.message_type }}</span>
                            <span class="msg-from">{{ msg.sender }} · {{ msg.lecture_title }}</span>
                        </div>
                        <h4 class="msg-title">{{ msg.title }}</h4>
                        <p class="msg-content">{{ msg.content }}</p>
                    </div>
                </section>

                <section v-if="srDueItems.length > 0" class="sr-section glass-panel mt-section">
                    <div class="section-header">
                        <h2>🔔 복습 알림 <span class="sr-badge">{{ srDueItems.length }}</span></h2>
                    </div>
                    <div class="sr-items">
                        <div v-for="item in srDueItems" :key="item.id" class="sr-card">
                            <div class="sr-card-info">
                                <span class="sr-concept">{{ item.concept_name }}</span>
                                <span class="sr-label">{{ item.label }}</span>
                            </div>
                            <button class="sr-quiz-btn" @click="startSRQuiz(item)">30초 퀴즈 →</button>
                        </div>
                    </div>
                </section>

                <!-- SR 미니 퀴즈 모달 -->
                <div v-if="srAnswering" class="sr-modal-overlay" @click.self="closeSRQuiz">
                    <div class="sr-modal">
                        <h3>📝 {{ srAnswering.concept_name }}</h3>
                        <p class="sr-question">{{ srAnswering.review_question }}</p>
                        <div v-if="srAnswering.review_options && srAnswering.review_options.length > 0" class="sr-options">
                            <button v-for="(opt, idx) in srAnswering.review_options" :key="idx"
                                class="sr-option-btn"
                                :class="{ correct: srResult && srResult.correct_answer === opt, wrong: srResult && !srResult.is_correct && opt === srResult.correct_answer }"
                                @click="submitSRAnswer(srAnswering.id, opt)"
                                :disabled="!!srResult">
                                {{ opt }}
                            </button>
                        </div>
                        <div v-if="srResult" class="sr-result" :class="srResult.is_correct ? 'correct' : 'wrong'">
                            {{ srResult.is_correct ? '🎉 정답!' : '❌ 오답 — 정답: ' + srResult.correct_answer }}
                        </div>
                        <button v-if="srResult && !srResult.is_correct" class="sr-close-btn" @click="closeSRQuiz">닫기</button>
                    </div>
                </div>

                <!-- 1.5 My Courses -->
                <section v-if="myLectures.length > 0" class="lectures-section glass-panel mt-section">
                    <div class="section-header">
                        <h2>수강 중인 클래스</h2>
                    </div>
                    <div class="lecture-list-dash">
                        <div v-for="lec in myLectures" :key="lec.id" class="lecture-card" @click="selectLecture(lec)">
                            <div class="lec-icon">📚</div>
                            <div class="lec-info">
                                <h3>{{ lec.title }}</h3>
                                <p>{{ lec.instructor_name }} 강사님</p>
                            </div>
                            <div class="lec-arrow">→</div>
                        </div>
                    </div>
                </section>

                <!-- 2. Recent Activity -->
                <section class="history-section glass-panel mt-section">
                    <div class="section-header">
                        <h2>최근 수강 목록</h2>
                        <button class="btn btn-primary btn-small">전체보기</button>
                    </div>
                    
                    <div v-if="uniqueHistory.length > 0" class="history-list">
                        <div v-for="(item, idx) in uniqueHistory" :key="idx" class="history-item" @click="goToLearning(item)">
                            
                            <!-- Thumbnail: URL vs Type Icon -->
                            <div class="thumbnail-placeholder" :class="{'has-image': getThumbnail(item.url)}">
                                <img v-if="getThumbnail(item.url)" :src="getThumbnail(item.url)" alt="Thumbnail" class="thumb-img" />
                                <template v-else>
                                    <YoutubeIcon v-if="item.url" />
                                    <MonitorPlay v-else />
                                </template>
                            </div>

                            <div class="info">
                                <p class="url-text">{{ item.title || item }}</p>
                                <span class="date">{{ item.url ? '온라인 학습' : '오프라인/강의실 수업' }}</span>
                            </div>
                            
                            <div class="item-actions">
                                <button class="btn btn-primary btn-small" @click.stop="goToLearning(item)">이어하기</button>
                                <button class="btn-icon delete-btn" @click.stop="deleteHistory(item.sessionId)">
                                    <Trash2 size="16" />
                                </button>
                            </div>
                        </div>
                    </div>
                    <div v-else class="empty-state">
                        <p>아직 학습 기록이 없습니다.</p>
                        <button class="btn btn-primary" @click="startLearning">학습 시작하기</button>
                    </div>
                </section>
            </div>
        </div>
        
    <!-- Join Class Modal -->
    <div v-if="showJoinModal" class="modal-overlay" @click.self="closeJoinModal">
        <div class="modal-card wide-modal">
            <h2>클래스 참여</h2>
            
            <div class="modal-body-split">
                <!-- Left: Verification Code -->
                <div class="input-section">
                    <p class="sub-text">강사님에게 전달받은<br>6자리 코드를 입력해주세요.</p>
                    <input type="text" v-model="joinCode" maxlength="6" class="code-input" placeholder="CODE" @keyup.enter="joinClass" />
                    <button class="btn btn-primary full-width" @click="joinClass">코드 입력하여 입장</button>
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
                            <div v-if="lec.is_enrolled" class="badge-enrolled">수강 중 →</div>
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
        
    </div>
</template>

<style scoped lang="scss">
/* ... existing styles ... */

/* Modal Styles */
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.8); z-index: 2000;
    display: flex; align-items: center; justify-content: center;
}
.modal-card.wide-modal {
    background: #1c1c1e; padding: 32px; border-radius: 16px; 
    width: 800px; /* Wider for split view */
    max-width: 95vw;
    text-align: center; border: 1px solid #333;
}
.modal-body-split {
    display: flex; gap: 30px; margin-top: 30px; text-align: left;
}
.input-section { flex: 1; padding-right: 20px; display: flex; flex-direction: column; justify-content: center; }
.list-section { flex: 1.2; border-left: 1px solid #333; padding-left: 30px; max-height: 400px; overflow-y: auto; }

h2 { margin: 0; font-size: 24px; color: white; margin-bottom: 0px; text-align: center; width: 100%; }
h3 { font-size: 16px; color: #888; margin-bottom: 20px; font-weight: normal; }

.sub-text { color: #888; margin-bottom: 24px; font-size: 14px; text-align: center; }
.code-input {
    width: 100%; padding: 16px; font-size: 24px; letter-spacing: 4px; text-align: center;
    background: #000; border: 1px solid #444; border-radius: 8px; color: var(--color-accent);
    margin-bottom: 24px; text-transform: uppercase;
    &:focus { border-color: var(--color-accent); outline: none; }
}
.full-width { width: 100%; }

/* Lecture List */
.lecture-list { display: flex; flex-direction: column; gap: 10px; }
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

@media (max-width: 768px) {
    .modal-card.wide-modal { width: 90vw; }
    .modal-body-split { flex-direction: column; }
    .list-section { border-left: none; border-top: 1px solid #333; padding-left: 0; padding-top: 20px; }
    .input-section { padding-right: 0; }
}

.clickable { cursor: pointer; transition: transform 0.2s; &:hover { transform: scale(1.02); border-color: var(--color-accent); } }
/* Thumbnail Styles */
.thumbnail-placeholder {
    width: 60px; height: 40px; background: #333; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    
    &.has-image { background: transparent; }
    
    .thumb-img {
        width: 100%; height: 100%; object-fit: cover;
    }
}

.dashboard-view {
    padding-top: var(--header-height);
    min-height: 100vh;
    background: radial-gradient(circle at 10% 20%, rgba(29, 78, 216, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(124, 58, 237, 0.15) 0%, transparent 40%),
                #000; /* Deep black with subtle colored glows */
    color: white;
    padding-bottom: 40px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 24px;
}

.dashboard-header {
    margin: 40px 0;
    display: flex; justify-content: space-between; align-items: flex-end;
    .header-text {
        h1 { font-size: 32px; font-weight: 700; }
        .subtitle { color: #888; margin-top: 8px; font-size: 16px; }
    }
    .highlight { color: var(--color-primary); }
    .large-btn { padding: 12px 24px; font-size: 16px; border-radius: 12px; }
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
    margin-bottom: 40px;
}

.stat-card {
    display: flex; align-items: center; gap: 20px;
    padding: 24px;
    
    .icon-box {
        width: 50px; height: 50px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        background: rgba(255,255,255,0.1);
        
        &.blue { color: #4facfe; background: rgba(79, 172, 254, 0.1); }
        &.purple { color: #a18cd1; background: rgba(161, 140, 209, 0.1); }
        &.green { color: #00f260; background: rgba(0, 242, 96, 0.1); }
        &.orange { color: #ff9800; background: rgba(255, 152, 0, 0.1); }
    }
    
    .stat-info {
        h3 { font-size: 14px; color: #888; margin-bottom: 4px; }
        .value { font-size: 24px; font-weight: 700; }
        .sub-value { font-size: 12px; color: #666; margin-top: 2px; }
    }
}

/* Main Layout Stack */
.dashboard-main {
    display: flex; flex-direction: column;
}

.mt-section { margin-top: 24px; }

/* Task Grid (Horizontal) */
.task-grid {
    display: flex; gap: 24px;
}

.daily-task-card {
    flex: 1; margin-bottom: 0; /* reset */
    display: flex; align-items: center; gap: 16px;
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 20px; border-radius: 12px;
}

.analysis-card {
    flex: 1;
    background: rgba(79, 172, 254, 0.1); 
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(79, 172, 254, 0.2);
    padding: 20px; border-radius: 12px;
    h3 { color: #4facfe; font-size: 15px; margin-bottom: 8px; }
    p { font-size: 13px; line-height: 1.5; color: #ccc; }
}

/* My Lectures Section */
.lecture-list-dash {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
}

.lecture-card {
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    padding: 16px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid rgba(255, 255, 255, 0.05);

    &:hover {
        background: rgba(255,255,255,0.08); /* Slightly lighter on hover */
        transform: translateY(-2px);
        border-color: var(--color-accent);
    }
}

.lec-icon {
    font-size: 24px;
    width: 40px; height: 40px;
    background: rgba(255,255,255,0.05);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
}

.lec-info {
    flex: 1;
    h3 { font-size: 15px; font-weight: 600; color: white; margin-bottom: 4px; }
    p { font-size: 13px; color: #888; }
}

.lec-arrow {
    color: var(--color-accent);
    font-size: 18px;
    opacity: 0;
    transition: opacity 0.2s;
}

.lecture-card:hover .lec-arrow { opacity: 1; }

.section-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px;
    h2 { font-size: 20px; font-weight: 600; }
    .btn-text { 
        white-space: nowrap; /* Prevent wrapping */
        color: #888;
        font-size: 14px;
        &:hover { color: white; text-decoration: underline; }
    }
}

.glass-panel {
    background: rgba(28, 28, 30, 0.6); /* Semi-transparent */
    backdrop-filter: blur(20px); /* Heavy blur for glass effect */
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    border-radius: 16px;
    padding: 24px;
}

.history-list {
    display: flex; flex-direction: column; gap: 16px;
}

/* Button Styles matching global or logout button feel */
.btn {
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center; justify-content: center;
    white-space: nowrap; /* Prevent wrapping globally */
}

.btn-primary {
    background: var(--color-primary, #007aff); /* Fallback to standard blue */
    color: white;
    
    &:hover {
        background: var(--color-primary-dark, #0062cc);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
    }
}

.btn-small {
    padding: 6px 16px; /* Increased padding */
    font-size: 13px;
    height: 34px; /* Slightly taller */
}

.btn-text {
    background: transparent;
    color: #888;
    padding: 8px 16px;
    
    &:hover { color: white; background: rgba(255,255,255,0.1); }
}

.btn-icon {
    background: transparent;
    border: none;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    padding: 8px;
    border-radius: 50%;
    color: #888;
    transition: all 0.2s;
    
    &:hover {
        background: rgba(255,255,255,0.1);
        color: white;
    }
}

.item-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.history-item {
    display: flex; align-items: center; gap: 16px;
    padding: 16px; /* Increased padding for better touch target */
    border-radius: 12px;
    background: rgba(255,255,255,0.03); 
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    cursor: default; /* Item itself is container */
    transition: all 0.2s;
    border: 1px solid rgba(255,255,255,0.05); 
    
    &:hover { 
        background: rgba(255,255,255,0.05); 
        border-color: rgba(255,255,255,0.1);
    }
    
    .info {
        flex: 1; overflow: hidden;
        cursor: pointer; /* Text area is clickable */
        .url-text { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #eee; margin-bottom: 4px;}
        .date { font-size: 12px; color: #888; }
    }
    
    .delete-btn { 
        color: #666; 
        &:hover { color: #ef4444; background: rgba(239, 68, 68, 0.1); } 
    }
}

.empty-state {
    text-align: center; padding: 40px 0; color: #666;
    button { margin-top: 16px; }
}

.progress-ring {
    width: 50px; height: 50px; border-radius: 50%;
    /* border removal */
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: bold; color: var(--color-accent);
    position: relative; /* For pseudo-element */
}

/* Create the 'hole' to make it a ring */
.progress-ring::before {
    content: "";
    position: absolute;
    inset: 5px; /* Ring thickness */
    background: #2c2c2e; /* Match card bg somewhat */
    border-radius: 50%;
    z-index: 1;
}

.percentage {
    position: relative;
    z-index: 2;
}

.task-info { flex: 1; h3 { font-size: 16px; font-weight: 600; } p { font-size: 13px; color: #888; } }

/* ── Phase 2-3: Spaced Repetition ── */
.sr-section .section-header h2 { display: flex; align-items: center; gap: 8px; }
.sr-badge { background: #ef4444; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 700; }
.sr-items { display: flex; flex-direction: column; gap: 8px; }
.sr-card { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.2); border-radius: 10px; }
.sr-card-info { display: flex; flex-direction: column; gap: 4px; }
.sr-concept { font-size: 14px; font-weight: 600; color: #e2e8f0; }
.sr-label { font-size: 11px; color: #a78bfa; }
.sr-quiz-btn { padding: 6px 14px; background: rgba(99,102,241,0.2); color: #a78bfa; border: 1px solid rgba(99,102,241,0.3); border-radius: 8px; font-size: 12px; cursor: pointer; }
.sr-quiz-btn:hover { background: rgba(99,102,241,0.3); }
.sr-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 2000; display: flex; align-items: center; justify-content: center; }
.sr-modal { background: rgba(30,30,50,0.98); backdrop-filter: blur(12px); border: 1px solid rgba(99,102,241,0.3); border-radius: 16px; padding: 24px; max-width: 420px; width: 90%; }
.sr-modal h3 { margin: 0 0 12px; color: #a78bfa; font-size: 16px; }
.sr-question { color: #e2e8f0; font-size: 14px; line-height: 1.6; margin-bottom: 16px; }
.sr-options { display: flex; flex-direction: column; gap: 8px; }
.sr-option-btn { padding: 10px 14px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; color: #e2e8f0; font-size: 13px; cursor: pointer; text-align: left; transition: all 0.2s; }
.sr-option-btn:hover:not(:disabled) { background: rgba(99,102,241,0.15); border-color: rgba(99,102,241,0.4); }
.sr-option-btn.correct { background: rgba(34,197,94,0.2); border-color: #22c55e; color: #22c55e; }
.sr-option-btn.wrong { background: rgba(239,68,68,0.2); border-color: #ef4444; }
.sr-result { margin-top: 12px; padding: 10px; border-radius: 8px; font-size: 14px; font-weight: 600; text-align: center; }
.sr-result.correct { background: rgba(34,197,94,0.15); color: #22c55e; }
.sr-result.wrong { background: rgba(239,68,68,0.15); color: #ef4444; }
.sr-close-btn { margin-top: 12px; width: 100%; padding: 10px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; color: #94a3b8; cursor: pointer; }

/* Phase 3: 교수자 메시지 */
.msg-section { margin-bottom: 16px; }
.msg-card { padding: 12px; border-radius: 8px; margin-bottom: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); cursor: pointer; transition: all 0.2s; }
.msg-card:hover { background: rgba(255,255,255,0.06); }
.msg-unread { border-left: 3px solid #6366f1; background: rgba(99,102,241,0.05); }
.msg-card-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.msg-type-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(99,102,241,0.2); color: #a78bfa; font-weight: 600; }
.msg-from { font-size: 11px; color: #94a3b8; }
.msg-title { margin: 4px 0; font-size: 14px; color: #e2e8f0; }
.msg-content { margin: 0; font-size: 12px; color: #94a3b8; line-height: 1.5; }

/* 스킬블록 */
.skillblock-section { margin-bottom: 16px; }
.sb-interview-card { background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(168,85,247,0.1)); border: 1px solid rgba(99,102,241,0.2); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.sb-level-badge { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.sb-level-emoji { font-size: 32px; }
.sb-level-name { font-size: 18px; font-weight: 700; color: #c4b5fd; }
.sb-hint { color: #e2e8f0; font-size: 13px; line-height: 1.6; margin: 8px 0; }
.sb-counts { display: flex; gap: 16px; }
.sb-earned { color: #22c55e; font-size: 13px; font-weight: 600; }
.sb-remaining { color: #94a3b8; font-size: 13px; }

.sb-categories { margin-bottom: 16px; }
.sb-category { margin-bottom: 12px; }
.sb-cat-title { color: #a78bfa; font-size: 13px; margin: 0 0 6px 0; }
.sb-blocks-row { display: flex; gap: 6px; flex-wrap: wrap; }
.sb-block { display: flex; flex-direction: column; align-items: center; padding: 8px; border-radius: 10px; min-width: 70px; text-align: center; transition: all 0.2s; }
.sb-block.sb-earned { background: linear-gradient(135deg, rgba(234,179,8,0.15), rgba(251,191,36,0.1)); border: 1px solid rgba(234,179,8,0.3); }
.sb-block.sb-remaining { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); opacity: 0.6; }
.sb-emoji { font-size: 20px; }
.sb-name { font-size: 10px; color: #e2e8f0; margin-top: 2px; }
.sb-score { font-size: 9px; color: #a78bfa; }

.sb-gap-compare { display: flex; gap: 12px; justify-content: center; padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; }
.sb-gap-item { text-align: center; }
.sb-gap-label { display: block; font-size: 11px; color: #94a3b8; }
.sb-gap-val { display: block; font-size: 20px; font-weight: 700; color: #e2e8f0; }
</style>
