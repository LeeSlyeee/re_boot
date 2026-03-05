<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';
import { useToast } from '../composables/useToast';
const { showToast } = useToast();

const router = useRouter();
const activeTab = ref('placement');
const isLoading = ref(false);

// ─── 수준 진단 (Placement) ───
const placementQuestions = ref([]);
const placementAnswers = ref({});
const placementResult = ref(null);
const placementSubmitting = ref(false);
const hasExistingResult = ref(false);

const fetchPlacement = async () => {
  // 기존 결과 확인
  try {
    const { data } = await api.get('/learning/placement/my-result/');
    if (data && data.level) {
      placementResult.value = data;
      hasExistingResult.value = true;
    }
  } catch (e) { /* 결과 없음 */ }

  // 문항 로드
  try {
    const { data } = await api.get('/learning/placement/questions/');
    placementQuestions.value = data.questions || data || [];
  } catch (e) { /* silent */ }
};

const submitPlacement = async () => {
  if (Object.keys(placementAnswers.value).length < placementQuestions.value.length) {
    showToast('모든 문항에 답변해주세요.', 'error');
    return;
  }
  placementSubmitting.value = true;
  try {
    const { data } = await api.post('/learning/placement/submit/', { answers: placementAnswers.value });
    placementResult.value = data;
    hasExistingResult.value = true;
  } catch (e) { showToast('제출 실패: ' + (e.response?.data?.error || e.message, 'error')); }
  placementSubmitting.value = false;
};

const retakePlacement = () => {
  placementResult.value = null;
  hasExistingResult.value = false;
  placementAnswers.value = {};
};

const levelBadge = computed(() => {
  if (!placementResult.value) return {};
  const m = { 1: { label: 'Level 1 — 기초', color: '#43e97b', emoji: '🌱' },
              2: { label: 'Level 2 — 표준', color: '#4facfe', emoji: '📘' },
              3: { label: 'Level 3 — 심화', color: '#a78bfa', emoji: '🚀' } };
  return m[placementResult.value.level] || m[2];
});

// ─── 목표 설정 (Goal) ───
const careers = ref([]);
const myGoal = ref(null);
const showCustomGoal = ref(false);
const customGoalForm = ref({ title: '', description: '', icon: '🎯', estimated_weeks: 12, skills: '' });

const fetchGoals = async () => {
  try {
    const [careersRes, goalRes] = await Promise.all([
      api.get('/learning/goals/careers/'),
      api.get('/learning/goals/my-goal/')
    ]);
    careers.value = careersRes.data.careers || careersRes.data || [];
    // API가 { career_goal: {...}, custom_goal_text } 형태로 응답
    const goalData = goalRes.data;
    if (goalData?.has_goal && goalData.career_goal) {
      myGoal.value = {
        ...goalData.career_goal,
        custom_goal_text: goalData.custom_goal_text,
        required_skills: (goalData.career_goal.required_skills || []).map(s => typeof s === 'string' ? s : s.name),
      };
    } else if (goalData?.goal) {
      myGoal.value = goalData.goal;
    } else {
      myGoal.value = null;
    }
  } catch (e) { /* silent */ }
};

const setGoal = async (careerGoalId) => {
  try {
    const { data } = await api.post('/learning/goals/set/', { career_goal_id: careerGoalId });
    myGoal.value = data.goal || data;
    showToast('목표가 설정되었습니다!', 'success');
  } catch (e) { showToast('목표 설정 실패', 'error'); }
};

const createCustomGoal = async () => {
  if (!customGoalForm.value.title) return;
  try {
    const payload = {
      ...customGoalForm.value,
      skills: customGoalForm.value.skills.split(',').map(s => s.trim()).filter(Boolean),
    };
    const { data } = await api.post('/learning/goals/create-custom/', payload);
    myGoal.value = data.goal || data;
    showCustomGoal.value = false;
    showToast('커스텀 목표가 설정되었습니다!', 'success');
  } catch (e) { showToast('생성 실패', 'error'); }
};

// ─── 갭맵 (Gap Map) ───
const gapMap = ref(null);

const fetchGapMap = async () => {
  try {
    const { data } = await api.get('/learning/gapmap/my-map/');
    // API가 { categories: { "카테고리": [...] }, stats: {...} } 형태로 응답
    // flat list로 변환
    if (data?.categories) {
      const flatSkills = [];
      for (const [cat, skills] of Object.entries(data.categories)) {
        skills.forEach(s => flatSkills.push({ ...s, category: cat }));
      }
      gapMap.value = { skills: flatSkills, stats: data.stats };
    } else {
      gapMap.value = data;
    }
  } catch (e) { /* silent */ }
};

const gapStats = computed(() => {
  if (!gapMap.value?.skills) return { owned: 0, learning: 0, gap: 0, total: 0, rate: 0 };
  const skills = gapMap.value.skills;
  const owned = skills.filter(s => s.status === 'OWNED').length;
  const learning = skills.filter(s => s.status === 'LEARNING').length;
  const gap = skills.filter(s => s.status === 'GAP').length;
  const total = skills.length;
  return { owned, learning, gap, total, rate: total > 0 ? Math.round((owned / total) * 100) : 0 };
});

// ─── 체크리스트 ───
const checklist = ref([]);
const analysisResult = ref(null);
const recoveryPlan = ref(null);

const fetchChecklist = async () => {
  try {
    const { data } = await api.get('/learning/checklist/');
    checklist.value = data.items || data || [];
  } catch (e) { /* silent */ }
};

const toggleCheckItem = async (itemId) => {
  try {
    const { data } = await api.post(`/learning/checklist/${itemId}/toggle/`);
    const item = checklist.value.find(i => i.id === itemId);
    if (item) item.is_checked = data.is_checked;
  } catch (e) { /* silent */ }
};

const analyzeChecklist = async () => {
  try {
    const { data } = await api.get('/learning/checklist/analyze/');
    analysisResult.value = data;
  } catch (e) { showToast('분석 실패', 'error'); }
};

const getRecoveryPlan = async () => {
  try {
    const { data } = await api.post('/learning/checklist/recovery_plan/');
    recoveryPlan.value = data;
  } catch (e) { showToast('복구 플랜 생성 실패', 'error'); }
};

const checklistProgress = computed(() => {
  if (!checklist.value.length) return 0;
  const checked = checklist.value.filter(i => i.is_checked).length;
  return Math.round((checked / checklist.value.length) * 100);
});

// ─── 수료증 ───
const certData = ref(null);
const certLectureId = ref(null);

const fetchCertificate = async (lectureId) => {
  if (!lectureId) return;
  try {
    const { data } = await api.get(`/learning/certificate/${lectureId}/`);
    certData.value = data;
  } catch (e) { certData.value = null; }
};

// ─── 탭 전환 시 데이터 로드 ───
const switchTab = (tab) => {
  activeTab.value = tab;
  if (tab === 'placement' && !placementQuestions.value.length) fetchPlacement();
  if (tab === 'goal') fetchGoals();
  if (tab === 'gapmap') fetchGapMap();
  if (tab === 'checklist') fetchChecklist();
};

// ─── 마운트 ───
onMounted(() => {
  fetchPlacement();
  fetchGoals();
});
</script>

<template>
  <div class="onboarding-view">
    <header class="ob-header">
      <h1>🎓 학습 온보딩 센터</h1>
      <p class="ob-subtitle">수준 진단부터 수료까지, 맞춤 학습 경로를 설계하세요.</p>
    </header>

    <!-- Tabs -->
    <nav class="ob-tabs">
      <button :class="{ active: activeTab === 'placement' }" @click="switchTab('placement')">📋 수준 진단</button>
      <button :class="{ active: activeTab === 'goal' }" @click="switchTab('goal')">🎯 목표 설정</button>
      <button :class="{ active: activeTab === 'gapmap' }" @click="switchTab('gapmap')">🗺️ 갭 맵</button>
      <button :class="{ active: activeTab === 'checklist' }" @click="switchTab('checklist')">✅ 체크리스트</button>
      <button :class="{ active: activeTab === 'certificate' }" @click="switchTab('certificate')">🏅 수료증</button>
    </nav>

    <!-- Tab Content -->
    <div class="ob-content">
      <!-- ═══════════════ 수준 진단 ═══════════════ -->
      <div v-if="activeTab === 'placement'" class="tab-panel">
        <!-- 결과 표시 -->
        <div v-if="hasExistingResult && placementResult" class="placement-result glass-panel">
          <div class="result-header">
            <span class="result-emoji">{{ levelBadge.emoji }}</span>
            <div>
              <h2>{{ levelBadge.label }}</h2>
              <p>점수: <strong>{{ placementResult.score }}</strong> / {{ placementResult.total }}</p>
            </div>
          </div>
          <div class="result-details" v-if="placementResult.category_scores">
            <div v-for="(score, cat) in placementResult.category_scores" :key="cat" class="cat-score">
              <span class="cat-name">{{ cat }}</span>
              <div class="cat-bar"><div class="cat-fill" :style="{ width: score + '%', background: levelBadge.color }"></div></div>
              <span class="cat-pct">{{ score }}%</span>
            </div>
          </div>
          <button class="btn-outline" @click="retakePlacement">다시 진단 받기</button>
        </div>

        <!-- 문항 풀기 -->
        <div v-else>
          <div class="quiz-intro glass-panel" v-if="placementQuestions.length > 0">
            <h2>📋 수준 진단 테스트</h2>
            <p>{{ placementQuestions.length }}문항 · 약 5분 소요</p>
          </div>
          <div v-for="q in placementQuestions" :key="q.id" class="quiz-card glass-panel">
            <h3>Q{{ q.order || q.id }}. {{ q.question_text }}</h3>
            <div class="options">
              <label v-for="(opt, idx) in q.options" :key="idx"
                class="option-label" :class="{ selected: placementAnswers[q.id] === opt }">
                <input type="radio" :name="'pq-' + q.id" :value="opt" v-model="placementAnswers[q.id]" />
                {{ opt }}
              </label>
            </div>
          </div>
          <button v-if="placementQuestions.length > 0" class="btn-primary submit-btn"
            @click="submitPlacement" :disabled="placementSubmitting">
            {{ placementSubmitting ? '제출 중...' : '✅ 진단 결과 확인' }}
          </button>
          <div v-else class="empty-msg glass-panel">
            <p>진단 문항이 아직 등록되지 않았습니다.</p>
          </div>
        </div>
      </div>

      <!-- ═══════════════ 목표 설정 ═══════════════ -->
      <div v-if="activeTab === 'goal'" class="tab-panel">
        <!-- 현재 목표 -->
        <div v-if="myGoal" class="my-goal glass-panel">
          <h2>🎯 내 목표</h2>
          <div class="goal-card-main">
            <span class="goal-icon-lg">{{ myGoal.icon || '🎯' }}</span>
            <div>
              <h3>{{ myGoal.title }}</h3>
              <p>{{ myGoal.description }}</p>
              <div class="goal-meta">
                <span>📅 예상 {{ myGoal.estimated_weeks }}주</span>
                <span v-if="myGoal.required_skills?.length">🔧 {{ myGoal.required_skills.map(s => typeof s === 'string' ? s : s.name).join(', ') }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 직무 목록 -->
        <h2 class="section-title">직무 목록에서 선택</h2>
        <div class="career-grid">
          <div v-for="career in careers" :key="career.id" class="career-card glass-panel"
            :class="{ selected: myGoal?.career_goal_id === career.id }">
            <span class="career-icon">{{ career.icon || '💼' }}</span>
            <h4>{{ career.title }}</h4>
            <p>{{ career.description }}</p>
            <div class="career-skills" v-if="career.required_skills">
              <span v-for="s in career.required_skills.slice(0, 4)" :key="s.id || s" class="skill-chip">{{ typeof s === 'string' ? s : s.name }}</span>
            </div>
            <button class="btn-sm select-btn" @click="setGoal(career.id)">선택</button>
          </div>
        </div>

        <!-- 커스텀 목표 -->
        <div class="custom-section">
          <button class="btn-outline" @click="showCustomGoal = !showCustomGoal">
            {{ showCustomGoal ? '접기' : '➕ 직접 목표 만들기' }}
          </button>
          <div v-if="showCustomGoal" class="custom-form glass-panel">
            <input v-model="customGoalForm.title" placeholder="직무명 (예: AI 엔지니어)" />
            <textarea v-model="customGoalForm.description" placeholder="설명" rows="2"></textarea>
            <input v-model="customGoalForm.skills" placeholder="필요 스킬 (쉼표 구분)" />
            <input v-model.number="customGoalForm.estimated_weeks" type="number" placeholder="예상 기간(주)" />
            <button class="btn-primary" @click="createCustomGoal">생성 & 설정</button>
          </div>
        </div>
      </div>

      <!-- ═══════════════ 갭 맵 ═══════════════ -->
      <div v-if="activeTab === 'gapmap'" class="tab-panel">
        <div v-if="gapMap" class="gapmap-section">
          <div class="gapmap-stats glass-panel">
            <h2>🗺️ 나의 갭 맵</h2>
            <div class="stat-row">
              <div class="gm-stat owned"><span>{{ gapStats.owned }}</span> 보유</div>
              <div class="gm-stat learning"><span>{{ gapStats.learning }}</span> 학습중</div>
              <div class="gm-stat gap"><span>{{ gapStats.gap }}</span> 미보유</div>
              <div class="gm-stat rate"><span>{{ gapStats.rate }}%</span> 달성률</div>
            </div>
          </div>

          <div class="skill-list">
            <div v-for="skill in gapMap.skills" :key="skill.skill_id || skill.name"
              class="skill-item glass-panel" :class="skill.status.toLowerCase()">
              <span class="skill-status-icon">
                {{ skill.status === 'OWNED' ? '✅' : skill.status === 'LEARNING' ? '📖' : '❌' }}
              </span>
              <div>
                <h4>{{ skill.name }}</h4>
                <div class="skill-progress-bar" v-if="skill.status !== 'OWNED'">
                  <div class="skill-fill" :style="{ width: (skill.progress || 0) + '%' }"></div>
                </div>
                <span class="skill-status-label">{{ skill.status }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-msg glass-panel">
          <p>목표를 먼저 설정하면 갭 맵이 생성됩니다.</p>
          <button class="btn-primary" @click="switchTab('goal')">목표 설정하러 가기 →</button>
        </div>
      </div>

      <!-- ═══════════════ 체크리스트 ═══════════════ -->
      <div v-if="activeTab === 'checklist'" class="tab-panel">
        <div class="checklist-header glass-panel">
          <h2>✅ 학습 체크리스트</h2>
          <div class="cl-progress">
            <div class="cl-bar"><div class="cl-fill" :style="{ width: checklistProgress + '%' }"></div></div>
            <span>{{ checklistProgress }}%</span>
          </div>
          <div class="cl-actions">
            <button class="btn-outline" @click="analyzeChecklist">📊 달성률 분석</button>
            <button class="btn-outline danger" @click="getRecoveryPlan">🚑 복구 플랜</button>
          </div>
        </div>

        <!-- 분석 결과 -->
        <div v-if="analysisResult" class="analysis-result glass-panel">
          <h3>📊 분석 결과</h3>
          <p>전체 달성률: <strong>{{ analysisResult.completion_rate || analysisResult.rate }}%</strong></p>
          <p v-if="analysisResult.status" :class="'status-' + analysisResult.status.toLowerCase()">
            상태: {{ analysisResult.status }}
          </p>
        </div>

        <!-- 복구 플랜 -->
        <div v-if="recoveryPlan" class="recovery-plan glass-panel">
          <h3>🚑 AI 복구 플랜</h3>
          <div class="recovery-content" v-html="recoveryPlan.plan || recoveryPlan.content || ''"></div>
        </div>

        <!-- 체크리스트 항목 -->
        <div class="cl-items">
          <div v-for="item in checklist" :key="item.id" class="cl-item"
            :class="{ checked: item.is_checked }" @click="toggleCheckItem(item.id)">
            <span class="cl-check">{{ item.is_checked ? '☑️' : '⬜' }}</span>
            <div>
              <span class="cl-text">{{ item.content || item.objective_content }}</span>
              <span class="cl-week" v-if="item.week">{{ item.week }}주차</span>
            </div>
          </div>
        </div>
        <div v-if="!checklist.length" class="empty-msg glass-panel">
          <p>강의에 등록하면 학습 체크리스트가 자동으로 생성됩니다.</p>
        </div>
      </div>

      <!-- ═══════════════ 수료증 ═══════════════ -->
      <div v-if="activeTab === 'certificate'" class="tab-panel">
        <div class="cert-section glass-panel">
          <h2>🏅 수료증 발급</h2>
          <p class="cert-desc">수강 중인 강의를 선택하여 수료 자격을 확인하세요.</p>
          <div class="cert-input">
            <input v-model.number="certLectureId" placeholder="강의 ID 입력" type="number" />
            <button class="btn-primary" @click="fetchCertificate(certLectureId)">조회</button>
          </div>

          <div v-if="certData" class="cert-result">
            <div v-if="certData.eligible" class="cert-card eligible">
              <div class="cert-badge">🏅</div>
              <h3>수료 자격 충족!</h3>
              <p>{{ certData.lecture_title }}</p>
              <p>완료율: {{ certData.completion_rate }}%</p>
              <p>발급일: {{ certData.issued_at || '지금' }}</p>
            </div>
            <div v-else class="cert-card not-eligible">
              <div class="cert-badge">📝</div>
              <h3>수료까지 조금 더!</h3>
              <p>현재 완료율: {{ certData.completion_rate }}%</p>
              <p v-if="certData.remaining">남은 항목: {{ certData.remaining }}건</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.onboarding-view { max-width: 900px; margin: 0 auto; padding: 30px 20px; min-height: 100vh; }
.ob-header { text-align: center; margin-bottom: 24px; }
.ob-header h1 { font-size: 28px; margin: 0; color: #eee; }
.ob-subtitle { color: #888; font-size: 14px; margin-top: 6px; }

.ob-tabs {
  display: flex; gap: 4px; background: rgba(255,255,255,0.04); border-radius: 10px; padding: 4px; margin-bottom: 24px;
  button {
    flex: 1; padding: 10px 8px; border: none; background: none; border-radius: 8px;
    color: #888; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s;
    &.active { background: rgba(79,172,254,0.15); color: #4facfe; }
    &:hover:not(.active) { background: rgba(255,255,255,0.04); }
  }
}

.tab-panel { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

.glass-panel {
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; padding: 20px;
}

/* ─── Placement ─── */
.placement-result { text-align: center; }
.result-header { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 20px; }
.result-emoji { font-size: 48px; }
.result-header h2 { margin: 0; font-size: 22px; color: #eee; }
.result-details { margin: 16px 0 20px; }
.cat-score { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.cat-name { width: 100px; text-align: right; font-size: 13px; color: #aaa; }
.cat-bar { flex: 1; height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.cat-fill { height: 100%; border-radius: 4px; transition: width 0.4s; }
.cat-pct { width: 40px; font-size: 13px; color: #ddd; font-weight: 700; }

.quiz-intro { text-align: center; margin-bottom: 16px; }
.quiz-intro h2 { margin: 0 0 4px; font-size: 20px; color: #eee; }
.quiz-intro p { color: #888; font-size: 14px; margin: 0; }

.quiz-card { margin-bottom: 12px; }
.quiz-card h3 { font-size: 15px; color: #ddd; margin: 0 0 12px; }
.options { display: flex; flex-direction: column; gap: 6px; }
.option-label {
  padding: 10px 14px; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
  cursor: pointer; font-size: 14px; color: #ccc; transition: all 0.2s;
  input { display: none; }
  &.selected { border-color: #4facfe; background: rgba(79,172,254,0.1); color: #fff; }
  &:hover:not(.selected) { border-color: rgba(255,255,255,0.2); }
}

.submit-btn { width: 100%; margin-top: 16px; }
.btn-primary {
  padding: 12px 24px; border: none; border-radius: 10px; font-size: 15px; font-weight: 700;
  background: linear-gradient(135deg, #4facfe, #00f2fe); color: #fff; cursor: pointer;
  transition: all 0.2s;
  &:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(79,172,254,0.3); }
  &:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
}
.btn-outline {
  padding: 8px 16px; border: 1px solid rgba(79,172,254,0.3); background: none;
  color: #4facfe; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600;
  &:hover { background: rgba(79,172,254,0.1); }
  &.danger { border-color: rgba(255,85,85,0.3); color: #ff5555; &:hover { background: rgba(255,85,85,0.1); } }
}
.btn-sm { padding: 6px 14px; border: none; border-radius: 6px; background: rgba(79,172,254,0.15); color: #4facfe; cursor: pointer; font-size: 12px; font-weight: 600; }

.empty-msg { text-align: center; padding: 40px; color: #666; }

/* ─── Goal ─── */
.my-goal { margin-bottom: 24px; }
.my-goal h2 { margin: 0 0 12px; font-size: 18px; color: #eee; }
.goal-card-main { display: flex; align-items: center; gap: 16px; }
.goal-icon-lg { font-size: 40px; }
.goal-card-main h3 { margin: 0; font-size: 18px; color: #eee; }
.goal-card-main p { margin: 4px 0 0; font-size: 14px; color: #aaa; }
.goal-meta { display: flex; gap: 12px; font-size: 12px; color: #888; margin-top: 6px; }

.section-title { font-size: 18px; color: #ddd; margin: 0 0 12px; }

.career-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-bottom: 24px; }
.career-card {
  text-align: center; transition: all 0.2s;
  &:hover { border-color: rgba(79,172,254,0.3); transform: translateY(-2px); }
  &.selected { border-color: #4facfe; background: rgba(79,172,254,0.06); }
}
.career-icon { font-size: 32px; display: block; margin-bottom: 8px; }
.career-card h4 { margin: 0 0 4px; font-size: 16px; color: #eee; }
.career-card p { font-size: 13px; color: #999; margin: 0 0 8px; }
.career-skills { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; margin-bottom: 10px; }
.skill-chip { font-size: 11px; padding: 2px 8px; background: rgba(79,172,254,0.1); color: #4facfe; border-radius: 4px; }
.select-btn { margin: 0 auto; display: block; }

.custom-section { margin-top: 16px; }
.custom-form {
  margin-top: 12px; display: flex; flex-direction: column; gap: 10px;
  input, textarea { padding: 10px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: #eee; font-size: 14px; }
}

/* ─── Gap Map ─── */
.gapmap-stats { margin-bottom: 20px; }
.gapmap-stats h2 { margin: 0 0 16px; font-size: 18px; color: #eee; }
.stat-row { display: flex; gap: 12px; }
.gm-stat {
  flex: 1; text-align: center; padding: 12px; border-radius: 10px;
  span { display: block; font-size: 24px; font-weight: 800; }
  font-size: 12px; color: #aaa;
  &.owned { background: rgba(67,233,123,0.1); span { color: #43e97b; } }
  &.learning { background: rgba(79,172,254,0.1); span { color: #4facfe; } }
  &.gap { background: rgba(255,85,85,0.1); span { color: #ff5555; } }
  &.rate { background: rgba(251,197,49,0.1); span { color: #fbc531; } }
}

.skill-list { display: flex; flex-direction: column; gap: 8px; }
.skill-item {
  display: flex; align-items: center; gap: 12px; padding: 14px;
  &.owned { border-left: 3px solid #43e97b; }
  &.learning { border-left: 3px solid #4facfe; }
  &.gap { border-left: 3px solid #ff5555; }
}
.skill-status-icon { font-size: 20px; }
.skill-item h4 { margin: 0; font-size: 15px; color: #eee; }
.skill-progress-bar { width: 120px; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; margin-top: 4px; }
.skill-fill { height: 100%; background: #4facfe; border-radius: 3px; }
.skill-status-label { font-size: 11px; color: #888; margin-top: 2px; }

/* ─── Checklist ─── */
.checklist-header h2 { margin: 0 0 12px; font-size: 18px; color: #eee; }
.cl-progress { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.cl-bar { flex: 1; height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.cl-fill { height: 100%; background: linear-gradient(90deg, #43e97b, #38f9d7); border-radius: 4px; transition: width 0.4s; }
.cl-progress span { font-size: 14px; font-weight: 700; color: #43e97b; }
.cl-actions { display: flex; gap: 8px; }

.analysis-result, .recovery-plan { margin-top: 16px; }
.analysis-result h3, .recovery-plan h3 { margin: 0 0 8px; font-size: 16px; color: #eee; }
.status-critical { color: #ff5555; font-weight: 700; }
.status-warning { color: #fbc531; font-weight: 700; }
.status-good { color: #43e97b; font-weight: 700; }
.recovery-content { font-size: 14px; color: #ccc; line-height: 1.7; white-space: pre-wrap; }

.cl-items { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.cl-item {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px; cursor: pointer; transition: all 0.2s;
  &:hover { background: rgba(255,255,255,0.06); }
  &.checked { opacity: 0.6; .cl-text { text-decoration: line-through; } }
}
.cl-check { font-size: 18px; }
.cl-text { font-size: 14px; color: #ddd; }
.cl-week { font-size: 11px; color: #888; margin-left: 8px; }

/* ─── Certificate ─── */
.cert-section { text-align: center; }
.cert-desc { color: #888; font-size: 14px; margin: 8px 0 16px; }
.cert-input { display: flex; gap: 8px; justify-content: center; margin-bottom: 24px; }
.cert-input input { padding: 8px 16px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; color: #eee; width: 160px; text-align: center; }

.cert-card {
  display: inline-block; padding: 40px; border-radius: 16px; margin-top: 16px;
  &.eligible { background: linear-gradient(135deg, rgba(67,233,123,0.1), rgba(79,172,254,0.1)); border: 2px solid rgba(67,233,123,0.3); }
  &.not-eligible { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); }
}
.cert-badge { font-size: 48px; margin-bottom: 16px; }
.cert-card h3 { margin: 0 0 8px; font-size: 20px; color: #eee; }
.cert-card p { margin: 4px 0; font-size: 14px; color: #aaa; }

@media (max-width: 600px) {
  .ob-tabs button { font-size: 11px; padding: 8px 4px; }
  .career-grid { grid-template-columns: 1fr; }
  .stat-row { flex-wrap: wrap; }
  .gm-stat { flex: 1 1 45%; }
}
</style>
