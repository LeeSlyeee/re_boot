<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' });
API.interceptors.request.use(c => { const t = localStorage.getItem('token'); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });

const gapMap = ref(null);
const loading = ref(true);
const myResult = ref(null);
const myGoal = ref(null);
const activeFilter = ref('ALL'); // ALL, GAP, LEARNING, OWNED

onMounted(async () => {
    try {
        const [mapRes, resultRes, goalRes] = await Promise.all([
            API.get('/learning/gapmap/my-map/'),
            API.get('/learning/placement/my-result/'),
            API.get('/learning/goals/my-goal/'),
        ]);
        gapMap.value = mapRes.data;
        myResult.value = resultRes.data;
        myGoal.value = goalRes.data;
    } catch (e) {
        console.error(e);
    }
    loading.value = false;
});

const statusIcon = (s) => ({ OWNED: '✅', GAP: '⚠️', LEARNING: '🔄' }[s] || '❓');
const statusLabel = (s) => ({ OWNED: '보유', GAP: '부족', LEARNING: '학습 중' }[s] || '?');

// 모든 스킬을 플랫하게 + GAP 우선 정렬
const allSkills = computed(() => {
    if (!gapMap.value?.categories) return [];
    const flat = [];
    for (const [cat, skills] of Object.entries(gapMap.value.categories)) {
        for (const s of skills) {
            flat.push({ ...s, categoryName: cat });
        }
    }
    // GAP 우선 → LEARNING → OWNED
    const order = { GAP: 0, LEARNING: 1, OWNED: 2 };
    flat.sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3) || a.progress - b.progress);
    return flat;
});

const filteredSkills = computed(() => {
    if (activeFilter.value === 'ALL') return allSkills.value;
    return allSkills.value.filter(s => s.status === activeFilter.value);
});

// 카테고리별 부족 비율 (레이더 대용)
const categoryBreakdown = computed(() => {
    if (!gapMap.value?.categories) return [];
    const result = [];
    for (const [cat, skills] of Object.entries(gapMap.value.categories)) {
        const total = skills.length;
        const gap = skills.filter(s => s.status === 'GAP').count;
        const gapCount = skills.filter(s => s.status === 'GAP').length;
        const ownedCount = skills.filter(s => s.status === 'OWNED').length;
        const learningCount = skills.filter(s => s.status === 'LEARNING').length;
        const completionRate = total > 0 ? Math.round((ownedCount / total) * 100) : 0;
        result.push({ name: cat, total, gapCount, ownedCount, learningCount, completionRate });
    }
    // 부족이 많은 카테고리 우선
    result.sort((a, b) => b.gapCount - a.gapCount);
    return result;
});

const goToPlacement = () => router.push('/placement');

// 도넛 차트 SVG
const donutSegments = computed(() => {
    if (!gapMap.value?.stats) return [];
    const { owned, learning, gap } = gapMap.value.stats;
    const total = owned + learning + gap;
    if (total === 0) return [];
    const radius = 40;
    const circumference = 2 * Math.PI * radius;
    let offset = 0;
    const segments = [];
    const items = [
        { value: gap, color: '#ef4444', label: '부족' },
        { value: learning, color: '#f59e0b', label: '학습 중' },
        { value: owned, color: '#22c55e', label: '보유' },
    ];
    for (const item of items) {
        const pct = item.value / total;
        const dash = pct * circumference;
        segments.push({
            ...item,
            dashArray: `${dash} ${circumference - dash}`,
            dashOffset: -offset,
            pct: Math.round(pct * 100),
        });
        offset += dash;
    }
    return segments;
});
</script>

<template>
<div class="gapmap-container">
    <!-- 헤더 -->
    <div class="gapmap-header">
        <h1>🗺️ 나의 역량 갭 맵</h1>
        <div v-if="myResult?.has_result" class="header-badges">
            <span class="badge level" :class="'lv' + myResult.level">
                {{ { 1: '🌱 Level 1', 2: '🌿 Level 2', 3: '🌳 Level 3' }[myResult.level] }}
            </span>
            <span v-if="myGoal?.has_goal && myGoal.career_goal" class="badge goal">
                {{ myGoal.career_goal.icon }} {{ myGoal.career_goal.title }}
            </span>
        </div>
        <p v-else class="no-diagnosis">
            진단을 먼저 완료해주세요.
            <button @click="goToPlacement" class="btn-inline">진단 시작 →</button>
        </p>
    </div>

    <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>갭 맵을 불러오는 중...</p>
    </div>

    <template v-else-if="gapMap">
        <!-- ═══ 상단: 도넛 + 통계 ═══ -->
        <div class="overview-row">
            <!-- 도넛 차트 -->
            <div class="donut-card">
                <svg viewBox="0 0 100 100" class="donut-svg">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="12" />
                    <circle v-for="(seg, i) in donutSegments" :key="i"
                        cx="50" cy="50" r="40" fill="none"
                        :stroke="seg.color" stroke-width="12"
                        :stroke-dasharray="seg.dashArray"
                        :stroke-dashoffset="seg.dashOffset"
                        stroke-linecap="round"
                        transform="rotate(-90 50 50)"
                        style="transition: all 0.8s ease;" />
                    <text x="50" y="46" text-anchor="middle" fill="white" font-size="16" font-weight="800">
                        {{ gapMap.stats.completion_rate }}%
                    </text>
                    <text x="50" y="58" text-anchor="middle" fill="#94a3b8" font-size="6">달성률</text>
                </svg>
                <div class="donut-legend">
                    <span class="legend-item"><i style="background:#ef4444"></i> 부족 {{ gapMap.stats.gap }}</span>
                    <span class="legend-item"><i style="background:#f59e0b"></i> 학습 {{ gapMap.stats.learning }}</span>
                    <span class="legend-item"><i style="background:#22c55e"></i> 보유 {{ gapMap.stats.owned }}</span>
                </div>
            </div>

            <!-- 카테고리별 부족 비율 바 -->
            <div class="category-bars-card">
                <h3>📊 영역별 달성률</h3>
                <div v-for="cat in categoryBreakdown" :key="cat.name" class="cat-row">
                    <div class="cat-label">
                        <span class="cat-name">{{ cat.name }}</span>
                        <span class="cat-pct">{{ cat.completionRate }}%</span>
                    </div>
                    <div class="cat-bar-bg">
                        <div class="cat-bar-owned" :style="{ width: (cat.ownedCount / cat.total * 100) + '%' }"></div>
                        <div class="cat-bar-learning" :style="{ width: (cat.learningCount / cat.total * 100) + '%' }"></div>
                    </div>
                    <div class="cat-detail">
                        <span v-if="cat.gapCount > 0" class="cat-gap-badge">⚠️ {{ cat.gapCount }}개 부족</span>
                        <span v-else class="cat-ok-badge">✅ 완료</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══ 필터 탭 ═══ -->
        <div class="filter-tabs">
            <button class="ftab" :class="{ active: activeFilter === 'ALL' }" @click="activeFilter = 'ALL'">
                전체 <span class="ftab-count">{{ allSkills.length }}</span>
            </button>
            <button class="ftab ftab-gap" :class="{ active: activeFilter === 'GAP' }" @click="activeFilter = 'GAP'">
                ⚠️ 부족 <span class="ftab-count">{{ gapMap.stats.gap }}</span>
            </button>
            <button class="ftab ftab-learning" :class="{ active: activeFilter === 'LEARNING' }" @click="activeFilter = 'LEARNING'">
                🔄 학습 중 <span class="ftab-count">{{ gapMap.stats.learning }}</span>
            </button>
            <button class="ftab ftab-owned" :class="{ active: activeFilter === 'OWNED' }" @click="activeFilter = 'OWNED'">
                ✅ 보유 <span class="ftab-count">{{ gapMap.stats.owned }}</span>
            </button>
        </div>

        <!-- ═══ 스킬 목록 ═══ -->
        <div class="skills-list">
            <TransitionGroup name="skill-fade" tag="div" class="skills-grid">
                <div v-for="skill in filteredSkills" :key="skill.id"
                    class="skill-card" :class="skill.status.toLowerCase()">
                    <div class="skill-top">
                        <span class="skill-status-dot" :class="skill.status.toLowerCase()"></span>
                        <span class="skill-name">{{ skill.name }}</span>
                        <span class="skill-badge" :class="skill.status.toLowerCase()">{{ statusLabel(skill.status) }}</span>
                    </div>
                    <div class="skill-meta">
                        <span class="skill-cat">{{ skill.categoryName }}</span>
                        <span class="skill-diff">Lv{{ skill.difficulty }}</span>
                    </div>
                    <div class="skill-bar-track">
                        <div class="skill-bar-fill" :class="skill.status.toLowerCase()"
                            :style="{ width: skill.progress + '%' }"></div>
                    </div>
                    <div class="skill-bottom">
                        <span class="skill-pct">{{ skill.progress }}%</span>
                        <span v-if="skill.status === 'GAP'" class="skill-action">학습 필요 →</span>
                    </div>
                </div>
            </TransitionGroup>

            <div v-if="filteredSkills.length === 0" class="empty-filter">
                해당 상태의 스킬이 없습니다.
            </div>
        </div>
    </template>

    <div v-else class="empty-map">
        <p>아직 갭 맵 데이터가 없습니다.</p>
        <button @click="goToPlacement" class="btn-primary">🎯 진단 시작하기</button>
    </div>
</div>
</template>

<style scoped>
.gapmap-container {
    min-height: 100vh; padding: 40px 20px;
    background: linear-gradient(135deg, #0f172a, #1e293b);
    font-family: 'Pretendard', -apple-system, sans-serif;
    max-width: 960px; margin: 0 auto;
}

.gapmap-header { margin-bottom: 28px; }
.gapmap-header h1 { color: white; font-size: 28px; margin: 0 0 12px; }
.header-badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge { padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.badge.level { background: rgba(59,130,246,0.2); color: #93c5fd; }
.badge.level.lv1 { background: rgba(245,158,11,0.2); color: #fcd34d; }
.badge.level.lv2 { background: rgba(59,130,246,0.2); color: #93c5fd; }
.badge.level.lv3 { background: rgba(139,92,246,0.2); color: #c4b5fd; }
.badge.goal { background: rgba(34,197,94,0.2); color: #86efac; }
.no-diagnosis { color: #94a3b8; font-size: 14px; }
.btn-inline { background: none; border: none; color: #3b82f6; cursor: pointer; font-weight: 600; font-size: 14px; }

/* 로딩 */
.loading { text-align: center; color: #94a3b8; padding: 60px 0; }
.spinner { width: 36px; height: 36px; border: 3px solid rgba(255,255,255,0.1); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ═══ 상단 오버뷰 ═══ */
.overview-row {
    display: grid; grid-template-columns: 240px 1fr; gap: 16px; margin-bottom: 24px;
}
@media (max-width: 700px) {
    .overview-row { grid-template-columns: 1fr; }
}

/* 도넛 */
.donut-card {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 24px; text-align: center;
}
.donut-svg { width: 160px; height: 160px; margin: 0 auto; display: block; }
.donut-legend { display: flex; flex-direction: column; gap: 6px; margin-top: 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; color: #94a3b8; font-size: 12px; }
.legend-item i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

/* 카테고리 바 */
.category-bars-card {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 24px;
}
.category-bars-card h3 { color: white; font-size: 15px; margin: 0 0 16px; }
.cat-row { margin-bottom: 14px; }
.cat-label { display: flex; justify-content: space-between; margin-bottom: 4px; }
.cat-name { color: #e2e8f0; font-size: 13px; font-weight: 500; }
.cat-pct { color: #94a3b8; font-size: 12px; font-weight: 700; }
.cat-bar-bg {
    height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px;
    overflow: hidden; display: flex;
}
.cat-bar-owned { height: 100%; background: #22c55e; transition: width 0.6s; }
.cat-bar-learning { height: 100%; background: #f59e0b; transition: width 0.6s; }
.cat-detail { margin-top: 4px; }
.cat-gap-badge { font-size: 11px; color: #fca5a5; }
.cat-ok-badge { font-size: 11px; color: #86efac; }

/* ═══ 필터 탭 ═══ */
.filter-tabs {
    display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;
}
.ftab {
    padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    color: #94a3b8; cursor: pointer; transition: all 0.2s;
}
.ftab:hover { border-color: rgba(255,255,255,0.25); color: white; }
.ftab.active { background: rgba(59,130,246,0.2); border-color: #3b82f6; color: white; }
.ftab-gap.active { background: rgba(239,68,68,0.15); border-color: #ef4444; }
.ftab-learning.active { background: rgba(245,158,11,0.15); border-color: #f59e0b; }
.ftab-owned.active { background: rgba(34,197,94,0.15); border-color: #22c55e; }
.ftab-count {
    display: inline-block; padding: 1px 7px; margin-left: 4px;
    background: rgba(255,255,255,0.1); border-radius: 10px; font-size: 11px;
}

/* ═══ 스킬 카드 ═══ */
.skills-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;
}
.skill-card {
    padding: 14px 16px; border-radius: 12px;
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.25s;
}
.skill-card:hover { transform: translateY(-2px); }
.skill-card.gap {
    border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.04);
    box-shadow: inset 0 0 0 1px rgba(239,68,68,0.06);
}
.skill-card.learning {
    border-color: rgba(245,158,11,0.2); background: rgba(245,158,11,0.04);
}
.skill-card.owned {
    border-color: rgba(34,197,94,0.15); background: rgba(34,197,94,0.04);
}

.skill-top { display: flex; align-items: center; gap: 8px; }
.skill-status-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.skill-status-dot.gap { background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.5); animation: pulse-dot 2s infinite; }
.skill-status-dot.learning { background: #f59e0b; }
.skill-status-dot.owned { background: #22c55e; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.skill-name { flex: 1; color: white; font-size: 14px; font-weight: 600; }
.skill-badge {
    padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700;
}
.skill-badge.gap { background: rgba(239,68,68,0.15); color: #fca5a5; }
.skill-badge.learning { background: rgba(245,158,11,0.15); color: #fcd34d; }
.skill-badge.owned { background: rgba(34,197,94,0.15); color: #86efac; }

.skill-meta { display: flex; gap: 8px; margin: 6px 0 8px; }
.skill-cat { font-size: 11px; color: #64748b; }
.skill-diff { font-size: 10px; color: #64748b; background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 4px; }

.skill-bar-track { height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
.skill-bar-fill { height: 100%; border-radius: 3px; transition: width 0.8s ease; }
.skill-bar-fill.gap { background: linear-gradient(90deg, #ef4444, #f87171); }
.skill-bar-fill.learning { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.skill-bar-fill.owned { background: linear-gradient(90deg, #22c55e, #4ade80); }

.skill-bottom { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; }
.skill-pct { font-size: 11px; color: #64748b; font-weight: 600; }
.skill-action { font-size: 11px; color: #ef4444; font-weight: 600; }

.empty-filter { text-align: center; color: #64748b; font-size: 14px; padding: 40px 0; }

/* 애니메이션 */
.skill-fade-enter-active { transition: all 0.3s ease; }
.skill-fade-leave-active { transition: all 0.2s ease; }
.skill-fade-enter-from { opacity: 0; transform: translateY(10px); }
.skill-fade-leave-to { opacity: 0; transform: scale(0.95); }

/* 빈 상태 */
.empty-map { text-align: center; padding: 60px 0; color: #94a3b8; }
.btn-primary { padding: 12px 28px; background: #3b82f6; color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 16px; }
</style>
