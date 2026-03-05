<script setup>
import { ref, onMounted, computed } from 'vue';
import { useToast } from '../composables/useToast';
const { showToast } = useToast();
import { useRouter } from 'vue-router';
import { ArrowLeft, CheckCircle, Circle, Zap, RefreshCw, Clock, ChevronDown, ChevronUp, BookOpen, AlertTriangle, ExternalLink } from 'lucide-vue-next';
import { getCurriculums, getCurriculum, completeItem, rerouteCurriculum, getRerouteHistory, generateCurriculum } from '../api/learning';

const router = useRouter();

const curriculums = ref([]);
const activeCurriculum = ref(null);
const rerouteHistory = ref([]);
const isLoading = ref(false);
const isRerouting = ref(false);
const showHistory = ref(false);
const isGenerating = ref(false);

const progressColor = computed(() => {
    if (!activeCurriculum.value) return '#333';
    const p = activeCurriculum.value.progress_percent;
    if (p >= 80) return '#00f260';
    if (p >= 50) return '#4facfe';
    if (p >= 20) return '#fbc531';
    return '#ff5555';
});

const fetchCurriculums = async () => {
    isLoading.value = true;
    try {
        const data = await getCurriculums();
        curriculums.value = Array.isArray(data) ? data : (data.results || []);
        if (curriculums.value.length > 0 && !activeCurriculum.value) {
            await selectCurriculum(curriculums.value[0]);
        }
    } catch (e) { /* silent */ }
    isLoading.value = false;
};

const selectCurriculum = async (c) => {
    try {
        const data = await getCurriculum(c.id);
        activeCurriculum.value = data;
        fetchHistory(c.id);
    } catch (e) { /* silent */ }
};

const fetchHistory = async (id) => {
    try {
        const data = await getRerouteHistory(id);
        rerouteHistory.value = data.logs || [];
    } catch (e) { rerouteHistory.value = []; }
};

const toggleComplete = async (item) => {
    if (!activeCurriculum.value) return;
    try {
        const data = await completeItem(activeCurriculum.value.id, item.id);
        activeCurriculum.value.progress_percent = data.progress_percent;
        item.is_completed = data.is_completed;
        item.completed_at = data.is_completed ? new Date().toISOString() : null;
    } catch (e) { /* silent */ }
};

const goToItem = (item) => {
    // 해당 주제로 AI 튜터 학습 페이지 진입
    const query = { topic: item.title };
    if (item.lecture) query.lectureId = item.lecture;
    router.push({ path: '/ai-chat', query });
};

const doReroute = async () => {
    if (!activeCurriculum.value || isRerouting.value) return;
    isRerouting.value = true;
    try {
        await rerouteCurriculum(activeCurriculum.value.id);
        await selectCurriculum(activeCurriculum.value);
    } catch (e) {
        showToast('리라우팅 실패: ' + (e.response?.data?.error || e.message), 'error');
    }
    isRerouting.value = false;
};

const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return `${d.getMonth()+1}/${d.getDate()}`;
};

const typeEmoji = (type) => {
    const map = { LECTURE: '📖', QUIZ: '📝', PROJECT: '🛠️', SUPPLEMENT: '📌', REVIEW: '🔄' };
    return map[type] || '📄';
};

const doGenerate = async () => {
    if (isGenerating.value) return;
    isGenerating.value = true;
    try {
        const data = await generateCurriculum();
        activeCurriculum.value = data;
        curriculums.value = [data];
        showToast('🎉 AI 로드맵이 생성되었습니다!', 'success');
    } catch (e) {
        const errMsg = e.response?.data?.error || e.message;
        if (errMsg.includes('활성 커리큘럼')) {
            showToast('이미 진행 중인 로드맵이 있습니다. 새로고침 해주세요.', 'warning');
            // 기존 커리큘럼 다시 불러오기
            await fetchCurriculums();
        } else if (e.response?.status === 401) {
            showToast('로그인이 필요합니다. 다시 로그인해주세요.', 'error');
            router.push('/login');
        } else {
            showToast('로드맵 생성 실패: ' + errMsg + '\n수강 강의가 있는지 확인해주세요.', 'error');
        }
    }
    isGenerating.value = false;
};

onMounted(fetchCurriculums);
</script>

<template>
    <div class="curriculum-view">
        <div class="container">
            <!-- Header -->
            <header class="cv-header">
                <button class="back-btn" @click="router.push('/dashboard')">
                    <ArrowLeft :size="18" /> 대시보드
                </button>
                <h1>🗺️ 나의 학습 로드맵</h1>
                <p class="subtitle">AI가 당신의 학습 경로를 최적으로 안내합니다</p>
            </header>

            <!-- Curriculum Tabs -->
            <div v-if="curriculums.length > 1" class="cv-tabs">
                <button v-for="c in curriculums" :key="c.id"
                    class="cv-tab" :class="{ active: activeCurriculum?.id === c.id }"
                    @click="selectCurriculum(c)">
                    {{ c.title }}
                </button>
            </div>

            <!-- No Curriculum -->
            <div v-if="!activeCurriculum && !isLoading" class="cv-empty glass-panel">
                <div class="empty-icon">🗺️</div>
                <h2>아직 학습 로드맵이 없습니다</h2>
                <p>수강 중인 강의를 기반으로<br>AI가 맞춤형 학습 경로를 설계해드립니다.</p>
                <button class="generate-btn" @click="doGenerate" :disabled="isGenerating">
                    <RefreshCw v-if="isGenerating" :size="18" class="spinning" />
                    <span v-if="isGenerating">AI가 로드맵을 설계하고 있습니다...</span>
                    <span v-else>🤖 AI 로드맵 생성하기</span>
                </button>
            </div>

            <!-- Active Curriculum -->
            <div v-if="activeCurriculum" class="cv-content">
                <!-- Progress Overview -->
                <div class="cv-progress glass-panel">
                    <div class="progress-info">
                        <h2>{{ activeCurriculum.title }}</h2>
                        <p class="course-name" v-if="activeCurriculum.course_name">
                            <BookOpen :size="14" /> {{ activeCurriculum.course_name }}
                        </p>
                        <div class="progress-stats">
                            <span class="progress-pct" :style="{ color: progressColor }">
                                {{ activeCurriculum.progress_percent }}%
                            </span>
                            <span class="progress-label">완료</span>
                            <span v-if="activeCurriculum.target_date" class="target-date">
                                <Clock :size="14" /> 목표: {{ formatDate(activeCurriculum.target_date) }}
                            </span>
                        </div>
                    </div>
                    <div class="progress-ring-wrap">
                        <svg viewBox="0 0 120 120" class="progress-svg">
                            <circle cx="60" cy="60" r="50" fill="none" stroke="#222" stroke-width="10" />
                            <circle cx="60" cy="60" r="50" fill="none" :stroke="progressColor" stroke-width="10"
                                stroke-linecap="round"
                                :stroke-dasharray="314"
                                :stroke-dashoffset="314 - (314 * activeCurriculum.progress_percent / 100)"
                                transform="rotate(-90 60 60)" />
                        </svg>
                        <span class="ring-text">{{ activeCurriculum.progress_percent }}%</span>
                    </div>
                </div>

                <!-- AI Reroute Button -->
                <button class="reroute-btn" @click="doReroute" :disabled="isRerouting">
                    <RefreshCw :size="16" :class="{ spinning: isRerouting }" />
                    {{ isRerouting ? 'AI 분석 중...' : '🤖 AI 경로 재설계' }}
                </button>

                <!-- Timeline -->
                <div class="cv-timeline">
                    <div v-for="(item, idx) in (activeCurriculum.items || [])" :key="item.id"
                        class="timeline-item"
                        :class="{
                            completed: item.is_completed,
                            supplementary: item.is_supplementary,
                            current: !item.is_completed && (idx === 0 || (activeCurriculum.items[idx-1]?.is_completed))
                        }">
                        <div class="timeline-line" v-if="idx > 0"></div>
                        <div class="timeline-node" @click.stop="toggleComplete(item)" :title="item.is_completed ? '완료 해제' : '완료 처리'">
                            <CheckCircle v-if="item.is_completed" :size="24" class="node-icon done" />
                            <Zap v-else-if="item.is_supplementary" :size="24" class="node-icon supplement" />
                            <Circle v-else :size="24" class="node-icon pending" />
                        </div>
                        <div class="timeline-card clickable" @click="goToItem(item)">
                            <div class="card-top">
                                <span class="item-emoji">{{ typeEmoji(item.item_type) }}</span>
                                <div class="card-info">
                                    <h4>{{ item.title }}</h4>
                                    <div class="card-tags">
                                        <span class="tag type-tag">{{ item.item_type }}</span>
                                        <span v-if="item.is_supplementary" class="tag supp-tag">
                                            <AlertTriangle :size="12" /> 보충
                                        </span>
                                    </div>
                                </div>
                                <ExternalLink :size="16" class="go-icon" />
                            </div>
                            <div v-if="item.completed_at" class="card-completed">
                                ✅ {{ formatDate(item.completed_at) }} 완료
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Reroute History -->
                <div class="cv-history glass-panel" v-if="rerouteHistory.length > 0">
                    <button class="history-toggle" @click="showHistory = !showHistory">
                        📋 리라우팅 이력 ({{ rerouteHistory.length }}건)
                        <ChevronDown v-if="!showHistory" :size="16" />
                        <ChevronUp v-else :size="16" />
                    </button>
                    <div v-if="showHistory" class="history-list">
                        <div v-for="log in rerouteHistory" :key="log.id" class="history-item">
                            <div class="history-header">
                                <span class="history-reason">{{ log.reason }}</span>
                                <span class="history-date">{{ formatDate(log.created_at) }}</span>
                            </div>
                            <p class="history-detail">{{ log.reason_detail }}</p>
                            <p class="history-rec" v-if="log.ai_recommendation">
                                🤖 {{ log.ai_recommendation }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.curriculum-view {
    min-height: 100vh;
    background: radial-gradient(circle at 30% 20%, rgba(0, 242, 96, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 70% 80%, rgba(79, 172, 254, 0.08) 0%, transparent 40%),
                #0a0a0a;
    color: white;
    padding: 80px 0 60px;
}

.container { max-width: 900px; margin: 0 auto; padding: 0 24px; }

.cv-header {
    margin-bottom: 32px;
    h1 { font-size: 28px; margin: 12px 0 8px; }
    .subtitle { color: #888; font-size: 14px; }
}

.back-btn {
    display: flex; align-items: center; gap: 6px;
    background: none; border: none; color: #888; cursor: pointer; font-size: 13px; padding: 0;
    &:hover { color: #4facfe; }
}

.glass-panel {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 24px;
}

// ═══ Progress ═══
.cv-progress {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px;
    h2 { font-size: 20px; margin-bottom: 8px; }
    .course-name { color: #888; font-size: 13px; display: flex; align-items: center; gap: 6px; margin-bottom: 12px; }
}

.progress-stats {
    display: flex; align-items: baseline; gap: 8px;
    .progress-pct { font-size: 36px; font-weight: 900; }
    .progress-label { color: #888; font-size: 14px; }
    .target-date { color: #666; font-size: 12px; display: flex; align-items: center; gap: 4px; margin-left: 16px; }
}

.progress-ring-wrap {
    position: relative; width: 100px; height: 100px;
    .progress-svg { width: 100%; height: 100%; }
    .ring-text {
        position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
        font-size: 18px; font-weight: 700; color: #fff;
    }
}

// ═══ Reroute Button ═══
.reroute-btn {
    width: 100%; padding: 14px;
    background: linear-gradient(135deg, rgba(79,172,254,0.15), rgba(0,242,96,0.15));
    border: 1px solid rgba(79,172,254,0.3);
    border-radius: 12px; color: #4facfe;
    font-size: 15px; font-weight: 600;
    cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
    margin-bottom: 32px; transition: all 0.3s;
    &:hover:not(:disabled) { background: linear-gradient(135deg, rgba(79,172,254,0.25), rgba(0,242,96,0.25)); }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
    .spinning { animation: spin 1s linear infinite; }
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

// ═══ Timeline ═══
.cv-timeline {
    position: relative;
}

.timeline-item {
    display: flex; align-items: flex-start; gap: 16px;
    position: relative;
    margin-bottom: 8px;
}

.timeline-line {
    position: absolute; left: 11px; top: -8px;
    width: 2px; height: 16px; background: #333;
    .completed + & { background: #00f260; }
}

.timeline-node {
    flex-shrink: 0; cursor: pointer;
    .node-icon {
        &.done { color: #00f260; }
        &.supplement { color: #fbc531; }
        &.pending { color: #444; }
    }
}

.timeline-card {
    flex: 1;
    background: #111; border: 1px solid #222;
    border-radius: 12px; padding: 16px;
    transition: all 0.2s;
    &.clickable:hover { border-color: #4facfe; background: #161616; }
}

.completed .timeline-card { border-color: rgba(0,242,96,0.2); opacity: 0.7; }
.supplementary .timeline-card { border-color: rgba(251,197,49,0.3); background: rgba(251,197,49,0.03); }
.current .timeline-card { border-color: #4facfe; box-shadow: 0 0 20px rgba(79,172,254,0.1); }

.card-top {
    display: flex; align-items: center; gap: 12px;
}

.item-emoji { font-size: 24px; }

.card-info {
    flex: 1;
    h4 { font-size: 15px; margin: 0 0 6px; }
}

.card-tags { display: flex; gap: 6px; }
.tag {
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    &.type-tag { background: rgba(79,172,254,0.1); color: #4facfe; }
    &.supp-tag { background: rgba(251,197,49,0.1); color: #fbc531; display: flex; align-items: center; gap: 3px; }
}

.card-actions {
    display: flex; align-items: center; gap: 10px;
    flex-shrink: 0;
}

.check-btn {
    background: none; border: none; cursor: pointer;
    color: #555; padding: 4px;
    border-radius: 50%; transition: all 0.2s;
    display: flex; align-items: center;
    &:hover { color: #4facfe; background: rgba(79,172,254,0.1); }
    &.checked { color: #00f260; }
    &.checked:hover { color: #ff5555; background: rgba(255,85,85,0.1); }
}

.go-icon { color: #555; flex-shrink: 0; }

.card-completed {
    margin-top: 8px; padding-top: 8px;
    border-top: 1px solid rgba(255,255,255,0.05);
    font-size: 12px; color: #00f260;
}

// ═══ History ═══
.cv-history { margin-top: 32px; }

.history-toggle {
    width: 100%; background: none; border: none; color: #888;
    font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 8px;
    &:hover { color: #4facfe; }
}

.history-list { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; }

.history-item {
    padding: 16px; background: #1a1a1a; border-radius: 10px; border: 1px solid #222;
}
.history-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.history-reason { color: #fbc531; font-weight: 600; font-size: 13px; }
.history-date { color: #666; font-size: 12px; }
.history-detail { color: #aaa; font-size: 13px; margin-bottom: 8px; }
.history-rec { color: #4facfe; font-size: 13px; background: rgba(79,172,254,0.05); padding: 8px 12px; border-radius: 8px; }

// ═══ Tabs ═══
.cv-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-bottom: 4px;
    &::-webkit-scrollbar { display: none; }
}
.cv-tab {
    padding: 8px 16px;
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 20px;
    color: #888;
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
    flex-shrink: 0;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    &.active { background: #1e3a5f; border-color: #4facfe; color: white; }
    &:hover:not(.active) { border-color: #555; }
}

.cv-empty {
    text-align: center; padding: 60px;
    .empty-icon { font-size: 64px; margin-bottom: 16px; }
    h2 { font-size: 20px; margin-bottom: 12px; }
    p { color: #888; line-height: 1.6; margin-bottom: 24px; }
}

.generate-btn {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 16px 32px;
    background: linear-gradient(135deg, rgba(79,172,254,0.2), rgba(0,242,96,0.2));
    border: 1px solid rgba(79,172,254,0.4);
    border-radius: 14px;
    color: #4facfe;
    font-size: 16px; font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    &:hover:not(:disabled) {
        background: linear-gradient(135deg, rgba(79,172,254,0.35), rgba(0,242,96,0.35));
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(79,172,254,0.2);
    }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
    .spinning { animation: spin 1s linear infinite; }
}
</style>
