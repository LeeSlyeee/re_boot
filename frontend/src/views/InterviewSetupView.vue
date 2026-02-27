<script setup>
import { ref, onMounted, computed } from "vue";
import { useToast } from '../composables/useToast';
const { showToast } = useToast();
import { useRouter } from "vue-router";
import api from "../api/axios";
import { getPortfolios } from "../api/career";
import {
  BookOpen,
  User,
  Briefcase,
  Zap,
  Globe,
  AlertTriangle,
  Hash,
  Clock,
  Infinity as InfinityIcon,
  History,
  ChevronRight,
  Trophy,
  GraduationCap,
  Users,
} from "lucide-vue-next";

const router = useRouter();
const portfolios = ref([]);
const selectedPortfolio = ref(null);
const selectedPersona = ref("TECH_LEAD");
const loading = ref(false);
const interviewHistory = ref([]);

// Step 3: Interview Mode
const interviewMode = ref("questions"); // 'questions' | 'time' | 'unlimited'
const questionCount = ref(5);
const timeLimit = ref(15); // minutes

const questionOptions = [3, 5, 7, 10];
const timeOptions = [10, 15, 20, 30];

const limitLabel = computed(() => {
  if (interviewMode.value === "questions") return `${questionCount.value}개 질문`;
  if (interviewMode.value === "time") return `${timeLimit.value}분`;
  return "무제한";
});

const personas = [
  {
    id: "TECH_LEAD",
    name: "깐깐한 기술 팀장",
    desc: "기술적 깊이와 아키텍처를 집요하게 검증합니다.",
    icon: BookOpen,
    color: "#4facfe",
  },
  {
    id: "FRIENDLY_SENIOR",
    name: "친절한 사수",
    desc: "잠재력과 학습 태도, 팀 적응력을 봅니다.",
    icon: User,
    color: "#43e97b",
  },
  {
    id: "HR_MANAGER",
    name: "인사 담당자",
    desc: "컬처핏, 커뮤니케이션, 갈등 해결 능력을 봅니다.",
    icon: Briefcase,
    color: "#fa709a",
  },
  {
    id: "STARTUP_CEO",
    name: "스타트업 대표",
    desc: "비즈니스 임팩트와 빠른 문제 해결력을 중시합니다.",
    icon: Zap,
    color: "#fddb92",
  },
  {
    id: "BIG_TECH",
    name: "글로벌 빅테크",
    desc: "CS 기초(자료구조/알고리즘)와 대규모 시스템 설계를 봅니다.",
    icon: Globe,
    color: "#a18cd1",
  },
  {
    id: "PRESSURE",
    name: "압박 면접관",
    desc: "논리적 허점을 파고들며 위기 대처 능력을 테스트합니다.",
    icon: AlertTriangle,
    color: "#ff0844",
  },
  {
    id: "GROWTH",
    name: "성장 잠재력 평가",
    desc: "기술 습득 속도, 자기주도 학습력, 신기술 적응력을 평가합니다.",
    icon: GraduationCap,
    color: "#f7971e",
  },
  {
    id: "PEER",
    name: "동료 개발자",
    desc: "함께 일할 동료로서 코드 리뷰, 협업, 실무 방식을 편하게 대화합니다.",
    icon: Users,
    color: "#36d1dc",
  },
];

onMounted(async () => {
  try {
    const [portfolioRes, historyRes] = await Promise.all([
      getPortfolios(),
      api.get('/career/interview/')
    ]);

    portfolios.value = portfolioRes;
    if (portfolios.value.length > 0) {
      selectedPortfolio.value = portfolios.value[0].id;
    }

    interviewHistory.value = historyRes.data;
  } catch (e) {
    console.error("Failed to load data", e);
  }
});

const getPersonaName = (personaId) => {
  const p = personas.find(x => x.id === personaId);
  return p ? p.name : personaId;
};

const getPersonaColor = (personaId) => {
  const p = personas.find(x => x.id === personaId);
  return p ? p.color : '#4facfe';
};

const getAvgScore = (interview) => {
  const scored = (interview.exchanges || []).filter(e => e.score > 0);
  if (scored.length === 0) return 0;
  return Math.round(scored.reduce((a, b) => a + b.score, 0) / scored.length);
};

const getScoreClass = (score) => {
  if (score >= 80) return 'high';
  if (score >= 50) return 'mid';
  return 'low';
};

const reviewInterview = (id) => {
  router.push(`/interview/${id}`);
};

const startInterview = async () => {
  if (!selectedPortfolio.value) {
    showToast("기반이 될 포트폴리오를 선택해주세요.", 'warning');
    return;
  }

  loading.value = true;
  try {
    const payload = {
      portfolio_id: selectedPortfolio.value,
      persona: selectedPersona.value,
    };

    if (interviewMode.value === "questions") {
      payload.max_questions = questionCount.value;
    } else if (interviewMode.value === "time") {
      payload.max_minutes = timeLimit.value;
    }
    // 'unlimited' → 둘 다 보내지 않음

    const res = await api.post("/career/interview/start/", payload);

    const interviewId = res.data.interview_id;
    router.push(`/interview/${interviewId}`);
  } catch (e) {
    console.error(e);
    showToast("면접 세션 생성 실패: " + (e.response?.data?.error || e.message, 'error'));
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="setup-container">
    <header class="page-header">
      <h1>🎙️ AI 모의 면접 (Mock Interview)</h1>
      <p>
        작성된 포트폴리오와 스킬셋을 기반으로 실전 같은 기술 면접을
        경험해보세요.
      </p>
    </header>

    <main class="glass-panel">
      <!-- Step 1: Portfolio -->
      <section class="step-section">
        <h2>1. 어떤 포트폴리오로 면접을 볼까요?</h2>
        <div class="portfolio-selector">
          <select v-model="selectedPortfolio" class="glass-select">
            <option v-for="p in portfolios" :key="p.id" :value="p.id">
              {{ p.title }} ({{ p.portfolio_type_display }}) -
              {{ p.created_at }}
            </option>
          </select>
          <p v-if="portfolios.length === 0" class="empty-msg">
            생성된 포트폴리오가 없습니다. '커리어 포트폴리오' 메뉴에서 먼저
            문서를 생성해주세요.
          </p>
        </div>
      </section>

      <!-- Step 2: Persona -->
      <section class="step-section">
        <h2>2. 어떤 면접관을 만나시겠습니까?</h2>
        <div class="persona-grid">
          <div
            v-for="p in personas"
            :key="p.id"
            class="persona-card"
            :class="{ active: selectedPersona === p.id }"
            @click="selectedPersona = p.id"
            :style="{ '--accent-color': p.color }"
          >
            <div class="icon-wrapper" :style="{ background: p.color }">
              <component :is="p.icon" size="24" color="white" />
            </div>
            <h3>{{ p.name }}</h3>
            <p>{{ p.desc }}</p>
          </div>
        </div>
      </section>

      <!-- Step 3: Interview Mode -->
      <section class="step-section">
        <h2>3. 면접 방식을 선택하세요</h2>
        <div class="mode-grid">
          <!-- Questions Mode -->
          <div
            class="mode-card"
            :class="{ active: interviewMode === 'questions' }"
            @click="interviewMode = 'questions'"
          >
            <div class="mode-icon questions">
              <Hash size="28" color="white" />
            </div>
            <h3>질문 수 지정</h3>
            <p>정해진 질문 수만큼 면접을 진행합니다.</p>
            <div v-if="interviewMode === 'questions'" class="mode-options">
              <button
                v-for="opt in questionOptions"
                :key="opt"
                class="option-chip"
                :class="{ selected: questionCount === opt }"
                @click.stop="questionCount = opt"
              >
                {{ opt }}문항
              </button>
            </div>
          </div>

          <!-- Time Mode -->
          <div
            class="mode-card"
            :class="{ active: interviewMode === 'time' }"
            @click="interviewMode = 'time'"
          >
            <div class="mode-icon time">
              <Clock size="28" color="white" />
            </div>
            <h3>시간 제한</h3>
            <p>설정한 시간 동안 면접을 진행합니다.</p>
            <div v-if="interviewMode === 'time'" class="mode-options">
              <button
                v-for="opt in timeOptions"
                :key="opt"
                class="option-chip"
                :class="{ selected: timeLimit === opt }"
                @click.stop="timeLimit = opt"
              >
                {{ opt }}분
              </button>
            </div>
          </div>

          <!-- Unlimited Mode -->
          <div
            class="mode-card"
            :class="{ active: interviewMode === 'unlimited' }"
            @click="interviewMode = 'unlimited'"
          >
            <div class="mode-icon unlimited">
              <InfinityIcon size="28" color="white" />
            </div>
            <h3>무제한 면접</h3>
            <p>원할 때까지 자유롭게 면접을 계속합니다.</p>
          </div>
        </div>
      </section>

      <!-- AI 활용 사전 고지 (AI 기본법 투명성 의무) -->
      <div class="ai-notice">
        <span class="ai-notice-icon">🤖</span>
        <div class="ai-notice-text">
          <strong>AI 활용 안내</strong>
          <p>
            본 모의면접은 <strong>AI(인공지능)</strong>가 질문을 생성하고 답변을
            평가합니다. 모든 결과는 <strong>AI 자동 생성 참고 자료</strong>이며
            실제 채용 결과와 무관합니다.
          </p>
        </div>
      </div>

      <!-- Summary -->
      <div class="interview-summary">
        <span class="summary-chip">{{ limitLabel }}</span>
        <span class="summary-divider">·</span>
        <span class="summary-chip persona">{{ personas.find(p => p.id === selectedPersona)?.name }}</span>
      </div>

      <!-- Action -->
      <div class="action-footer">
        <button
          class="start-btn"
          @click="startInterview"
          :disabled="loading || portfolios.length === 0"
        >
          <span v-if="loading">면접장 준비 중... ⏳</span>
          <span v-else>면접 시작하기 🚀</span>
        </button>
      </div>
    </main>

    <!-- Interview History -->
    <section class="history-section" v-if="interviewHistory.length > 0">
      <div class="history-header">
        <History :size="22" />
        <h2>면접 기록 (Interview History)</h2>
        <span class="history-count">{{ interviewHistory.length }}회</span>
      </div>

      <div class="history-list">
        <div
          v-for="iv in interviewHistory"
          :key="iv.id"
          class="history-card"
          @click="reviewInterview(iv.id)"
          :style="{ '--card-accent': getPersonaColor(iv.persona) }"
        >
          <div class="history-left">
            <div class="history-persona-badge" :style="{ background: getPersonaColor(iv.persona) }">
              🤖
            </div>
            <div class="history-info">
              <div class="history-title">
                {{ getPersonaName(iv.persona) }} 면접
              </div>
              <div class="history-meta">
                <span>{{ iv.portfolio_title || '포트폴리오' }}</span>
                <span class="meta-dot">·</span>
                <span>{{ (iv.exchanges || []).filter(e => e.score > 0).length }}문항 응답</span>
                <span class="meta-dot">·</span>
                <span>{{ iv.created_at }}</span>
              </div>
            </div>
          </div>
          <div class="history-right">
            <div class="history-score" :class="getScoreClass(getAvgScore(iv))" v-if="getAvgScore(iv) > 0">
              <Trophy :size="14" />
              {{ getAvgScore(iv) }}점
            </div>
            <span class="status-tag" :class="iv.status">
              {{ iv.status === 'COMPLETED' ? '완료' : '진행 중' }}
            </span>
            <ChevronRight :size="18" class="history-arrow" />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.setup-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 20px;
  color: white;
}
.page-header {
  text-align: center;
  margin-bottom: 40px;
}
.page-header h1 {
  font-size: 2.5rem;
  font-weight: 800;
  margin-bottom: 10px;
  background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.page-header p {
  color: #aaa;
  font-size: 1.1rem;
}

.glass-panel {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(16px);
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 40px;
}

.step-section {
  margin-bottom: 40px;
}
.step-section h2 {
  font-size: 1.2rem;
  margin-bottom: 20px;
  border-left: 4px solid #4facfe;
  padding-left: 15px;
}

.glass-select {
  width: 100%;
  padding: 15px;
  font-size: 1rem;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  outline: none;
  cursor: pointer;
}
.empty-msg {
  color: #ff6b6b;
  margin-top: 10px;
  font-size: 0.9rem;
}

/* Persona Grid */
.persona-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}
.persona-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 25px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}
.persona-card:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.08);
}
.persona-card.active {
  border-color: var(--accent-color);
  background: rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 20px rgba(var(--accent-color), 0.2);
}
.icon-wrapper {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 15px;
}
.persona-card h3 {
  margin: 0 0 10px 0;
  font-size: 1.1rem;
}
.persona-card p {
  margin: 0;
  font-size: 0.9rem;
  color: #ccc;
  line-height: 1.4;
}

/* ── Mode Grid (Step 3) ── */
.mode-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.mode-card {
  background: rgba(255, 255, 255, 0.03);
  border: 2px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
}
.mode-card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.06);
}
.mode-card.active {
  border-color: #4facfe;
  background: rgba(79, 172, 254, 0.08);
  box-shadow: 0 0 24px rgba(79, 172, 254, 0.15);
}
.mode-card h3 {
  font-size: 1.05rem;
  margin: 14px 0 6px;
  font-weight: 700;
}
.mode-card p {
  font-size: 0.85rem;
  color: #999;
  margin: 0 0 12px;
  line-height: 1.4;
}

.mode-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}
.mode-icon.questions {
  background: linear-gradient(135deg, #667eea, #764ba2);
}
.mode-icon.time {
  background: linear-gradient(135deg, #f093fb, #f5576c);
}
.mode-icon.unlimited {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
}

.mode-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 12px;
  animation: fadeIn 0.3s ease;
}

.option-chip {
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #ccc;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.option-chip:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}
.option-chip.selected {
  background: rgba(79, 172, 254, 0.2);
  border-color: #4facfe;
  color: #4facfe;
  box-shadow: 0 0 8px rgba(79, 172, 254, 0.2);
}

/* ── Interview Summary ── */
.interview-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 24px;
  padding: 14px;
  background: rgba(79, 172, 254, 0.06);
  border: 1px solid rgba(79, 172, 254, 0.12);
  border-radius: 12px;
}
.summary-chip {
  font-size: 0.95rem;
  font-weight: 600;
  color: #4facfe;
}
.summary-chip.persona {
  color: #a18cd1;
}
.summary-divider {
  color: #555;
}

/* ── Action ── */
.action-footer {
  text-align: center;
  margin-top: 20px;
}
.start-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 16px 48px;
  font-size: 1.2rem;
  font-weight: bold;
  border-radius: 50px;
  cursor: pointer;
  transition: transform 0.2s;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
}
.start-btn:hover:not(:disabled) {
  transform: scale(1.05);
}
.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  filter: grayscale(100%);
}

/* AI 기본법 사전 고지 */
.ai-notice {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  background: rgba(79, 172, 254, 0.06);
  border: 1px solid rgba(79, 172, 254, 0.15);
  border-radius: 14px;
  padding: 18px 22px;
  margin-bottom: 24px;
}
.ai-notice-icon {
  font-size: 28px;
  flex-shrink: 0;
  margin-top: 2px;
}
.ai-notice-text strong {
  color: #4facfe;
  font-size: 0.95rem;
}
.ai-notice-text p {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: #9ab3d0;
  line-height: 1.6;
}
.ai-notice-text p strong {
  color: #7ec8f8;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 반응형 */
@media (max-width: 768px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }
}

/* ── Interview History Section ── */
.history-section {
  margin-top: 40px;
}
.history-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  color: #ddd;
}
.history-header h2 {
  font-size: 1.3rem;
  font-weight: 700;
  margin: 0;
}
.history-count {
  font-size: 0.85rem;
  background: rgba(79, 172, 254, 0.12);
  color: #4facfe;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 600;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-left: 3px solid var(--card-accent, #4facfe);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  transition: all 0.25s ease;
}
.history-card:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateX(4px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.history-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 0;
}

.history-persona-badge {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.history-info {
  min-width: 0;
}
.history-title {
  font-weight: 600;
  font-size: 1rem;
  margin-bottom: 4px;
  color: #eee;
}
.history-meta {
  font-size: 0.8rem;
  color: #888;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.meta-dot {
  color: #555;
}

.history-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.history-score {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 700;
  font-size: 0.95rem;
  padding: 5px 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
}
.history-score.high {
  color: #4caf50;
}
.history-score.mid {
  color: #ff9800;
}
.history-score.low {
  color: #f44336;
}

.status-tag {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
}
.status-tag.COMPLETED {
  background: rgba(76, 175, 80, 0.12);
  color: #4caf50;
}
.status-tag.IN_PROGRESS {
  background: rgba(255, 152, 0, 0.12);
  color: #ff9800;
}

.history-arrow {
  color: #555;
  transition: transform 0.2s;
}
.history-card:hover .history-arrow {
  transform: translateX(3px);
  color: #4facfe;
}
</style>
