<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';

const router = useRouter();
const dashboard = ref(null);
const classDetail = ref(null);
const atRiskStudents = ref([]);
const vizData = ref(null);
const quizData = ref(null);
const engagementData = ref(null);
const skillHeatmap = ref(null);
const isLoading = ref(true);
const activeTab = ref('overview');
const selectedClassId = ref(null);

const fetchDashboard = async () => {
    isLoading.value = true;
    try {
        const { data } = await api.get('/learning/manager/dashboard/');
        dashboard.value = data;
        if (data.classes?.length > 0) {
            selectedClassId.value = data.classes[0].id;
            await fetchClassDetail(data.classes[0].id);
        }
        await fetchVisualization();
    } catch (e) { console.error(e); }
    isLoading.value = false;
};

const fetchClassDetail = async (classId) => {
    try {
        const { data } = await api.get(`/learning/manager/class/${classId}/`);
        classDetail.value = data;
    } catch (e) { /* silent */ }

    try {
        const { data } = await api.get(`/learning/manager/class/${classId}/at-risk/`);
        atRiskStudents.value = data.at_risk_students || [];
    } catch (e) { /* silent */ }
};

const fetchVisualization = async () => {
    try {
        const [vizRes, quizRes, engRes, heatmapRes] = await Promise.all([
            api.get('/learning/visualization/student-progress/'),
            api.get('/learning/visualization/quiz-analytics/'),
            api.get('/learning/visualization/engagement/'),
            api.get('/learning/visualization/skill-heatmap/'),
        ]);
        vizData.value = vizRes.data;
        quizData.value = quizRes.data;
        engagementData.value = engRes.data;
        skillHeatmap.value = heatmapRes.data;
    } catch (e) { /* silent */ }
};

const selectClass = async (classId) => {
    selectedClassId.value = classId;
    await fetchClassDetail(classId);
};

const riskBadge = (level) => {
    return level === 'HIGH' ? '🔴' : '🟠';
};

const statCards = computed(() => {
    if (!dashboard.value) return [];
    return [
        { label: '전체 학생', value: dashboard.value.total_students, icon: '👥', color: '#4facfe' },
        { label: '평균 퀴즈', value: `${dashboard.value.avg_quiz_score}점`, icon: '📝', color: '#00f260' },
        { label: '이탈 위험', value: dashboard.value.at_risk_count, icon: '⚠️', color: '#ff5555' },
        { label: '스킬 완성률', value: `${dashboard.value.skill_completion_rate}%`, icon: '🏆', color: '#fbc531' },
    ];
});

onMounted(fetchDashboard);
</script>

<template>
    <div class="manager-view">
        <header class="mv-header">
            <div>
                <button class="back-btn" @click="router.push('/')">← 강의실 목록</button>
                <h1>📊 학생 관리 대시보드</h1>
                <p class="subtitle" v-if="dashboard">{{ dashboard.generated_at?.slice(0,10) }} 기준</p>
            </div>
        </header>

        <div v-if="isLoading" class="loading">
            <p>⏳ 데이터를 불러오는 중...</p>
        </div>

        <template v-else-if="dashboard">
            <!-- Stats Cards -->
            <div class="stat-cards">
                <div v-for="stat in statCards" :key="stat.label" class="stat-card">
                    <span class="stat-icon">{{ stat.icon }}</span>
                    <div>
                        <div class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</div>
                        <div class="stat-label">{{ stat.label }}</div>
                    </div>
                </div>
            </div>

            <!-- Tabs -->
            <div class="tabs">
                <button :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">📋 클래스 현황</button>
                <button :class="{ active: activeTab === 'students' }" @click="activeTab = 'students'">👥 학생 관리</button>
                <button :class="{ active: activeTab === 'risk' }" @click="activeTab = 'risk'">⚠️ 이탈 위험</button>
                <button :class="{ active: activeTab === 'analytics' }" @click="activeTab = 'analytics'">📈 성적 분석</button>
            </div>

            <!-- Tab: Overview -->
            <div v-if="activeTab === 'overview'" class="tab-content">
                <div class="class-selector" v-if="dashboard.classes.length > 0">
                    <h3>클래스 목록</h3>
                    <div class="class-list">
                        <div v-for="cls in dashboard.classes" :key="cls.id"
                            class="class-item"
                            :class="{ active: selectedClassId === cls.id }"
                            @click="selectClass(cls.id)">
                            <div class="class-name">{{ cls.name }}</div>
                            <div class="class-meta">
                                <span>👥 {{ cls.student_count }}명</span>
                                <span>📊 평균 {{ cls.avg_score }}점</span>
                            </div>
                            <div class="class-period">{{ cls.start_date }} ~ {{ cls.end_date }}</div>
                        </div>
                    </div>
                </div>

                <div class="lecture-list-section" v-if="dashboard.lectures.length > 0">
                    <h3>내 강의 목록</h3>
                    <div class="lecture-items">
                        <div v-for="lec in dashboard.lectures" :key="lec.id" class="lecture-item" @click="router.push(`/lecture/${lec.id}`)">
                            <div class="lec-title">{{ lec.title }}</div>
                            <div class="lec-meta">
                                <span class="lec-code">{{ lec.access_code }}</span>
                                <span>👥 {{ lec.student_count }}명</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Students -->
            <div v-if="activeTab === 'students' && classDetail" class="tab-content">
                <h3>{{ classDetail.class_name }} — 학생 현황 ({{ classDetail.total_students }}명)</h3>
                <div class="student-table">
                    <div class="table-header">
                        <span>이름</span>
                        <span>평균점수</span>
                        <span>스킬블록</span>
                        <span>마지막 활동</span>
                        <span>상태</span>
                    </div>
                    <div v-for="s in classDetail.students" :key="s.student_id" class="table-row" :class="{ 'at-risk': s.is_at_risk }">
                        <span class="student-name">{{ s.nickname }}</span>
                        <span>{{ s.avg_quiz_score }}점</span>
                        <span>{{ s.skill_blocks_earned }}/{{ s.skill_blocks_total }}</span>
                        <span class="last-active">{{ s.last_active ? s.last_active.slice(0,10) : '없음' }}</span>
                        <span>
                            <span v-if="s.is_at_risk" class="risk-badge">🔴 위험</span>
                            <span v-else class="ok-badge">🟢 정상</span>
                        </span>
                    </div>
                </div>
            </div>

            <!-- Tab: At-Risk -->
            <div v-if="activeTab === 'risk'" class="tab-content">
                <h3>⚠️ 이탈 위험 학생 ({{ atRiskStudents.length }}명)</h3>
                <div v-if="atRiskStudents.length === 0" class="empty-state">
                    <p>🎉 이탈 위험 학생이 없습니다!</p>
                </div>
                <div v-else class="risk-list">
                    <div v-for="s in atRiskStudents" :key="s.student_id" class="risk-card">
                        <div class="risk-header">
                            <span class="risk-name">{{ riskBadge(s.risk_level) }} {{ s.nickname }}</span>
                            <span class="risk-level" :class="s.risk_level">{{ s.risk_level }}</span>
                        </div>
                        <div class="risk-details">
                            <span>📅 {{ s.days_inactive }}일 미접속</span>
                            <span>📊 최근 평균 {{ s.recent_avg_score }}점</span>
                        </div>
                        <div class="risk-factors">
                            <span v-for="(f, i) in s.risk_factors" :key="i" class="factor-tag">{{ f }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Analytics -->
            <div v-if="activeTab === 'analytics'" class="tab-content">
                <div class="analytics-grid">
                    <!-- Quiz Distribution -->
                    <div class="analytics-card" v-if="quizData">
                        <h4>📝 점수 분포</h4>
                        <div class="bar-chart">
                            <div v-for="(count, idx) in quizData.score_distribution?.data" :key="idx" class="bar-item">
                                <div class="bar"
                                    :style="{ height: Math.max(4, count * 3) + 'px', background: barColor(idx) }">
                                </div>
                                <span class="bar-label">{{ quizData.score_distribution?.labels[idx] }}</span>
                                <span class="bar-val">{{ count }}</span>
                            </div>
                        </div>
                        <div class="stats-row">
                            <span>통과율: <strong>{{ quizData.pass_rate }}%</strong></span>
                            <span>총 응시: <strong>{{ quizData.total_attempts }}회</strong></span>
                        </div>
                    </div>

                    <!-- Engagement -->
                    <div class="analytics-card" v-if="engagementData">
                        <h4>📈 참여도 트렌드 ({{ engagementData.period_days }}일)</h4>
                        <div class="engagement-chart">
                            <div v-for="d in engagementData.daily_engagement" :key="d.date" class="eng-bar-item">
                                <div class="eng-bar"
                                    :style="{ height: Math.max(2, d.engagement_rate) + 'px' }">
                                </div>
                                <span class="eng-label">{{ d.date.slice(5) }}</span>
                            </div>
                        </div>
                        <div class="stats-row">
                            <span>전체 학생: <strong>{{ engagementData.total_students }}명</strong></span>
                        </div>
                    </div>

                    <!-- Student Rankings -->
                    <div class="analytics-card wide" v-if="quizData?.student_rankings">
                        <h4>🏆 퀴즈 순위 (Top 20)</h4>
                        <div class="ranking-list">
                            <div v-for="(s, idx) in quizData.student_rankings" :key="idx" class="ranking-item">
                                <span class="rank">{{ idx + 1 }}</span>
                                <span class="rank-name">{{ s.student__username }}</span>
                                <span class="rank-score">{{ s.avg_score?.toFixed(1) }}점</span>
                                <span class="rank-count">{{ s.attempt_count }}회</span>
                            </div>
                        </div>
                    </div>

                    <!-- Skill Heatmap -->
                    <div class="analytics-card wide" v-if="skillHeatmap?.categories">
                        <h4>🔥 스킬 히트맵</h4>
                        <div v-for="cat in skillHeatmap.categories" :key="cat.category" class="heatmap-category">
                            <div class="heatmap-cat-name">{{ cat.category }}</div>
                            <div class="heatmap-blocks">
                                <div v-for="skill in cat.skills" :key="skill.name" class="heatmap-block"
                                    :style="{ background: `rgba(79,172,254,${Math.max(0.1, skill.acquisition_rate / 100)})` }"
                                    :title="`${skill.name}: ${skill.acquired}/${skill.total} (${skill.acquisition_rate}%)`">
                                    <span class="heatmap-name">{{ skill.name }}</span>
                                    <span class="heatmap-rate">{{ skill.acquisition_rate }}%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>

<script>
export default {
    methods: {
        barColor(idx) {
            const colors = ['#ff5555', '#ff9040', '#fbc531', '#4facfe', '#00f260'];
            return colors[idx] || '#4facfe';
        }
    }
}
</script>

<style scoped>
.manager-view { padding: 30px; max-width: 1200px; margin: 0 auto; min-height: 100vh; }
.mv-header { margin-bottom: 30px; }
.mv-header h1 { font-size: 28px; margin: 8px 0 4px; color: #333; }
.mv-header .subtitle { color: #636b72; font-size: 13px; }
.back-btn { background: none; border: none; color: #4facfe; cursor: pointer; font-size: 14px; padding: 0; }
.back-btn:hover { text-decoration: underline; }

.loading { text-align: center; padding: 60px; color: #636b72; }

/* Stat Cards */
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card {
    background: #fff; border: 1px solid #eee; border-radius: 12px;
    padding: 20px; display: flex; align-items: center; gap: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.stat-icon { font-size: 32px; }
.stat-value { font-size: 28px; font-weight: 800; }
.stat-label { color: #636b72; font-size: 13px; margin-top: 2px; }

/* Tabs */
.tabs { display: flex; gap: 4px; margin-bottom: 24px; background: #f5f5f5; border-radius: 8px; padding: 4px; }
.tabs button {
    flex: 1; padding: 10px; border: none; background: none;
    border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; color: #636b72;
    transition: all 0.2s;
}
.tabs button.active { background: #fff; color: #333; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

.tab-content { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

h3 { color: #333; margin-bottom: 16px; font-size: 18px; }

/* Class Selector */
.class-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin-bottom: 32px; }
.class-item {
    background: #fff; border: 2px solid #eee; border-radius: 12px;
    padding: 16px; cursor: pointer; transition: all 0.2s;
}
.class-item:hover { border-color: #4facfe; transform: translateY(-2px); }
.class-item.active { border-color: #4facfe; background: #f0f7ff; }
.class-name { font-weight: 700; font-size: 16px; color: #333; margin-bottom: 8px; }
.class-meta { display: flex; gap: 12px; font-size: 13px; color: #636b72; margin-bottom: 4px; }
.class-period { font-size: 12px; color: #6e6e6e; }

/* Lecture List */
.lecture-items { display: flex; flex-direction: column; gap: 8px; }
.lecture-item {
    background: #fff; border: 1px solid #eee; border-radius: 10px;
    padding: 14px 18px; cursor: pointer; transition: all 0.2s;
    display: flex; justify-content: space-between; align-items: center;
}
.lecture-item:hover { border-color: #4facfe; background: #fafcff; }
.lec-title { font-weight: 600; color: #333; }
.lec-meta { display: flex; gap: 12px; font-size: 13px; color: #636b72; }
.lec-code { background: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }

/* Student Table */
.student-table { background: #fff; border-radius: 12px; border: 1px solid #eee; overflow: hidden; }
.table-header {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
    padding: 12px 18px; background: #f8f9fa; font-weight: 600;
    font-size: 13px; color: #636b72; border-bottom: 1px solid #eee;
}
.table-row {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
    padding: 12px 18px; font-size: 14px; border-bottom: 1px solid #f0f0f0;
    transition: background 0.2s;
}
.table-row:hover { background: #f8f9fa; }
.table-row.at-risk { background: #fff5f5; }
.student-name { font-weight: 600; color: #333; }
.last-active { color: #636b72; font-size: 13px; }
.risk-badge { background: #ffebee; color: #d32f2f; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.ok-badge { background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }

/* Risk List */
.risk-list { display: flex; flex-direction: column; gap: 12px; }
.risk-card {
    background: #fff; border: 1px solid #ffcdd2; border-left: 4px solid #f44336;
    border-radius: 10px; padding: 16px;
}
.risk-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.risk-name { font-weight: 700; font-size: 16px; }
.risk-level { font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.risk-level.HIGH { background: #ffebee; color: #d32f2f; }
.risk-level.MEDIUM { background: #fff3e0; color: #e65100; }
.risk-details { display: flex; gap: 16px; font-size: 13px; color: #636b72; margin-bottom: 8px; }
.risk-factors { display: flex; gap: 6px; flex-wrap: wrap; }
.factor-tag { font-size: 11px; background: #fce4ec; color: #c62828; padding: 2px 8px; border-radius: 10px; }

.empty-state { text-align: center; padding: 40px; color: #636b72; }

/* Analytics */
.analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.analytics-card {
    background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 20px;
    &.wide { grid-column: 1 / -1; }
}
.analytics-card h4 { margin: 0 0 16px; font-size: 16px; color: #333; }

.bar-chart { display: flex; align-items: flex-end; gap: 12px; height: 120px; margin-bottom: 12px; }
.bar-item { display: flex; flex-direction: column; align-items: center; flex: 1; }
.bar { width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; transition: height 0.3s; }
.bar-label { font-size: 11px; color: #636b72; margin-top: 6px; }
.bar-val { font-size: 12px; font-weight: 700; color: #333; }

.engagement-chart { display: flex; align-items: flex-end; gap: 4px; height: 80px; margin-bottom: 12px; overflow-x: auto; }
.eng-bar-item { display: flex; flex-direction: column; align-items: center; min-width: 20px; }
.eng-bar { width: 16px; background: #4facfe; border-radius: 3px 3px 0 0; min-height: 2px; }
.eng-label { font-size: 9px; color: #6e6e6e; margin-top: 4px; }

.stats-row { display: flex; gap: 16px; font-size: 13px; color: #636b72; }
.stats-row strong { color: #333; }

.ranking-list { max-height: 400px; overflow-y: auto; }
.ranking-item {
    display: grid; grid-template-columns: 40px 2fr 1fr 1fr;
    padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px;
}
.rank { font-weight: 800; color: #4facfe; }
.rank-name { font-weight: 500; color: #333; }
.rank-score { color: #00f260; font-weight: 700; }
.rank-count { color: #636b72; font-size: 12px; }

/* Skill Heatmap */
.heatmap-category { margin-bottom: 16px; }
.heatmap-cat-name { font-weight: 600; font-size: 14px; color: #555; margin-bottom: 8px; }
.heatmap-blocks { display: flex; flex-wrap: wrap; gap: 6px; }
.heatmap-block {
    padding: 6px 10px; border-radius: 6px; font-size: 12px;
    display: flex; flex-direction: column; align-items: center; gap: 2px;
    cursor: default; min-width: 60px;
}
.heatmap-name { font-weight: 500; color: #fff; font-size: 11px; }
.heatmap-rate { font-weight: 700; color: #fff; font-size: 13px; }

@media (max-width: 768px) {
    .stat-cards { grid-template-columns: repeat(2, 1fr); }
    .analytics-grid { grid-template-columns: 1fr; }
    .table-header, .table-row { grid-template-columns: 1.5fr 1fr 1fr 1fr; }
}
</style>
