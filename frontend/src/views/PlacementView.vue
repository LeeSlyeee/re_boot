<script setup>
import { ref, computed, onMounted } from 'vue';
import { useToast } from '../composables/useToast';
const { showToast } = useToast();
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' });
API.interceptors.request.use(c => { const t = localStorage.getItem('token'); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });

// ── 상태 ──
const step = ref('loading'); // loading → quiz → result → goal → done
const questions = ref([]);
const currentQ = ref(0);
const answers = ref({});
const result = ref(null);
const careers = ref([]);
const selectedCareer = ref(null);
const submitting = ref(false);

// ── 초기 로드 ──
onMounted(async () => {
    try {
        // 기존 진단 결과 확인
        const { data } = await API.get('/learning/placement/my-result/');
        if (data.has_result) {
            result.value = data;
            // 목표 확인
            const { data: goalData } = await API.get('/learning/goals/my-goal/');
            if (goalData.has_goal) {
                step.value = 'done';
            } else {
                await loadCareers();
                step.value = 'goal';
            }
        } else {
            // 진단 문항 로드
            const { data: qs } = await API.get('/learning/placement/questions/');
            questions.value = qs;
            step.value = 'quiz';
        }
    } catch (e) {
        console.error(e);
        step.value = 'quiz';
        const { data: qs } = await API.get('/learning/placement/questions/');
        questions.value = qs;
    }
});

const loadCareers = async () => {
    const { data } = await API.get('/learning/goals/careers/');
    careers.value = data;
};

// ── 퀴즈 ──
const progress = computed(() => {
    if (questions.value.length === 0) return 0;
    return Math.round((currentQ.value / questions.value.length) * 100);
});

const selectAnswer = (questionId, answer) => {
    answers.value[questionId] = answer;
    // 자동 다음 문항 (0.3초 딜레이)
    setTimeout(() => {
        if (currentQ.value < questions.value.length - 1) {
            currentQ.value++;
        }
    }, 300);
};

const submitQuiz = async () => {
    submitting.value = true;
    try {
        const { data } = await API.post('/learning/placement/submit/', { answers: answers.value });
        result.value = data;
        await loadCareers();
        step.value = 'result';
    } catch (e) {
        showToast('제출 실패: ' + (e.response?.data?.error || '알 수 없는 오류'), 'error');
    }
    submitting.value = false;
};

// ── 목표 설정 ──
const selectGoal = async (career) => {
    selectedCareer.value = career;
    submitting.value = true;
    try {
        await API.post('/learning/goals/set/', { career_goal_id: career.id });
        step.value = 'done';
    } catch (e) {
        showToast('목표 설정 실패', 'error');
    }
    submitting.value = false;
};

// ── 커스텀 직무 만들기 ──
const showCustomForm = ref(false);
const customCareer = ref({ title: '', description: '', icon: '🎯', estimated_weeks: 12 });
const customSkillInput = ref('');
const customSkills = ref([]);

const addCustomSkill = () => {
    const name = customSkillInput.value.trim();
    if (name && !customSkills.value.includes(name)) {
        customSkills.value.push(name);
        customSkillInput.value = '';
    }
};

const removeCustomSkill = (index) => {
    customSkills.value.splice(index, 1);
};

const submitCustomCareer = async () => {
    if (!customCareer.value.title.trim()) {
        showToast('직무명을 입력해주세요.', 'warning');
        return;
    }
    if (customSkills.value.length === 0) {
        showToast('최소 1개 이상의 스킬을 추가해주세요.', 'warning');
        return;
    }
    submitting.value = true;
    try {
        const { data } = await API.post('/learning/goals/create-custom/', {
            title: customCareer.value.title,
            description: customCareer.value.description,
            icon: customCareer.value.icon,
            estimated_weeks: customCareer.value.estimated_weeks,
            skills: customSkills.value,
        });
        result.value = result.value || {};
        showToast(data.message, 'error');
        step.value = 'done';
    } catch (e) {
        showToast('직무 생성 실패: ' + (e.response?.data?.error || e.message), 'error');
    }
    submitting.value = false;
};

const goToGapMap = () => { router.push('/gapmap'); };
const goToDashboard = () => { router.push('/dashboard'); };

const retakePlacement = async () => {
    // 기존 결과 초기화하고 다시 문항 로드
    result.value = null;
    answers.value = {};
    currentQ.value = 0;
    try {
        const { data: qs } = await API.get('/learning/placement/questions/');
        questions.value = qs;
        step.value = 'quiz';
    } catch (e) {
        showToast('문항을 불러올 수 없습니다.', 'error');
    }
};

const levelLabel = computed(() => {
    const labels = { 1: '쉽게 이해하기', 2: '핵심 정리', 3: '심화 완성' };
    return labels[result.value?.level] || '';
});
const levelColor = computed(() => {
    const colors = { 1: '#f59e0b', 2: '#3b82f6', 3: '#8b5cf6' };
    return colors[result.value?.level] || '#9ba1a6';
});
const levelIcon = computed(() => {
    const icons = { 1: '🌱', 2: '🌿', 3: '🌳' };
    return icons[result.value?.level] || '🌱';
});
</script>

<template>
<div class="placement-container">
    <!-- 로딩 -->
    <div v-if="step === 'loading'" class="loading-screen">
        <div class="spinner"></div>
        <p>진단 정보를 불러오는 중...</p>
    </div>

    <!-- ═══ 진단 퀴즈 ═══ -->
    <div v-if="step === 'quiz'" class="quiz-screen">
        <div class="quiz-header">
            <h1>🎯 수준 진단 테스트</h1>
            <p>15~20문항으로 현재 수준을 진단합니다</p>
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progress + '%' }"></div>
            </div>
            <span class="progress-text">{{ currentQ + 1 }} / {{ questions.length }}</span>
        </div>

        <div v-if="questions.length > 0" class="question-card">
            <div class="q-category">
                {{ { CONCEPT: '💡 개념 이해도', PRACTICE: '🔧 실습 경험', PATTERN: '📚 학습 패턴' }[questions[currentQ].category] }}
            </div>
            <h2 class="q-text">{{ questions[currentQ].question_text }}</h2>
            <div class="q-options">
                <button v-for="(opt, i) in questions[currentQ].options" :key="i"
                    class="q-option"
                    :class="{ selected: answers[questions[currentQ].id] === opt }"
                    @click="selectAnswer(questions[currentQ].id, opt)">
                    <span class="opt-index">{{ ['A', 'B', 'C', 'D'][i] }}</span>
                    {{ opt }}
                </button>
            </div>
        </div>

        <div class="quiz-nav">
            <button v-if="currentQ > 0" class="btn-nav" @click="currentQ--">← 이전</button>
            <span v-else></span>
            <button v-if="currentQ < questions.length - 1" class="btn-nav" @click="currentQ++">다음 →</button>
            <button v-else class="btn-submit" :disabled="submitting || Object.keys(answers).length < questions.length"
                @click="submitQuiz">
                {{ submitting ? '제출 중...' : '✅ 진단 완료' }}
            </button>
        </div>
    </div>

    <!-- ═══ 결과 화면 ═══ -->
    <div v-if="step === 'result'" class="result-screen">
        <div class="result-card">
            <div class="result-level" :style="{ background: levelColor }">
                <span class="level-icon">{{ levelIcon }}</span>
                <h2>Level {{ result.level }}</h2>
                <p>{{ levelLabel }}</p>
            </div>
            <div class="result-stats">
                <div class="stat-item">
                    <span class="stat-value">{{ result.score }}</span>
                    <span class="stat-label">정답</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{{ result.total }}</span>
                    <span class="stat-label">총 문항</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{{ result.ratio }}%</span>
                    <span class="stat-label">정답률</span>
                </div>
            </div>
            <div class="category-breakdown">
                <h3>📊 영역별 분석</h3>
                <div v-for="(score, cat) in result.category_scores" :key="cat" class="cat-bar-row">
                    <span class="cat-name">{{ { CONCEPT: '💡 개념', PRACTICE: '🔧 실습', PATTERN: '📚 패턴' }[cat] }}</span>
                    <div class="cat-bar-track">
                        <div class="cat-bar-fill" :style="{ width: (score / (result.category_totals?.[cat] || 1) * 100) + '%' }"></div>
                    </div>
                    <span class="cat-score">{{ score }}점</span>
                </div>
            </div>
        </div>
        <button class="btn-next" @click="step = 'goal'">다음: 목표 설정하기 →</button>
    </div>

    <!-- ═══ 목표 설정 ═══ -->
    <div v-if="step === 'goal'" class="goal-screen">
        <h1>🎯 당신은 어디로 가고 싶으신가요?</h1>
        <p class="goal-subtitle">목표 직무를 선택하면 필요한 역량 로드맵이 생성됩니다</p>

        <div v-if="careers.length > 0" class="career-grid">
            <div v-for="career in careers" :key="career.id" class="career-card"
                :class="{ selected: selectedCareer?.id === career.id }"
                @click="selectGoal(career)">
                <span class="career-icon">{{ career.icon }}</span>
                <h3>{{ career.title }}</h3>
                <p class="career-desc">{{ career.description }}</p>
                <div class="career-meta">
                    <span>📅 약 {{ career.estimated_weeks }}주</span>
                    <span>🧩 {{ career.required_skills.length }}개 역량</span>
                </div>
                <div class="career-skills">
                    <span v-for="skill in career.required_skills.slice(0, 5)" :key="skill.id" class="skill-tag">
                        {{ skill.name }}
                    </span>
                    <span v-if="career.required_skills.length > 5" class="skill-more">
                        +{{ career.required_skills.length - 5 }}개
                    </span>
                </div>
            </div>
        </div>
        <div v-else class="goal-empty">
            <p>등록된 목표 직무가 없습니다.</p>
        </div>

        <!-- ── 직접 만들기 토글 ── -->
        <div class="custom-toggle-area">
            <button class="btn-custom-toggle" @click="showCustomForm = !showCustomForm">
                {{ showCustomForm ? '✕ 닫기' : '✨ 원하는 직무 직접 만들기' }}
            </button>
        </div>

        <!-- ── 커스텀 직무 폼 ── -->
        <div v-if="showCustomForm" class="custom-form-card">
            <h3>🛠️ 나만의 직무 만들기</h3>

            <div class="form-row">
                <label>직무명 *</label>
                <input v-model="customCareer.title" placeholder="예: AI 엔지니어, UX 디자이너..." class="form-input" />
            </div>

            <div class="form-row">
                <label>설명</label>
                <input v-model="customCareer.description" placeholder="이 직무에 대한 간단한 설명" class="form-input" />
            </div>

            <div class="form-row">
                <label>아이콘</label>
                <div class="icon-picker">
                    <button v-for="emoji in ['🎯','💻','🤖','🎨','📊','🔬','🏗️','📱','🌐','🛡️']" :key="emoji"
                        class="icon-btn" :class="{ active: customCareer.icon === emoji }"
                        @click="customCareer.icon = emoji">{{ emoji }}</button>
                </div>
            </div>

            <div class="form-row">
                <label>필요 스킬 * (Enter로 추가)</label>
                <div class="skill-input-row">
                    <input v-model="customSkillInput" placeholder="스킬명 입력 후 Enter"
                        class="form-input" @keydown.enter.prevent="addCustomSkill" />
                    <button class="btn-add-skill" @click="addCustomSkill">+ 추가</button>
                </div>
                <div v-if="customSkills.length > 0" class="skill-tags">
                    <span v-for="(skill, i) in customSkills" :key="i" class="custom-skill-tag">
                        {{ skill }}
                        <button class="tag-remove" @click="removeCustomSkill(i)">✕</button>
                    </span>
                </div>
                <p v-else class="skill-hint">아직 추가된 스킬이 없습니다. 위에 입력해주세요.</p>
            </div>

            <button class="btn-create-career" :disabled="submitting" @click="submitCustomCareer">
                {{ submitting ? '생성 중...' : '🚀 직무 생성 + 목표 설정' }}
            </button>
        </div>

        <div class="goal-bottom-actions">
            <button class="btn-skip" @click="step = 'done'">나중에 선택하기 →</button>
            <button class="btn-retake" @click="retakePlacement">🔄 다시 진단하기</button>
        </div>
    </div>

    <!-- ═══ 완료 ═══ -->
    <div v-if="step === 'done'" class="done-screen">
        <div class="done-card">
            <span class="done-icon">🎉</span>
            <h2>진단 + 목표 설정 완료!</h2>
            <p>이제 갭 맵에서 나에게 필요한 역량을 확인하세요.</p>
            <div v-if="result" class="done-result-summary">
                <span class="done-level" :style="{ background: levelColor }">Level {{ result.level }} — {{ levelLabel }}</span>
                <span class="done-score">{{ result.score }}/{{ result.total }} ({{ result.ratio }}%)</span>
            </div>
            <div class="done-actions">
                <button class="btn-primary" @click="goToGapMap">🗺️ 갭 맵 보기</button>
                <button class="btn-secondary" @click="goToDashboard">📊 대시보드로</button>
            </div>
            <button class="btn-retake" @click="retakePlacement">🔄 다시 진단하기</button>
        </div>
    </div>
</div>
</template>

<style scoped>
.placement-container {
    min-height: 100vh; padding: 40px 20px;
    background: linear-gradient(135deg, #0f172a, #1e293b);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

/* 로딩 */
.loading-screen { text-align: center; color: white; }
.spinner { width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.2); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 퀴즈 */
.quiz-screen { max-width: 700px; width: 100%; }
.quiz-header { text-align: center; margin-bottom: 32px; }
.quiz-header h1 { color: white; font-size: 28px; margin: 0; }
.quiz-header p { color: #94a3b8; font-size: 14px; margin: 8px 0 20px; }
.progress-bar { height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; border-radius: 3px; }
.progress-text { color: #94a3b8; font-size: 12px; margin-top: 8px; display: block; }

.question-card {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 32px; backdrop-filter: blur(10px);
}
.q-category { font-size: 12px; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.q-text { color: white; font-size: 18px; font-weight: 600; margin: 0 0 24px; line-height: 1.5; }
.q-options { display: flex; flex-direction: column; gap: 10px; }
.q-option {
    display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px; color: white; font-size: 14px; cursor: pointer;
    transition: all 0.2s; text-align: left;
}
.q-option:hover { background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.3); }
.q-option.selected { background: rgba(59,130,246,0.2); border-color: #3b82f6; }
.opt-index {
    width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center;
    background: rgba(255,255,255,0.1); font-weight: 700; font-size: 12px; flex-shrink: 0;
}
.q-option.selected .opt-index { background: #3b82f6; }

.quiz-nav { display: flex; justify-content: space-between; margin-top: 24px; }
.btn-nav { padding: 10px 24px; background: rgba(255,255,255,0.1); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-nav:hover { background: rgba(255,255,255,0.2); }
.btn-submit { padding: 12px 32px; background: #22c55e; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 15px; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* 결과 */
.result-screen { max-width: 500px; width: 100%; }
.result-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 0; overflow: hidden; }
.result-level { padding: 40px; text-align: center; color: white; }
.level-icon { font-size: 48px; display: block; margin-bottom: 8px; }
.result-level h2 { font-size: 32px; margin: 0; }
.result-level p { font-size: 16px; opacity: 0.9; margin: 4px 0 0; }
.result-stats { display: flex; justify-content: space-around; padding: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.stat-item { text-align: center; }
.stat-value { display: block; font-size: 24px; font-weight: 700; color: white; }
.stat-label { font-size: 11px; color: #94a3b8; }
.category-breakdown { padding: 20px; }
.category-breakdown h3 { color: white; font-size: 14px; margin: 0 0 12px; }
.cat-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.cat-name { color: #94a3b8; font-size: 12px; width: 70px; flex-shrink: 0; }
.cat-bar-track { flex: 1; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.cat-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 4px; transition: width 0.5s; }
.cat-score { color: white; font-size: 12px; font-weight: 600; width: 40px; text-align: right; }
.btn-next { width: 100%; padding: 14px; background: #3b82f6; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 16px; }

/* 목표 설정 */
.goal-screen { max-width: 900px; width: 100%; }
.goal-screen h1 { color: white; text-align: center; font-size: 28px; margin: 0 0 8px; }
.goal-subtitle { color: #94a3b8; text-align: center; font-size: 14px; margin-bottom: 32px; }
.goal-empty { text-align: center; color: #64748b; font-size: 14px; padding: 40px 0; }
.goal-bottom-actions {
    display: flex; justify-content: center; gap: 12px; margin-top: 32px; flex-wrap: wrap;
}
.btn-skip {
    padding: 10px 24px; background: rgba(255,255,255,0.08); color: #e2e8f0;
    border: 1px solid rgba(255,255,255,0.15); border-radius: 8px;
    font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.btn-skip:hover { background: rgba(255,255,255,0.15); }
.career-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.career-card {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 24px; cursor: pointer; transition: all 0.2s;
}
.career-card:hover { border-color: rgba(59,130,246,0.4); transform: translateY(-2px); }
.career-card.selected { border-color: #3b82f6; background: rgba(59,130,246,0.1); }
.career-icon { font-size: 36px; display: block; margin-bottom: 12px; }
.career-card h3 { color: white; font-size: 18px; margin: 0 0 8px; }
.career-desc { color: #94a3b8; font-size: 12px; line-height: 1.5; margin-bottom: 12px; }
.career-meta { display: flex; gap: 12px; font-size: 12px; color: #64748b; margin-bottom: 12px; }
.career-skills { display: flex; flex-wrap: wrap; gap: 4px; }
.skill-tag { padding: 3px 8px; background: rgba(59,130,246,0.15); color: #93c5fd; border-radius: 4px; font-size: 10px; }
.skill-more { padding: 3px 8px; color: #64748b; font-size: 10px; }

/* 완료 */
.done-screen { max-width: 500px; width: 100%; }
.done-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 48px; text-align: center; }
.done-icon { font-size: 64px; display: block; margin-bottom: 16px; }
.done-card h2 { color: white; font-size: 24px; margin: 0 0 8px; }
.done-card p { color: #94a3b8; font-size: 14px; margin-bottom: 24px; }
.done-actions { display: flex; gap: 12px; justify-content: center; }
.btn-primary { padding: 12px 28px; background: #3b82f6; color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; }
.btn-secondary { padding: 12px 28px; background: rgba(255,255,255,0.1); color: white; border: none; border-radius: 10px; font-size: 15px; cursor: pointer; }
.btn-retake {
    display: block; width: 100%; margin-top: 16px; padding: 10px;
    background: none; border: 1px solid rgba(255,255,255,0.15); color: #94a3b8;
    border-radius: 8px; font-size: 13px; cursor: pointer; transition: all 0.2s;
}
.btn-retake:hover { border-color: rgba(255,255,255,0.3); color: white; }
.done-result-summary {
    display: flex; align-items: center; justify-content: center; gap: 12px;
    margin: 16px 0 24px; flex-wrap: wrap;
}
.done-level {
    padding: 6px 16px; border-radius: 20px; color: white;
    font-size: 14px; font-weight: 600;
}
.done-score { color: #94a3b8; font-size: 14px; }

/* 커스텀 직무 만들기 */
.custom-toggle-area { text-align: center; margin: 24px 0 8px; }
.btn-custom-toggle {
    padding: 12px 28px; background: linear-gradient(135deg, #8b5cf6, #6366f1);
    color: white; border: none; border-radius: 10px; font-size: 15px;
    font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-custom-toggle:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(99,102,241,0.4); }
.custom-form-card {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(139,92,246,0.3);
    border-radius: 16px; padding: 28px; margin-top: 16px;
    animation: slideDown 0.3s ease;
}
@keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
.custom-form-card h3 { color: white; font-size: 18px; margin: 0 0 20px; }
.form-row { margin-bottom: 16px; }
.form-row label { display: block; color: #94a3b8; font-size: 12px; margin-bottom: 6px; font-weight: 600; }
.form-input {
    width: 100%; padding: 10px 14px; background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15); border-radius: 8px;
    color: white; font-size: 14px; outline: none; box-sizing: border-box;
}
.form-input:focus { border-color: #8b5cf6; }
.form-input::placeholder { color: #64748b; }
.icon-picker { display: flex; gap: 6px; flex-wrap: wrap; }
.icon-btn {
    width: 38px; height: 38px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.05); font-size: 18px; cursor: pointer;
    display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.icon-btn:hover { border-color: rgba(255,255,255,0.3); }
.icon-btn.active { border-color: #8b5cf6; background: rgba(139,92,246,0.2); }
.skill-input-row { display: flex; gap: 8px; }
.skill-input-row .form-input { flex: 1; }
.btn-add-skill {
    padding: 10px 16px; background: #8b5cf6; color: white; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.skill-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.custom-skill-tag {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 5px 10px; background: rgba(139,92,246,0.2); color: #c4b5fd;
    border-radius: 6px; font-size: 12px;
}
.tag-remove { background: none; border: none; color: #f87171; cursor: pointer; font-size: 12px; padding: 0; }
.skill-hint { color: #64748b; font-size: 12px; margin-top: 8px; }
.btn-create-career {
    width: 100%; padding: 14px; background: linear-gradient(135deg, #8b5cf6, #3b82f6);
    color: white; border: none; border-radius: 10px; font-size: 16px;
    font-weight: 600; cursor: pointer; margin-top: 8px; transition: all 0.2s;
}
.btn-create-career:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(59,130,246,0.4); }
.btn-create-career:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
</style>
