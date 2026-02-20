<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const API = axios.create({ baseURL: 'http://localhost:8000/api' });
API.interceptors.request.use(c => { const t = localStorage.getItem('access'); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });

const gapMap = ref(null);
const loading = ref(true);
const myResult = ref(null);
const myGoal = ref(null);

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

const statusIcon = (s) => ({ OWNED: '✅', GAP: '🔲', LEARNING: '🔄' }[s] || '❓');
const statusColor = (s) => ({ OWNED: '#22c55e', GAP: '#ef4444', LEARNING: '#f59e0b' }[s] || '#888');

const progressBarColor = (progress) => {
    if (progress >= 80) return '#22c55e';
    if (progress >= 40) return '#f59e0b';
    return '#ef4444';
};

const goToPlacement = () => router.push('/placement');
</script>

<template>
<div class="gapmap-container">
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
        <!-- 전체 통계 -->
        <div class="stats-row">
            <div class="stat-card owned">
                <span class="stat-num">{{ gapMap.stats.owned }}</span>
                <span class="stat-lbl">✅ 보유</span>
            </div>
            <div class="stat-card learning">
                <span class="stat-num">{{ gapMap.stats.learning }}</span>
                <span class="stat-lbl">🔄 학습 중</span>
            </div>
            <div class="stat-card gap">
                <span class="stat-num">{{ gapMap.stats.gap }}</span>
                <span class="stat-lbl">🔲 미보유</span>
            </div>
            <div class="stat-card total">
                <span class="stat-num">{{ gapMap.stats.completion_rate }}%</span>
                <span class="stat-lbl">달성률</span>
            </div>
        </div>

        <!-- 카테고리별 블록 -->
        <div v-for="(skills, category) in gapMap.categories" :key="category" class="category-section">
            <h3 class="cat-title">{{ category }}</h3>
            <div class="skills-grid">
                <div v-for="skill in skills" :key="skill.id" class="skill-block" :class="skill.status.toLowerCase()">
                    <div class="skill-header">
                        <span class="skill-icon">{{ statusIcon(skill.status) }}</span>
                        <span class="skill-name">{{ skill.name }}</span>
                        <span class="skill-diff">Lv{{ skill.difficulty }}</span>
                    </div>
                    <div class="skill-progress-track">
                        <div class="skill-progress-fill"
                            :style="{ width: skill.progress + '%', background: progressBarColor(skill.progress) }">
                        </div>
                    </div>
                    <span class="skill-pct">{{ skill.progress }}%</span>
                </div>
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
    max-width: 900px; margin: 0 auto;
}

.gapmap-header { margin-bottom: 32px; }
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

/* 통계 */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }
.stat-card {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px; padding: 16px; text-align: center;
}
.stat-card.owned { border-color: rgba(34,197,94,0.3); }
.stat-card.learning { border-color: rgba(245,158,11,0.3); }
.stat-card.gap { border-color: rgba(239,68,68,0.3); }
.stat-card.total { border-color: rgba(59,130,246,0.3); }
.stat-num { display: block; font-size: 28px; font-weight: 800; color: white; }
.stat-lbl { font-size: 11px; color: #94a3b8; }

/* 카테고리 */
.category-section { margin-bottom: 28px; }
.cat-title { color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }

.skills-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }

.skill-block {
    display: flex; flex-direction: column; gap: 6px;
    padding: 12px 14px; border-radius: 10px;
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.2s;
}
.skill-block.owned { border-color: rgba(34,197,94,0.2); background: rgba(34,197,94,0.05); }
.skill-block.learning { border-color: rgba(245,158,11,0.2); background: rgba(245,158,11,0.05); }
.skill-block.gap { border-color: rgba(239,68,68,0.15); background: rgba(239,68,68,0.03); }

.skill-header { display: flex; align-items: center; gap: 6px; }
.skill-icon { font-size: 14px; }
.skill-name { flex: 1; color: white; font-size: 13px; font-weight: 500; }
.skill-diff { font-size: 10px; color: #64748b; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; }

.skill-progress-track { height: 5px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; }
.skill-progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }

.skill-pct { font-size: 10px; color: #64748b; text-align: right; }

/* 빈 상태 */
.empty-map { text-align: center; padding: 60px 0; color: #94a3b8; }
.btn-primary { padding: 12px 28px; background: #3b82f6; color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 16px; }
</style>
