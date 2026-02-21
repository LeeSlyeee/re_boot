<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { getPortfolios, generatePortfolio } from "../api/career";
import api from "../api/axios"; // [New] for direct calls
import {
  FileText,
  Rocket,
  Loader,
  Plus,
  ChevronRight,
  Briefcase,
  AlertTriangle,
  X,
  CheckCircle,
  Lock,
  Mic,
  Trophy,
} from "lucide-vue-next";

const router = useRouter();
const portfolios = ref([]);
const skillData = ref({ stats: { total: 0, earned: 0, rate: 0 }, categories: [] });
const loading = ref(false);
const skillsLoading = ref(false);
const generating = ref(false);
const selectedPortfolio = ref(null);

// Error Modal State
const showModal = ref(false);
const errorMessage = ref("");

onMounted(async () => {
  loading.value = true;
  skillsLoading.value = true;

  try {
    // Parallel Fetch
    const [portfolioRes, skillsRes] = await Promise.all([
      getPortfolios(),
      api.get("/career/portfolios/skills/"), // [FIX] Correct Endpoint
    ]);

    portfolios.value = portfolioRes;
    if (portfolios.value.length > 0) {
      selectedPortfolio.value = portfolios.value[0];
    }

    skillData.value = skillsRes.data;
  } catch (e) {
    console.error("Skills Fetch Failed", e);
    // Only show critical errors, don't fallback to dummy
    if (e.response?.status !== 404) {
      alert(`스킬 데이터 로딩 실패: ${e.message}`);
    }
  } finally {
    loading.value = false;
    skillsLoading.value = false;
  }
});

const handleGenerate = async (type) => {
  generating.value = true;
  try {
    const newPortfolio = await generatePortfolio(type);
    portfolios.value.unshift(newPortfolio);
    selectedPortfolio.value = newPortfolio;
  } catch (e) {
    // 기존 alert 대신 모달 표시
    // e.response.data.error가 있으면 그것을 사용, 없으면 기본 메시지
    const serverMsg =
      e.response?.data?.error ||
      "학습 데이터가 부족하거나 AI 응답이 지연되고 있습니다.";
    errorMessage.value = serverMsg;
    showModal.value = true;
  } finally {
    generating.value = false;
  }
};

const selectPortfolio = (p) => {
  selectedPortfolio.value = p;
};

const closeModal = () => {
  showModal.value = false;
};
</script>

<template>
  <div class="portfolio-view">
    <div class="container">
      <header class="page-header">
        <div>
          <h1 class="text-headline">커리어 포트폴리오</h1>
          <p class="subtitle">
            AI가 학습 기록을 분석하여 포트폴리오와 기획서를 자동으로 생성합니다.
          </p>
        </div>
        <div class="header-actions">
          <button
            @click="handleGenerate('JOB')"
            :disabled="generating"
            class="gen-btn job"
          >
            <Briefcase size="16" /> 취업 포트폴리오 생성
          </button>
          <button
            @click="handleGenerate('STARTUP')"
            :disabled="generating"
            class="gen-btn startup"
          >
            <Rocket size="16" /> 창업 MVP 기획서 생성
          </button>
          <button
            @click="router.push('/interview/setup')"
            class="gen-btn interview"
          >
            <Mic size="16" /> AI 면접 연습
          </button>
        </div>
      </header>

      <div v-if="generating" class="loading-overlay">
        <Loader class="spin" />
        <p>AI가 지난 모든 학습 데이터를 분석중입니다... (최대 1분 소요)</p>
      </div>

      <!-- Error Modal -->
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content glass-panel">
          <button class="close-btn" @click="closeModal"><X size="20" /></button>
          <div class="modal-header">
            <div class="icon-box danger">
              <AlertTriangle size="24" />
            </div>
            <h2>생성 실패 (Generation Failed)</h2>
          </div>

          <div class="modal-body">
            <p class="main-msg">AI 포트폴리오를 생성하지 못했습니다.</p>
            <p class="sub-msg">{{ errorMessage }}</p>

            <div class="troubleshoot-box">
              <h3>원인 및 해결 방법</h3>
              <ul>
                <li>
                  <span class="bullet">1</span>
                  <div>
                    <strong>학습 데이터 부족</strong>
                    <p>
                      최소 1개 이상의 학습 세션(강의 요약)이 필요합니다.<br />'학습하기'
                      메뉴에서 강의를 듣고 AI 요약을 완료해주세요.
                    </p>
                  </div>
                </li>
                <li>
                  <span class="bullet">2</span>
                  <div>
                    <strong>OpenAI API 설정 문제</strong>
                    <p>
                      서버에 API Key가 설정되지 않았거나 만료되었을 수
                      있습니다.<br />관리자에게 문의해주세요.
                    </p>
                  </div>
                </li>
                <li>
                  <span class="bullet">3</span>
                  <div>
                    <strong>일시적인 시스템 오류</strong>
                    <p>네트워크 상태를 확인하고 잠시 후 다시 시도해주세요.</p>
                  </div>
                </li>
              </ul>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeModal">확인</button>
          </div>
        </div>
      </div>

      <!-- Skill Blocks Gamification Section -->
      <section
        v-if="skillData.stats.total > 0"
        class="skill-heatmap-section glass-panel"
      >
        <!-- 전체 진행률 헤더 -->
        <div class="section-header">
          <div class="header-left">
            <Trophy size="20" class="trophy-icon" />
            <h3>스킬 블록</h3>
          </div>
          <div class="stats-badge">
            <span class="earned-num">{{ skillData.stats.earned }}</span>
            <span class="divider">/</span>
            <span class="total-num">{{ skillData.stats.total }}</span>
            <span class="unit">블록 획득</span>
          </div>
        </div>

        <!-- 프로그레스 바 -->
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: skillData.stats.rate + '%' }"
            ></div>
          </div>
          <span class="progress-label">{{ skillData.stats.rate }}%</span>
        </div>

        <!-- 카테고리별 블록 -->
        <div class="skill-categories">
          <div
            v-for="cat in skillData.categories"
            :key="cat.category"
            class="skill-category"
          >
            <div class="category-header">
              <h4>{{ cat.category }}</h4>
              <span class="category-progress">{{ cat.earned_count }}/{{ cat.total }}</span>
            </div>
            <div class="blocks-grid">
              <!-- 획득한 블록 -->
              <div
                v-for="skill in cat.earned"
                :key="'e-' + skill.id"
                class="skill-block earned"
                :title="`✅ ${skill.week} - ${skill.source}\n획득일: ${skill.date}`"
              >
                <span class="block-check"><CheckCircle size="12" /></span>
                <span class="block-name">{{ skill.name }}</span>
              </div>
              <!-- 미획득 블록 (잠금) -->
              <div
                v-for="skill in cat.available"
                :key="'a-' + skill.id"
                class="skill-block locked"
                :title="skill.hint"
              >
                <span class="block-lock"><Lock size="12" /></span>
                <span class="block-name">{{ skill.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 스킬 블록이 아예 없을 때 -->
      <section
        v-else-if="!skillsLoading"
        class="skill-empty-section glass-panel"
      >
        <Trophy size="32" class="empty-icon" />
        <p>수강 중인 강의가 없습니다. 강의에 등록하면 스킬 블록을 획득할 수 있습니다!</p>
      </section>

      <div class="content-layout">
        <!-- Sidebar List -->
        <aside class="sidebar glass-panel">
          <h3>생성된 문서함</h3>
          <div class="list-container">
            <div v-if="portfolios.length === 0" class="empty-list">
              생성된 문서가 없습니다.
            </div>
            <div
              v-for="p in portfolios"
              :key="p.id"
              class="list-item"
              :class="{ active: selectedPortfolio?.id === p.id }"
              @click="selectPortfolio(p)"
            >
              <div class="icon">
                <Briefcase v-if="p.portfolio_type === 'JOB'" size="18" />
                <Rocket v-else size="18" />
              </div>
              <div class="item-info">
                <div class="item-title">{{ p.title }}</div>
                <div class="item-date">{{ p.created_at }}</div>
              </div>
              <ChevronRight size="16" class="arrow" />
            </div>
          </div>
        </aside>

        <!-- Document Viewer -->
        <main class="viewer glass-panel">
          <div v-if="selectedPortfolio" class="document-content">
            <div class="doc-header">
              <span class="badge" :class="selectedPortfolio.portfolio_type">
                {{ selectedPortfolio.portfolio_type_display }}
              </span>
              <h2>{{ selectedPortfolio.title }}</h2>
              <div class="doc-meta">
                생성일: {{ selectedPortfolio.created_at }}
              </div>
            </div>
            <div class="markdown-body">
              {{ selectedPortfolio.content }}
            </div>
          </div>
          <div v-else class="empty-state">
            <FileText size="48" />
            <p>왼쪽 목록에서 문서를 선택하거나 새로 생성해주세요.</p>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.portfolio-view {
  padding-top: var(--header-height);
  min-height: 100vh;
  background: #000;
  color: white;
  padding-bottom: 40px;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 40px 0;
  h1 {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .subtitle {
    color: #888;
  }
  .action-buttons {
    display: flex;
    gap: 12px;
    button {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      &:disabled {
        opacity: 0.5;
        cursor: wait;
      }
    }
    .btn-primary {
      background: var(--color-primary, #4facfe);
      color: white;
    }
    .btn-accent {
      background: var(--color-accent, #ff6b6b);
      color: white;
    }
  }
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(5px);
  animation: fadeIn 0.2s ease;
}

.modal-content {
  width: 480px;
  max-width: 90vw;
  background: #1c1c1e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
  padding: 32px;
  position: relative;
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  &:hover {
    color: white;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  h2 {
    font-size: 20px;
    font-weight: 600;
  }

  .icon-box {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 69, 58, 0.1);
    color: #ff453a;
  }
}

.modal-body {
  .main-msg {
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 8px;
  }
  .sub-msg {
    font-size: 14px;
    color: #ff453a;
    margin-bottom: 24px;
  }
}

.troubleshoot-box {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 16px;

  h3 {
    font-size: 13px;
    color: #888;
    text-transform: uppercase;
    margin-bottom: 12px;
    letter-spacing: 0.5px;
  }
  ul {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  li {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    font-size: 13px;
    line-height: 1.5;

    .bullet {
      width: 18px;
      height: 18px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 700;
      color: #aaa;
      flex-shrink: 0;
      margin-top: 2px;
    }

    strong {
      display: block;
      color: #eee;
      margin-bottom: 2px;
    }
    p {
      color: #888;
    }
  }
}

.modal-footer {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  .btn-secondary {
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border: none;
    padding: 10px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    &:hover {
      background: rgba(255, 255, 255, 0.2);
    }
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Skill Block Gamification */
.skill-heatmap-section {
  margin-bottom: 24px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.03);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .trophy-icon {
    color: #fbbf24;
  }

  h3 {
    font-size: 18px;
    font-weight: 700;
    color: #eee;
    margin: 0;
  }

  .stats-badge {
    display: flex;
    align-items: baseline;
    gap: 2px;
    font-weight: 600;
    background: rgba(79, 172, 254, 0.1);
    padding: 6px 14px;
    border-radius: 20px;

    .earned-num {
      font-size: 20px;
      color: #4facfe;
    }
    .divider {
      color: #555;
      margin: 0 2px;
    }
    .total-num {
      font-size: 14px;
      color: #888;
    }
    .unit {
      font-size: 12px;
      color: #666;
      margin-left: 6px;
    }
  }
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4facfe, #00f2fe);
  border-radius: 4px;
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.progress-label {
  font-size: 14px;
  font-weight: 700;
  color: #4facfe;
  min-width: 40px;
  text-align: right;
}

.skill-categories {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.skill-category {
  .category-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  h4 {
    font-size: 14px;
    color: #888;
    font-weight: 600;
    margin: 0;
  }

  .category-progress {
    font-size: 12px;
    color: #666;
    font-weight: 500;
  }

  .blocks-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
}

.skill-block {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: default;
  transition: all 0.2s;

  &.earned {
    background: rgba(79, 172, 254, 0.1);
    border: 1px solid rgba(79, 172, 254, 0.2);
    color: #eee;

    &:hover {
      background: rgba(79, 172, 254, 0.2);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .block-check {
      color: #4facfe;
      display: flex;
    }
  }

  &.locked {
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.1);
    color: #555;

    &:hover {
      background: rgba(255, 255, 255, 0.06);
      border-color: rgba(255, 255, 255, 0.2);
      color: #888;
      transform: translateY(-1px);
    }

    .block-lock {
      color: #444;
      display: flex;
    }

    .block-name {
      color: #555;
    }
  }
}

.skill-empty-section {
  margin-bottom: 24px;
  padding: 40px;
  text-align: center;
  color: #555;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;

  .empty-icon {
    color: #333;
  }

  p {
    font-size: 14px;
  }
}

/* Existing Content Styles */
.content-layout {
  display: flex;
  gap: 24px;
  height: calc(100vh - 200px);
}

.sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  h3 {
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 16px;
    font-size: 16px;
    color: #888;
  }
}

.list-container {
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.02);

  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  &.active {
    background: rgba(79, 172, 254, 0.2);
    border: 1px solid #4facfe;
  }

  .icon {
    color: #888;
  }
  .item-info {
    flex: 1;
    min-width: 0;
  }
  .item-title {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .item-date {
    font-size: 12px;
    color: #666;
  }
  .arrow {
    color: #444;
  }
}

.viewer {
  flex: 1;
  overflow-y: auto;
  background: #0d0d0d; // Slightly darker for document contrast
}

.document-content {
  padding: 40px;
  max-width: 900px;
  margin: 0 auto;
}

.doc-header {
  margin-bottom: 40px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 24px;
  h2 {
    font-size: 28px;
    font-weight: 700;
    margin: 16px 0;
  }
  .badge {
    padding: 4px 12px;
    border-radius: 100px;
    font-size: 12px;
    font-weight: 600;
    &.JOB {
      background: rgba(79, 172, 254, 0.2);
      color: #4facfe;
    }
    &.STARTUP {
      background: rgba(255, 107, 107, 0.2);
      color: #ff6b6b;
    }
  }
  .doc-meta {
    color: #666;
    font-size: 14px;
  }
}

.markdown-body {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #e0e0e0;
  font-size: 16px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #444;
  p {
    margin-top: 16px;
  }
}

.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  z-index: 999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
  gap: 16px;
  .spin {
    animation: spin 1s linear infinite;
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.glass-panel {
  background: #1c1c1e;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 24px;
}
</style>
