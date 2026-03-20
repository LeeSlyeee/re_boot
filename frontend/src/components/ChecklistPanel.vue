<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { CheckCircle, Circle, ChevronDown, ChevronRight, ListChecks, Search, ExternalLink, Sparkles, Trophy, Target } from 'lucide-vue-next';
import api from '../api/axios';

const router = useRouter();

const props = defineProps({
    lectureId: { type: [String, Number], required: true },
    compact: { type: Boolean, default: false }, // 라이브 세션용 컴팩트 모드
});

const syllabi = ref([]);
const isLoading = ref(true);
const openWeeks = ref({});
const searchQuery = ref('');
const sortMode = ref('all'); // 'all' | 'incomplete'
const showConfetti = ref(false);

// Computed: 전체 진도율
const progress = computed(() => {
    let total = 0;
    let checked = 0;
    syllabi.value.forEach(s => {
        s.objectives.forEach(o => {
            total++;
            if (o.is_checked) checked++;
        });
    });
    return total === 0 ? 0 : Math.round((checked / total) * 100);
});

// 전체/달성/미달성 통계
const stats = computed(() => {
    let total = 0, checked = 0;
    syllabi.value.forEach(s => {
        s.objectives.forEach(o => {
            total++;
            if (o.is_checked) checked++;
        });
    });
    return { total, checked, remaining: total - checked };
});

// 진행 등급 (레벨업 UX)
const progressTier = computed(() => {
    const p = progress.value;
    if (p >= 100) return { label: '🏆 마스터', color: '#fbbf24', emoji: '🏆' };
    if (p >= 80) return { label: '🔥 거의 완성', color: '#f97316', emoji: '🔥' };
    if (p >= 50) return { label: '💪 절반 돌파', color: '#3b82f6', emoji: '💪' };
    if (p >= 25) return { label: '🌱 성장 중', color: '#22c55e', emoji: '🌱' };
    return { label: '🚀 시작', color: '#8b5cf6', emoji: '🚀' };
});

// 검색 및 정렬된 실라버스
const filteredSyllabi = computed(() => {
    const q = searchQuery.value.trim().toLowerCase();
    return syllabi.value.map(week => {
        let objs = week.objectives;
        
        // 검색 필터
        if (q) {
            objs = objs.filter(o => o.content.toLowerCase().includes(q));
        }
        
        // 정렬: 미완료 우선
        if (sortMode.value === 'incomplete') {
            objs = [...objs].sort((a, b) => (a.is_checked === b.is_checked ? 0 : a.is_checked ? 1 : -1));
        }
        
        return { ...week, objectives: objs };
    }).filter(week => {
        // 검색 시 결과가 없는 주차는 숨김
        return q ? week.objectives.length > 0 : true;
    });
});

// 주차별 진도율
const weekProgress = (week) => {
    const total = week.objectives.length;
    if (total === 0) return 0;
    const checked = week.objectives.filter(o => o.is_checked).length;
    return Math.round((checked / total) * 100);
};

// 스킬 클릭 시 해당 주차 학습 세션으로 이동
const goToLecture = (weekNumber) => {
    router.push({ 
        path: '/learning', 
        query: { lectureId: props.lectureId } 
    });
};

const fetchChecklist = async () => {
    if (!props.lectureId) return;
    isLoading.value = true;
    try {
        const res = await api.get(`/learning/checklist/?lecture_id=${props.lectureId}`);
        syllabi.value = res.data;
        
        // Default: Open first incomplete week, or the first week
        let openedOne = false;
        syllabi.value.forEach((s) => {
             const hasIncomplete = s.objectives.some(o => !o.is_checked);
             if (!openedOne && hasIncomplete) {
                 openWeeks.value[s.week_number] = true;
                 openedOne = true;
             }
        });
        // 만약 모두 완료면 첫 주차를 열기
        if (!openedOne && syllabi.value.length > 0) {
            openWeeks.value[syllabi.value[0].week_number] = true;
        }
    } catch (e) {
        console.error("Failed to fetch checklist", e);
    } finally {
        isLoading.value = false;
    }
};

const toggleWeek = (weekNum) => {
    openWeeks.value[weekNum] = !openWeeks.value[weekNum];
};

const toggleObjective = async (objective) => {
    // Frontend Optimistic Update
    const originalState = objective.is_checked;
    objective.is_checked = !objective.is_checked;

    // 100% 달성 시 축하 이펙트
    if (progress.value === 100 && !showConfetti.value) {
        showConfetti.value = true;
        setTimeout(() => { showConfetti.value = false; }, 3000);
    }

    try {
        await api.post(`/learning/checklist/${objective.id}/toggle/`);
    } catch (e) {
        console.error("Toggle Failed", e);
        objective.is_checked = originalState; // Revert on fail
    }
};

onMounted(fetchChecklist);
watch(() => props.lectureId, fetchChecklist);

</script>

<template>
    <div class="checklist-panel" :class="{ 'compact-mode': compact }">
        <!-- 축하 이펙트 오버레이 -->
        <transition name="confetti-fade">
            <div v-if="showConfetti" class="confetti-overlay">
                <div class="confetti-content">
                    <span class="confetti-emoji">🎉</span>
                    <p>모든 학습 목표 달성!</p>
                </div>
            </div>
        </transition>

        <!-- 헤더 -->
        <div class="cl-header">
            <div class="cl-title-row">
                <div class="cl-icon-wrap">
                    <ListChecks :size="compact ? 16 : 18" />
                </div>
                <h3>학습 체크리스트</h3>
            </div>
            
            <!-- 진행 등급 뱃지 -->
            <div class="cl-tier-badge" :style="{ '--tier-color': progressTier.color }">
                <span class="tier-emoji">{{ progressTier.emoji }}</span>
                <span class="tier-label">{{ progressTier.label }}</span>
            </div>
        </div>

        <!-- 프로그레스 영역 -->
        <div class="cl-progress-area">
            <div class="cl-progress-ring-wrap">
                <svg class="cl-ring" viewBox="0 0 36 36">
                    <path class="ring-bg"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3" />
                    <path class="ring-fill"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none" :stroke="progressTier.color" stroke-width="3"
                        :stroke-dasharray="`${progress}, 100`"
                        stroke-linecap="round" />
                </svg>
                <span class="ring-number">{{ progress }}%</span>
            </div>
            <div class="cl-stats-pills">
                <div class="stat-pill done">
                    <CheckCircle :size="12" />
                    <span>{{ stats.checked }}</span>
                </div>
                <div class="stat-pill remaining">
                    <Target :size="12" />
                    <span>{{ stats.remaining }}</span>
                </div>
            </div>
        </div>

        <!-- 검색 및 정렬 -->
        <div class="cl-filter-bar" v-if="!compact || syllabi.length > 3">
            <div class="cl-search-box">
                <Search :size="13" class="cl-search-icon" />
                <input type="text" v-model="searchQuery" placeholder="스킬 검색..." class="cl-search-input" />
            </div>
            <div class="cl-sort-pills">
                <button 
                    :class="['cl-pill', { active: sortMode === 'all' }]" 
                    @click="sortMode = 'all'">전체</button>
                <button 
                    :class="['cl-pill', { active: sortMode === 'incomplete' }]" 
                    @click="sortMode = 'incomplete'">미완료</button>
            </div>
        </div>

        <!-- 로딩 -->
        <div v-if="isLoading" class="cl-loading">
            <div class="cl-spinner"></div>
            <span>로딩 중...</span>
        </div>

        <!-- 빈 상태 -->
        <div v-else-if="syllabi.length === 0" class="cl-empty">
            <Sparkles :size="32" class="cl-empty-icon" />
            <p>등록된 강의 계획서가 없습니다.</p>
        </div>

        <div v-else-if="filteredSyllabi.length === 0" class="cl-empty">
            <Search :size="28" class="cl-empty-icon" />
            <p>검색 결과가 없습니다.</p>
        </div>

        <!-- 주차별 목록 -->
        <div v-else class="cl-week-list">
            <div v-for="week in filteredSyllabi" :key="week.id" 
                 class="cl-week-card"
                 :class="{ 'week-complete': weekProgress(week) === 100 }">
                
                <!-- 주차 헤더 -->
                <div class="cl-week-header" @click="toggleWeek(week.week_number)">
                    <div class="cl-week-left">
                        <component :is="openWeeks[week.week_number] ? ChevronDown : ChevronRight" 
                                   :size="14" class="cl-arrow" />
                        <span class="cl-week-num">{{ week.week_number }}주차</span>
                        <span class="cl-week-title">{{ week.title }}</span>
                    </div>
                    <div class="cl-week-right">
                        <div class="cl-mini-bar">
                            <div class="cl-mini-fill" 
                                 :style="{ width: weekProgress(week) + '%' }"
                                 :class="{ complete: weekProgress(week) === 100 }"></div>
                        </div>
                        <span class="cl-week-pct" 
                              :class="{ complete: weekProgress(week) === 100 }">
                            {{ weekProgress(week) }}%
                        </span>
                        <button class="cl-go-btn" @click.stop="goToLecture(week.week_number)" 
                                title="해당 주차 학습으로 이동">
                            <ExternalLink :size="12" />
                        </button>
                    </div>
                </div>
                
                <!-- 목표 목록 -->
                <transition name="slide-open">
                    <div v-if="openWeeks[week.week_number]" class="cl-objective-list">
                        <div v-for="(obj, idx) in week.objectives" :key="obj.id" 
                             class="cl-obj-item" :class="{ checked: obj.is_checked }"
                             @click="toggleObjective(obj)">
                            <div class="cl-obj-check">
                                <transition name="check-pop" mode="out-in">
                                    <CheckCircle v-if="obj.is_checked" :size="18" 
                                                 class="cl-check-on" :key="'on'" />
                                    <Circle v-else :size="18" 
                                            class="cl-check-off" :key="'off'" />
                                </transition>
                            </div>
                            <span class="cl-obj-text">{{ obj.content }}</span>
                            <span v-if="obj.is_checked" class="cl-done-tag">완료</span>
                        </div>
                        <div v-if="week.objectives.length === 0" class="cl-no-obj">
                            목표 없음
                        </div>
                    </div>
                </transition>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
/* ══════════════════════════════════════════
   ChecklistPanel — 리디자인 v2
   ══════════════════════════════════════════ */

.checklist-panel {
    display: flex; 
    flex-direction: column;
    height: 100%; 
    max-height: 800px;
    background: rgba(20, 20, 24, 0.75);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px;
    padding: 20px;
    overflow: hidden;
    position: relative;
    transition: all 0.3s ease;

    &.compact-mode {
        max-height: 500px;
        border-radius: 16px;
        padding: 16px;

        .cl-header { margin-bottom: 8px; }
        .cl-progress-area { margin-bottom: 10px; }
        .cl-title-row h3 { font-size: 14px; }
        .ring-number { font-size: 11px; }
        .cl-ring { width: 44px; height: 44px; }
        .cl-week-header { padding: 8px 12px; }
        .cl-obj-item { padding: 5px 0; }
        .cl-obj-text { font-size: 12px; }
    }
}

/* ─── 축하 이펙트 ─── */
.confetti-overlay {
    position: absolute; inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center;
    z-index: 10; border-radius: 20px;
}
.confetti-content {
    text-align: center; animation: bounce-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
    p { color: white; font-weight: 700; font-size: 16px; margin: 8px 0 0; }
}
.confetti-emoji { font-size: 48px; display: block; animation: spin-trophy 1s ease; }
@keyframes spin-trophy { 0% { transform: scale(0) rotate(-180deg); } 100% { transform: scale(1) rotate(0); } }
@keyframes bounce-in { 0% { transform: scale(0.3); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
.confetti-fade-enter-active { animation: bounce-in 0.4s ease; }
.confetti-fade-leave-active { transition: opacity 0.5s ease; }
.confetti-fade-leave-to { opacity: 0; }

/* ─── 헤더 ─── */
.cl-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 14px;
}
.cl-title-row {
    display: flex; align-items: center; gap: 8px;
    h3 { font-size: 16px; color: #f0f0f2; margin: 0; font-weight: 700; letter-spacing: -0.02em; }
}
.cl-icon-wrap {
    width: 28px; height: 28px; border-radius: 8px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(139, 92, 246, 0.25));
    display: flex; align-items: center; justify-content: center;
    color: #a78bfa;
}
.cl-tier-badge {
    display: flex; align-items: center; gap: 4px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px; padding: 3px 10px;
    font-size: 11px; color: var(--tier-color); font-weight: 600;
    .tier-emoji { font-size: 12px; }
    .tier-label { white-space: nowrap; }
}

/* ─── 프로그레스 영역 ─── */
.cl-progress-area {
    display: flex; align-items: center; gap: 14px;
    margin-bottom: 14px;
    padding: 12px 14px;
    background: rgba(255,255,255,0.03);
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.05);
}
.cl-progress-ring-wrap {
    position: relative; flex-shrink: 0;
}
.cl-ring {
    width: 52px; height: 52px; transform: rotate(-90deg);
    .ring-fill { transition: stroke-dasharray 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
}
.ring-number {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 800; color: #f0f0f2;
    letter-spacing: -0.03em;
}
.cl-stats-pills {
    display: flex; gap: 8px; flex: 1; justify-content: flex-end;
}
.stat-pill {
    display: flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 600;
    &.done { background: rgba(34,197,94,0.12); color: #4ade80; }
    &.remaining { background: rgba(250,204,21,0.1); color: #facc15; }
}

/* ─── 검색 & 소트 ─── */
.cl-filter-bar {
    display: flex; gap: 6px; align-items: center; margin-bottom: 12px;
}
.cl-search-box {
    flex: 1; display: flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 6px 10px;
    transition: border-color 0.2s;
    &:focus-within { border-color: rgba(99, 102, 241, 0.4); }
    .cl-search-icon { color: #6b7280; flex-shrink: 0; }
    .cl-search-input {
        flex: 1; background: none; border: none; outline: none;
        color: #e5e7eb; font-size: 12px;
        &::placeholder { color: #4b5563; }
    }
}
.cl-sort-pills {
    display: flex; gap: 2px; background: rgba(255,255,255,0.04); border-radius: 8px; overflow: hidden;
    .cl-pill {
        background: none; border: none; color: #6b7280; font-size: 11px;
        padding: 5px 10px; cursor: pointer; transition: all 0.2s;
        white-space: nowrap; font-weight: 500;
        &.active { background: rgba(99, 102, 241, 0.15); color: #818cf8; font-weight: 600; }
        &:hover:not(.active) { color: #9ca3af; }
    }
}

/* ─── 로딩 / 빈 상태 ─── */
.cl-loading {
    display: flex; flex-direction: column; align-items: center; gap: 10px;
    padding: 40px 0; color: #6b7280; font-size: 13px;
}
.cl-spinner {
    width: 24px; height: 24px; border-radius: 50%;
    border: 2.5px solid rgba(255,255,255,0.1);
    border-top-color: #818cf8;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.cl-empty {
    text-align: center; padding: 36px 0; color: #6b7280;
    .cl-empty-icon { color: #4b5563; margin-bottom: 8px; }
    p { font-size: 13px; margin: 0; }
}

/* ─── 주차 리스트 ─── */
.cl-week-list {
    flex: 1; overflow-y: auto;
    display: flex; flex-direction: column; gap: 8px;
    padding-right: 2px;
    
    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 2px; }
    &::-webkit-scrollbar-track { background: transparent; }
}

/* ─── 주차 카드 ─── */
.cl-week-card {
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
    overflow: hidden;
    flex-shrink: 0;
    transition: border-color 0.2s, background 0.2s;

    &:hover { border-color: rgba(255,255,255,0.1); }

    &.week-complete {
        border-color: rgba(34,197,94,0.2);
        background: rgba(34,197,94,0.03);
    }
}

.cl-week-header {
    padding: 10px 14px; 
    display: flex; 
    align-items: center; 
    justify-content: space-between;
    cursor: pointer; 
    transition: background 0.15s;
    user-select: none;
    gap: 8px;
    
    &:hover { background: rgba(255,255,255,0.04); }
}
.cl-week-left {
    display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1;
    .cl-arrow { color: #6b7280; flex-shrink: 0; transition: transform 0.2s; }
    .cl-week-num { 
        font-weight: 700; font-size: 12px; color: #818cf8; 
        background: rgba(99,102,241,0.1); padding: 2px 7px; border-radius: 6px;
        white-space: nowrap; flex-shrink: 0;
    }
    .cl-week-title { 
        font-weight: 500; font-size: 13px; color: #d1d5db; 
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
}
.cl-week-right {
    display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.cl-mini-bar {
    width: 40px; height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden;
    .cl-mini-fill { 
        height: 100%; border-radius: 2px;
        background: linear-gradient(90deg, #6366f1, #818cf8);
        transition: width 0.4s ease;
        &.complete { background: linear-gradient(90deg, #22c55e, #4ade80); }
    }
}
.cl-week-pct {
    font-size: 11px; font-weight: 700; color: #6b7280; min-width: 28px; text-align: right;
    &.complete { color: #4ade80; }
}
.cl-go-btn {
    background: none; border: none; color: #4b5563; cursor: pointer;
    padding: 3px; border-radius: 6px; display: flex; align-items: center;
    transition: all 0.2s;
    &:hover { color: #818cf8; background: rgba(99,102,241,0.1); }
}

/* ─── 목표 목록 ─── */
.cl-objective-list {
    padding: 4px 14px 12px 28px;
    display: flex; flex-direction: column; gap: 2px;
}

.cl-obj-item {
    display: flex; align-items: center; gap: 10px;
    cursor: pointer; padding: 7px 8px;
    border-radius: 8px; transition: all 0.15s;
    
    &:hover { background: rgba(255,255,255,0.04); }
    
    &.checked {
        .cl-obj-text { color: #6b7280; text-decoration: line-through; text-decoration-color: rgba(107,114,128,0.4); }
    }
}
.cl-obj-check {
    flex-shrink: 0; display: flex; align-items: center;
}
.cl-check-off { color: #4b5563; transition: color 0.15s; }
.cl-check-on { color: #4ade80; filter: drop-shadow(0 0 4px rgba(74, 222, 128, 0.3)); }
.cl-obj-item:hover .cl-check-off { color: #818cf8; }

.cl-obj-text { 
    font-size: 13px; color: #d1d5db; line-height: 1.4; flex: 1; 
    transition: color 0.15s; 
}
.cl-obj-item:hover .cl-obj-text:not(.checked .cl-obj-text) { color: #f3f4f6; }

.cl-done-tag {
    font-size: 10px; color: #4ade80; background: rgba(34,197,94,0.1);
    padding: 1px 6px; border-radius: 4px; font-weight: 600;
    flex-shrink: 0;
}

.cl-no-obj { font-size: 12px; color: #4b5563; font-style: italic; padding: 4px 0; }

/* ─── 체크 애니메이션 ─── */
.check-pop-enter-active { animation: pop-check 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55); }
.check-pop-leave-active { transition: opacity 0.1s; }
.check-pop-leave-to { opacity: 0; }
@keyframes pop-check { 
    0% { transform: scale(0.5); opacity: 0; } 
    70% { transform: scale(1.2); }
    100% { transform: scale(1); opacity: 1; } 
}

/* ─── 슬라이드 오픈 ─── */
.slide-open-enter-active { 
    animation: slide-down 0.25s ease; 
    overflow: hidden;
}
.slide-open-leave-active { 
    animation: slide-down 0.2s ease reverse; 
    overflow: hidden;
}
@keyframes slide-down {
    0% { max-height: 0; opacity: 0; }
    100% { max-height: 600px; opacity: 1; }
}
</style>
