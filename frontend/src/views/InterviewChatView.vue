<script setup>
import { ref, onMounted, nextTick, computed, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../api/axios";
import { Send, Mic, StopCircle, Flag, Clock, Hash, Award, ArrowRight, TrendingUp, BookOpen } from "lucide-vue-next";

const route = useRoute();
const router = useRouter();
const interviewId = route.params.id;
const messages = ref([]);
const userInput = ref("");
const loading = ref(false);
const interviewInfo = ref(null);
const chatContainer = ref(null);

// Report State
const showReport = ref(false);
const reportData = ref(null);
const isFinishing = ref(false);
const isCompleted = ref(false);

// Progress State
const maxQuestions = ref(null);
const maxMinutes = ref(null);
const elapsedMinutes = ref(0);
const timerInterval = ref(null);
const startTime = ref(null);

const fetchInterview = async () => {
  try {
    const res = await api.get(`/career/interview/${interviewId}/`);
    interviewInfo.value = res.data;
    
    // exchanges의 feedback JSON 문자열을 파싱하여 rubric/feedback 분리
    const exchanges = (res.data.exchanges || []).map(ex => {
      if (ex.feedback && typeof ex.feedback === 'string') {
        try {
          const parsed = JSON.parse(ex.feedback);
          return {
            ...ex,
            rubric: parsed.rubric || null,
            feedback: parsed.feedback || '',
          };
        } catch {
          // JSON 파싱 실패 시 원래 텍스트 유지
          return { ...ex, rubric: null };
        }
      }
      return { ...ex, rubric: ex.rubric || null };
    });
    messages.value = exchanges;
    
    maxQuestions.value = res.data.max_questions;
    maxMinutes.value = res.data.max_minutes;
    
    // 완료된 면접인지 확인 (읽기 전용 모드)
    if (res.data.status === 'COMPLETED') {
      isCompleted.value = true;
      // 저장된 리포트가 있으면 로드
      if (res.data.report_data) {
        try {
          reportData.value = JSON.parse(res.data.report_data);
        } catch {
          // 파싱 실패 시 무시
        }
      }
    }
    
    // Start timer if time-limited and still in progress
    if (maxMinutes.value && !isCompleted.value) {
      startTime.value = new Date(res.data.created_at);
      startTimer();
    }
    
    scrollToBottom();
  } catch (e) {
    console.error("Failed to load interview", e);
    alert("면접 세션을 불러올 수 없습니다.");
    router.push("/portfolio");
  }
};

const startTimer = () => {
  if (timerInterval.value) clearInterval(timerInterval.value);
  timerInterval.value = setInterval(() => {
    const now = new Date();
    const created = new Date(interviewInfo.value?.created_at);
    elapsedMinutes.value = Math.floor((now - created) / 1000 / 60 * 10) / 10;
    
    // Auto-finish if time exceeded
    if (maxMinutes.value && elapsedMinutes.value >= maxMinutes.value && !showReport.value && !isFinishing.value) {
      clearInterval(timerInterval.value);
      autoFinish();
    }
  }, 1000);
};

const autoFinish = async () => {
  isFinishing.value = true;
  try {
    const res = await api.post(`/career/interview/${interviewId}/finish/`);
    reportData.value = res.data.report;
    showReport.value = true;
  } catch (e) {
    console.error(e);
    alert("면접 종료 처리 실패");
  } finally {
    isFinishing.value = false;
  }
};

const sendAnswer = async () => {
  if (!userInput.value.trim()) return;

  const currentExchange = messages.value[messages.value.length - 1];
  if (currentExchange) {
    currentExchange.answer = userInput.value;
  }

  loading.value = true;
  const answerText = userInput.value;
  userInput.value = "";
  scrollToBottom();

  try {
    const res = await api.post(`/career/interview/${interviewId}/chat/`, {
      answer: answerText,
    });

    // Update with Rubric feedback
    if (currentExchange) {
      currentExchange.feedback = res.data.feedback;
      currentExchange.score = res.data.overall_score || res.data.score;
      currentExchange.rubric = res.data.rubric || null;
    }

    // Check auto_finish signal from backend
    if (res.data.auto_finish) {
      // Wait a moment for user to see feedback, then auto-finish
      setTimeout(async () => {
        await autoFinish();
      }, 2000);
    } else if (res.data.next_question) {
      messages.value.push({
        id: Date.now(),
        question: res.data.next_question,
        answer: "",
        feedback: "",
        score: 0,
        rubric: null,
      });
    }
  } catch (e) {
    console.error(e);
    alert("답변 전송 실패");
  } finally {
    loading.value = false;
    scrollToBottom();
  }
};

const finishInterview = async () => {
  if (!confirm("면접을 종료하고 결과 리포트를 확인하시겠습니까?")) return;
  await autoFinish();
};

// 저장된 리포트가 없는 과거 면접의 결과 (재)생성
const generateReport = async () => {
  isFinishing.value = true;
  try {
    const res = await api.post(`/career/interview/${interviewId}/finish/`);
    reportData.value = res.data.report;
    showReport.value = true;
  } catch (e) {
    console.error(e);
    alert("결과 생성 실패: " + (e.response?.data?.error || e.message));
  } finally {
    isFinishing.value = false;
  }
};

// Rubric dimension labels
const dimensionLabels = {
  technical_depth: { label: "기술적 깊이", icon: "🔬" },
  logical_coherence: { label: "논리적 일관성", icon: "🧠" },
  communication: { label: "소통 능력", icon: "💬" },
  problem_solving: { label: "문제 해결력", icon: "🔧" },
};

// 종합 점수: msg.score가 있으면 사용, 없으면 rubric 평균 계산
const getOverallScore = (msg) => {
  if (msg.score && msg.score > 0) return msg.score;
  if (msg.rubric) {
    const validKeys = Object.keys(dimensionLabels);
    const scores = validKeys
      .filter(k => msg.rubric[k]?.score)
      .map(k => msg.rubric[k].score);
    if (scores.length > 0) {
      return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
    }
  }
  return 0;
};

const getScoreClass = (score) => {
  if (score >= 80) return "high";
  if (score >= 50) return "mid";
  return "low";
};

const getGradeClass = (grade) => {
  if (['S', 'A'].includes(grade)) return 'grade-high';
  if (['B', 'C'].includes(grade)) return 'grade-mid';
  return 'grade-low';
};

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  });
};

// Questions answered count
const answeredCount = computed(() => {
  return messages.value.filter((m) => m.answer && m.score > 0).length;
});

// Progress percentage
const progressPercent = computed(() => {
  if (maxQuestions.value) {
    return Math.min(100, Math.round((answeredCount.value / maxQuestions.value) * 100));
  }
  if (maxMinutes.value) {
    return Math.min(100, Math.round((elapsedMinutes.value / maxMinutes.value) * 100));
  }
  return 0;
});

const remainingLabel = computed(() => {
  if (maxQuestions.value) {
    const remaining = maxQuestions.value - answeredCount.value;
    return remaining > 0 ? `${remaining}문항 남음` : "마지막 질문!";
  }
  if (maxMinutes.value) {
    const remaining = Math.max(0, maxMinutes.value - elapsedMinutes.value);
    return remaining > 0 ? `${remaining.toFixed(1)}분 남음` : "시간 종료!";
  }
  return "";
});

onMounted(fetchInterview);
onUnmounted(() => {
  if (timerInterval.value) clearInterval(timerInterval.value);
});

const isRecording = ref(false);
</script>

<template>
  <div class="chat-view">
    <!-- Header -->
    <header class="chat-header" v-if="interviewInfo">
      <div class="persona-badge">
        <span class="icon">🤖</span>
        <span class="name">{{ interviewInfo.persona_display }}</span>
      </div>
      
      <!-- Progress Bar -->
      <div class="progress-section" v-if="maxQuestions || maxMinutes">
        <div class="progress-info">
          <span class="progress-icon" v-if="maxQuestions"><Hash :size="14" /></span>
          <span class="progress-icon" v-else-if="maxMinutes"><Clock :size="14" /></span>
          <span class="progress-label">
            <template v-if="maxQuestions">{{ answeredCount }} / {{ maxQuestions }}</template>
            <template v-else-if="maxMinutes">{{ elapsedMinutes.toFixed(1) }} / {{ maxMinutes }}분</template>
          </span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }" :class="{ warning: progressPercent >= 80 }"></div>
        </div>
        <span class="remaining-label" :class="{ urgent: progressPercent >= 80 }">{{ remainingLabel }}</span>
      </div>
      
      <div class="status">
        <span class="question-count">{{ answeredCount }}문항 완료</span>
        <span class="topic">{{ interviewInfo.portfolio_title }}</span>
        <button
          class="finish-btn"
          @click="finishInterview"
          :disabled="isFinishing || answeredCount === 0"
          v-if="!isCompleted"
        >
          <Flag :size="16" />
          {{ isFinishing ? "처리 중..." : "면접 종료" }}
        </button>
        <button class="exit-btn" @click="router.push('/interview/setup')">
          {{ isCompleted ? '↩ 면접 목록' : '나가기' }}
        </button>
      </div>
    </header>

    <!-- AI 활용 사전 고지 -->
    <div class="ai-disclosure-banner" v-if="!showReport">
      <span class="ai-disclosure-icon">🤖</span>
      <span
        >이 서비스는 <strong>AI(인공지능)</strong>를 활용하여 면접 질문 생성 및
        답변 평가를 수행합니다. 모든 결과는 AI가 자동 생성한 참고
        자료입니다.</span
      >
    </div>

    <!-- Auto-finish overlay -->
    <div v-if="isFinishing && !showReport" class="auto-finish-overlay">
      <div class="auto-finish-content">
        <div class="spinner"></div>
        <h3>면접이 종료되었습니다</h3>
        <p>AI가 종합 결과를 분석 중입니다...</p>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="chat-container" ref="chatContainer" v-if="!showReport">
      <div
        v-for="(msg, index) in messages"
        :key="msg.id || index"
        class="message-group"
      >
        <!-- AI Question -->
        <div class="ai-message">
          <div class="avatar">🤖</div>
          <div class="bubble question">
            <span class="ai-generated-tag">AI 생성</span>
            {{ msg.question }}
          </div>
        </div>

        <!-- User Answer -->
        <div v-if="msg.answer" class="user-message">
          <div class="bubble answer">
            {{ msg.answer }}
          </div>
          <div class="avatar">🧑‍💻</div>
        </div>

        <!-- Feedback with Rubric -->
        <div v-if="msg.feedback || msg.rubric" class="feedback-message">
          <div class="feedback-box">
            <div class="feedback-header">
              <span class="label">💡 면접관 피드백</span>
              <span
                class="score-badge"
                :class="getScoreClass(getOverallScore(msg))"
                v-if="getOverallScore(msg) > 0"
              >
                {{ getOverallScore(msg) }}점
              </span>
            </div>
            <p class="feedback-text">
              {{ typeof msg.feedback === "string" ? msg.feedback : "" }}
            </p>

            <!-- Rubric Breakdown (유효한 4개 차원만 렌더링) -->
            <div v-if="msg.rubric" class="rubric-grid">
              <template
                v-for="(val, key) in msg.rubric"
                :key="key"
              >
                <div v-if="dimensionLabels[key]" class="rubric-item">
                  <div class="rubric-label">
                    {{ dimensionLabels[key].icon }}
                    {{ dimensionLabels[key].label }}
                  </div>
                  <div class="rubric-bar-wrapper">
                    <div class="rubric-bar">
                      <div
                        class="rubric-fill"
                        :style="{ width: (val.score || 0) + '%' }"
                        :class="getScoreClass(val.score || 0)"
                      ></div>
                    </div>
                    <span class="rubric-score">{{ val.score || 0 }}</span>
                  </div>
                  <div class="rubric-comment">{{ val.comment || '' }}</div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="ai-message loading">
        <div class="avatar">🤖</div>
        <div class="bubble typing">
          <span>.</span><span>.</span><span>.</span>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════ -->
    <!-- Enhanced Report View -->
    <!-- ══════════════════════════════════════ -->
    <div v-if="showReport && reportData" class="report-view">
      <div class="report-card">
        <h2>📊 면접 결과 리포트</h2>
        <p class="report-subtitle">
          {{ reportData.persona }} 면접 | {{ reportData.total_questions }}문항 | {{ reportData.duration_minutes }}분 소요
        </p>

        <!-- Grade + Overall Score -->
        <div class="grade-section">
          <div class="grade-badge" :class="getGradeClass(reportData.ai_summary?.grade)" v-if="reportData.ai_summary?.grade">
            {{ reportData.ai_summary.grade }}
          </div>
          <div class="overall-score-section">
            <div
              class="big-score"
              :class="getScoreClass(reportData.overall_average)"
            >
              {{ reportData.overall_average }}
            </div>
            <div class="score-label">종합 점수</div>
          </div>
        </div>

        <!-- AI One-line Summary -->
        <div v-if="reportData.ai_summary?.one_line_summary" class="one-line-summary">
          <p>"{{ reportData.ai_summary.one_line_summary }}"</p>
        </div>

        <!-- Dimension Chart -->
        <div class="dimension-chart">
          <h3>차원별 분석</h3>
          <div class="dimension-bars">
            <div
              v-for="(dim, key) in reportData.dimensions"
              :key="key"
              class="dim-row"
            >
              <div class="dim-label">
                {{ dimensionLabels[key]?.icon }} {{ dim.label }}
              </div>
              <div class="dim-bar-track">
                <div
                  class="dim-bar-fill"
                  :style="{ width: dim.average + '%' }"
                  :class="getScoreClass(dim.average)"
                ></div>
              </div>
              <div class="dim-score" :class="getScoreClass(dim.average)">
                {{ dim.average }}
              </div>
            </div>
          </div>
        </div>

        <!-- Strengths & Weaknesses -->
        <div v-if="reportData.ai_summary" class="sw-section">
          <div class="sw-card strengths">
            <h4><TrendingUp :size="16" /> 강점</h4>
            <ul>
              <li v-for="(s, i) in reportData.ai_summary.strengths" :key="i">{{ s }}</li>
            </ul>
          </div>
          <div class="sw-card weaknesses">
            <h4><ArrowRight :size="16" /> 개선 포인트</h4>
            <ul>
              <li v-for="(w, i) in reportData.ai_summary.weaknesses" :key="i">{{ w }}</li>
            </ul>
          </div>
        </div>

        <!-- Improvement Tips -->
        <div v-if="reportData.ai_summary?.improvement_tips" class="tips-section">
          <h3><Award :size="18" /> 구체적 개선 가이드</h3>
          <div class="tips-list">
            <div class="tip-item" v-for="(tip, i) in reportData.ai_summary.improvement_tips" :key="i">
              <span class="tip-number">{{ i + 1 }}</span>
              <span>{{ tip }}</span>
            </div>
          </div>
        </div>

        <!-- Recommended Study -->
        <div v-if="reportData.ai_summary?.recommended_study" class="study-section">
          <h3><BookOpen :size="18" /> 추천 학습 주제</h3>
          <div class="study-tags">
            <span class="study-tag" v-for="(topic, i) in reportData.ai_summary.recommended_study" :key="i">
              {{ topic }}
            </span>
          </div>
        </div>

        <!-- Best/Worst -->
        <div class="highlight-section">
          <div class="highlight-card best">
            <h4>⭐ Best Answer</h4>
            <p class="highlight-question">
              {{ reportData.best_answer.question }}
            </p>
            <span class="highlight-score high"
              >{{ reportData.best_answer.score }}점</span
            >
          </div>
          <div class="highlight-card worst">
            <h4>📝 Needs Improvement</h4>
            <p class="highlight-question">
              {{ reportData.needs_improvement.question }}
            </p>
            <span class="highlight-score low"
              >{{ reportData.needs_improvement.score }}점</span
            >
          </div>
        </div>

        <!-- ═══════════════════════════════════ -->
        <!-- Skill Block Connection (Gamification) -->
        <!-- ═══════════════════════════════════ -->
        <div v-if="reportData.skill_connection" class="skill-connection-section">
          <h3>🧩 학습 ↔ 면접 연결 (Skill Connection)</h3>
          <p class="sc-subtitle">스킬 블록을 더 쌓으면 면접 역량이 함께 성장합니다.</p>

          <!-- Progress Ring + Stats -->
          <div class="sc-overview">
            <div class="sc-ring-wrapper">
              <svg class="sc-ring" viewBox="0 0 120 120">
                <circle class="sc-ring-bg" cx="60" cy="60" r="50" />
                <circle
                  class="sc-ring-fill"
                  cx="60" cy="60" r="50"
                  :stroke-dashoffset="314 - (314 * (reportData.skill_connection.progress_percent || 0) / 100)"
                />
              </svg>
              <div class="sc-ring-text">
                <span class="sc-ring-percent">{{ reportData.skill_connection.progress_percent || 0 }}%</span>
                <span class="sc-ring-label">스킬 진행률</span>
              </div>
            </div>

            <div class="sc-stats">
              <div class="sc-stat-item">
                <span class="sc-stat-value earned">{{ reportData.skill_connection.earned_count }}</span>
                <span class="sc-stat-label">획득한 블록</span>
              </div>
              <div class="sc-stat-divider"></div>
              <div class="sc-stat-item">
                <span class="sc-stat-value total">{{ reportData.skill_connection.total_count }}</span>
                <span class="sc-stat-label">전체 블록</span>
              </div>
              <div class="sc-stat-divider"></div>
              <div class="sc-stat-item">
                <span class="sc-stat-value remaining">{{ (reportData.skill_connection.total_count || 0) - (reportData.skill_connection.earned_count || 0) }}</span>
                <span class="sc-stat-label">미획득 블록</span>
              </div>
            </div>
          </div>

          <!-- Category Bars -->
          <div v-if="reportData.skill_connection.category_stats && Object.keys(reportData.skill_connection.category_stats).length > 0" class="sc-categories">
            <h4>카테고리별 현황</h4>
            <div
              v-for="(cat, key) in reportData.skill_connection.category_stats"
              :key="key"
              class="sc-cat-row"
            >
              <span class="sc-cat-name">{{ cat.name }}</span>
              <div class="sc-cat-bar-track">
                <div
                  class="sc-cat-bar-fill"
                  :style="{ width: cat.percent + '%' }"
                  :class="getScoreClass(cat.percent)"
                ></div>
              </div>
              <span class="sc-cat-count">{{ cat.earned }}/{{ cat.total }}</span>
            </div>
          </div>

          <!-- Recommended Skills (미획득 블록 추천) -->
          <div v-if="reportData.skill_connection.recommended_skills?.length > 0" class="sc-recommended">
            <h4>🔓 이 스킬을 획득하면 면접 역량이 UP!</h4>
            <div class="sc-skill-tags">
              <div
                v-for="(sk, i) in reportData.skill_connection.recommended_skills"
                :key="i"
                class="sc-skill-tag"
              >
                <span class="sc-skill-level">{{ sk.level === 1 ? '🌱' : sk.level === 2 ? '🌿' : '🌸' }}</span>
                <span class="sc-skill-name">{{ sk.name }}</span>
                <span class="sc-skill-cat">{{ sk.category }}</span>
              </div>
            </div>
          </div>

          <!-- Motivational CTA -->
          <div class="sc-motivation">
            <div class="sc-motivation-text">
              <strong>💡 학습이 곧 면접 경쟁력!</strong>
              <p>
                현재 <strong>{{ reportData.skill_connection.progress_percent || 0 }}%</strong>의 스킬을 획득했습니다.
                학습을 계속하면 더 풍부한 포트폴리오로 더 높은 면접 점수를 받을 수 있습니다.
              </p>
            </div>
            <button class="sc-cta-btn" @click="router.push('/dashboard')">
              📚 학습하러 가기
            </button>
          </div>
        </div>

        <!-- Disclaimer -->
        <div class="disclaimer">
          {{ reportData.disclaimer }}
        </div>
        <div class="non-deterministic-notice">
          📌 이 결과는 실제 채용 결과와 무관하며, 학습 참고 목적으로만
          활용하시기 바랍니다.
        </div>

        <div class="report-actions">
          <button class="btn-back" @click="showReport = false">
            💬 대화 내용 보기
          </button>
          <button class="btn-done" @click="router.push('/portfolio')">
            ✅ 완료
          </button>
        </div>
      </div>
    </div>

    <!-- 복습 모드 배너 (완료된 면접 열람 시) -->
    <div v-if="isCompleted && !showReport" class="review-banner">
      <div class="review-banner-content">
        <span class="review-icon">📖</span>
        <div>
          <strong>복습 모드</strong>
          <p>이전 면접의 질문과 피드백을 복습하고 있습니다.</p>
        </div>
        <button
          v-if="reportData"
          class="btn-view-report"
          @click="showReport = true"
        >
          📊 결과 보기
        </button>
        <button
          v-else
          class="btn-view-report generating"
          @click="generateReport"
          :disabled="isFinishing"
        >
          {{ isFinishing ? '생성 중...' : '📊 결과 생성' }}
        </button>
        <button class="btn-new-interview" @click="router.push('/interview/setup')">
          🎙️ 새 면접 시작
        </button>
      </div>
    </div>

    <!-- Input Area (진행 중인 면접만) -->
    <div class="input-area" v-if="!showReport && !isFinishing && !isCompleted">
      <div class="input-wrapper">
        <textarea
          v-model="userInput"
          placeholder="답변을 입력하세요... (Enter로 전송)"
          @keydown.enter.prevent="sendAnswer"
        ></textarea>
        <div class="controls">
          <button class="icon-btn record" :class="{ active: isRecording }">
            <Mic v-if="!isRecording" size="20" />
            <StopCircle v-else size="20" />
          </button>
          <button
            class="send-btn"
            @click="sendAnswer"
            :disabled="loading || !userInput.trim()"
          >
            <Send size="20" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1a1a2e;
  color: white;
}

/* ── AI 기본법 컴플라이언스 UI ── */
.ai-disclosure-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: rgba(79, 172, 254, 0.08);
  border-bottom: 1px solid rgba(79, 172, 254, 0.15);
  font-size: 12px;
  color: #9ab3d0;
  line-height: 1.5;
}
.ai-disclosure-icon {
  font-size: 16px;
  flex-shrink: 0;
}
.ai-disclosure-banner strong {
  color: #4facfe;
}

.ai-generated-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  background: rgba(79, 172, 254, 0.15);
  color: #4facfe;
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 6px;
  vertical-align: middle;
  letter-spacing: 0.3px;
}

.non-deterministic-notice {
  background: rgba(100, 181, 246, 0.06);
  border: 1px solid rgba(100, 181, 246, 0.15);
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 12px;
  color: #90a4ae;
  line-height: 1.5;
  margin-bottom: 24px;
  text-align: center;
}

/* ── Header ── */
.chat-header {
  padding: 15px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.persona-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: bold;
  font-size: 1.1rem;
  flex-shrink: 0;
}
.status {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.topic {
  color: #888;
  font-size: 0.9rem;
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.question-count {
  color: #4facfe;
  font-size: 0.85rem;
  font-weight: 600;
  background: rgba(79, 172, 254, 0.1);
  padding: 4px 10px;
  border-radius: 12px;
}
.exit-btn {
  background: none;
  border: 1px solid #444;
  color: #aaa;
  padding: 5px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.finish-btn {
  background: linear-gradient(135deg, #ff6b6b, #ee5a24);
  border: none;
  color: white;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: opacity 0.2s;
}
.finish-btn:hover {
  opacity: 0.85;
}
.finish-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Progress Bar ── */
.progress-section {
  flex: 1;
  max-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.progress-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #aaa;
}
.progress-icon {
  display: flex;
  color: #4facfe;
}
.progress-label {
  font-weight: 600;
  color: #ddd;
}
.progress-bar {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4facfe, #00f2fe);
  border-radius: 3px;
  transition: width 0.5s ease;
}
.progress-fill.warning {
  background: linear-gradient(90deg, #ff9800, #f44336);
}
.remaining-label {
  font-size: 11px;
  color: #888;
  text-align: right;
}
.remaining-label.urgent {
  color: #ff6b6b;
  font-weight: 600;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── Auto Finish Overlay ── */
.auto-finish-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(10px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auto-finish-content {
  text-align: center;
  animation: slideUp 0.5s ease;
}
.auto-finish-content h3 {
  font-size: 1.5rem;
  margin: 20px 0 8px;
  background: linear-gradient(to right, #4facfe, #00f2fe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.auto-finish-content p {
  color: #aaa;
}
.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: #4facfe;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Chat ── */
.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
}
.message-group {
  margin-bottom: 30px;
}

.ai-message {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
.user-message {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-bottom: 10px;
}
.avatar {
  font-size: 24px;
  margin-top: 5px;
}

.bubble {
  max-width: 70%;
  padding: 12px 18px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 0.95rem;
}
.bubble.question {
  background: #2d2d44;
  color: #eee;
  border-top-left-radius: 4px;
}
.bubble.answer {
  background: #4facfe;
  color: white;
  border-top-right-radius: 4px;
}

.feedback-message {
  display: flex;
  justify-content: flex-start;
  margin-left: 45px;
  max-width: 75%;
}
.feedback-box {
  background: rgba(255, 255, 0, 0.04);
  border: 1px solid rgba(255, 255, 0, 0.15);
  padding: 16px;
  border-radius: 12px;
  width: 100%;
}
.feedback-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.8rem;
  color: #ffd700;
  font-weight: bold;
}
.feedback-text {
  color: #ccc;
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0 0 12px;
}
.score-badge {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  font-size: 13px;
}
.score-badge.high,
.high {
  color: #4caf50;
}
.score-badge.mid,
.mid {
  color: #ff9800;
}
.score-badge.low,
.low {
  color: #f44336;
}

/* ── Rubric Grid ── */
.rubric-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rubric-label {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 3px;
}
.rubric-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rubric-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
.rubric-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}
.rubric-fill.high {
  background: #4caf50;
}
.rubric-fill.mid {
  background: #ff9800;
}
.rubric-fill.low {
  background: #f44336;
}
.rubric-score {
  font-size: 12px;
  font-weight: 700;
  min-width: 28px;
  text-align: right;
}
.rubric-comment {
  font-size: 11px;
  color: #888;
  margin-top: 1px;
}

/* ══════════════════════════════════════ */
/* ── Enhanced Report View ── */
/* ══════════════════════════════════════ */
.report-view {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
.report-card {
  background: #16213e;
  border-radius: 20px;
  padding: 40px;
  max-width: 750px;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.report-card h2 {
  text-align: center;
  margin: 0 0 5px;
  font-size: 24px;
}
.report-subtitle {
  text-align: center;
  color: #888;
  margin: 0 0 30px;
  font-size: 14px;
}

/* Grade + Score */
.grade-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 28px;
}
.grade-badge {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 900;
  letter-spacing: -2px;
}
.grade-badge.grade-high {
  background: linear-gradient(135deg, rgba(76, 175, 80, 0.2), rgba(76, 175, 80, 0.05));
  color: #4caf50;
  border: 2px solid rgba(76, 175, 80, 0.3);
}
.grade-badge.grade-mid {
  background: linear-gradient(135deg, rgba(255, 152, 0, 0.2), rgba(255, 152, 0, 0.05));
  color: #ff9800;
  border: 2px solid rgba(255, 152, 0, 0.3);
}
.grade-badge.grade-low {
  background: linear-gradient(135deg, rgba(244, 67, 54, 0.2), rgba(244, 67, 54, 0.05));
  color: #f44336;
  border: 2px solid rgba(244, 67, 54, 0.3);
}

.overall-score-section {
  text-align: center;
}
.big-score {
  font-size: 56px;
  font-weight: 800;
  display: inline-block;
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.big-score.high {
  background: linear-gradient(135deg, #4caf50, #81c784);
  -webkit-background-clip: text;
}
.big-score.mid {
  background: linear-gradient(135deg, #ff9800, #ffb74d);
  -webkit-background-clip: text;
}
.big-score.low {
  background: linear-gradient(135deg, #f44336, #e57373);
  -webkit-background-clip: text;
}
.score-label {
  color: #888;
  font-size: 14px;
  margin-top: 4px;
}

/* One-Line Summary */
.one-line-summary {
  text-align: center;
  margin-bottom: 32px;
  padding: 16px 24px;
  background: rgba(79, 172, 254, 0.06);
  border: 1px solid rgba(79, 172, 254, 0.12);
  border-radius: 12px;
}
.one-line-summary p {
  font-size: 1.05rem;
  font-weight: 500;
  font-style: italic;
  color: #bbb;
  margin: 0;
}

/* Dimension Chart */
.dimension-chart {
  margin-bottom: 32px;
}
.dimension-chart h3 {
  font-size: 16px;
  margin: 0 0 16px;
  color: #ddd;
}
.dim-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.dim-label {
  min-width: 130px;
  font-size: 13px;
  color: #bbb;
}
.dim-bar-track {
  flex: 1;
  height: 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  overflow: hidden;
}
.dim-bar-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.8s ease;
}
.dim-bar-fill.high {
  background: linear-gradient(90deg, #4caf50, #81c784);
}
.dim-bar-fill.mid {
  background: linear-gradient(90deg, #ff9800, #ffb74d);
}
.dim-bar-fill.low {
  background: linear-gradient(90deg, #f44336, #e57373);
}
.dim-score {
  min-width: 36px;
  text-align: right;
  font-weight: 700;
  font-size: 14px;
}

/* Strengths & Weaknesses */
.sw-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 28px;
}
.sw-card {
  padding: 20px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.sw-card.strengths {
  background: rgba(76, 175, 80, 0.06);
  border-color: rgba(76, 175, 80, 0.15);
}
.sw-card.weaknesses {
  background: rgba(255, 152, 0, 0.06);
  border-color: rgba(255, 152, 0, 0.15);
}
.sw-card h4 {
  margin: 0 0 12px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sw-card.strengths h4 { color: #4caf50; }
.sw-card.weaknesses h4 { color: #ff9800; }
.sw-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.sw-card li {
  font-size: 13px;
  color: #ccc;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  line-height: 1.5;
}
.sw-card li:last-child {
  border-bottom: none;
}
.sw-card li::before {
  content: "•";
  margin-right: 8px;
  font-weight: bold;
}
.sw-card.strengths li::before { color: #4caf50; }
.sw-card.weaknesses li::before { color: #ff9800; }

/* Improvement Tips */
.tips-section {
  margin-bottom: 28px;
}
.tips-section h3 {
  font-size: 15px;
  margin: 0 0 14px;
  color: #ddd;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tips-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  font-size: 13px;
  color: #ccc;
  line-height: 1.5;
}
.tip-number {
  width: 24px;
  height: 24px;
  background: rgba(79, 172, 254, 0.15);
  color: #4facfe;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

/* Recommended Study */
.study-section {
  margin-bottom: 28px;
}
.study-section h3 {
  font-size: 15px;
  margin: 0 0 14px;
  color: #ddd;
  display: flex;
  align-items: center;
  gap: 8px;
}
.study-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.study-tag {
  padding: 8px 16px;
  background: rgba(161, 140, 209, 0.12);
  border: 1px solid rgba(161, 140, 209, 0.2);
  border-radius: 20px;
  font-size: 13px;
  color: #a18cd1;
  font-weight: 500;
}

/* Best/Worst */
.highlight-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 28px;
}
.highlight-card {
  padding: 18px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.highlight-card.best {
  background: rgba(76, 175, 80, 0.08);
}
.highlight-card.worst {
  background: rgba(244, 67, 54, 0.08);
}
.highlight-card h4 {
  margin: 0 0 8px;
  font-size: 14px;
}
.highlight-question {
  font-size: 13px;
  color: #aaa;
  line-height: 1.4;
  margin: 0 0 8px;
}
.highlight-score {
  font-size: 18px;
  font-weight: 800;
}

.disclaimer {
  background: rgba(255, 193, 7, 0.06);
  border: 1px solid rgba(255, 193, 7, 0.2);
  padding: 14px;
  border-radius: 8px;
  font-size: 12px;
  color: #bbb;
  line-height: 1.5;
  margin-bottom: 14px;
}

.report-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.btn-back,
.btn-done {
  padding: 12px 24px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s;
}
.btn-back:hover,
.btn-done:hover {
  transform: translateY(-2px);
}
.btn-back {
  background: #2d2d44;
  color: #ccc;
}
.btn-done {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  color: white;
}

/* ── Input Area ── */
.input-area {
  padding: 20px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.input-wrapper {
  background: #2d2d44;
  border-radius: 20px;
  padding: 10px;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
textarea {
  flex: 1;
  background: none;
  border: none;
  color: white;
  padding: 10px;
  outline: none;
  resize: none;
  height: 50px;
  font-size: 1rem;
}
.controls {
  display: flex;
  gap: 5px;
}
.icon-btn,
.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon-btn {
  background: rgba(255, 255, 255, 0.1);
  color: #ccc;
}
.send-btn {
  background: #4facfe;
  color: white;
}
.send-btn:disabled {
  background: #555;
  cursor: not-allowed;
}

/* Typing Animation */
.bubble.typing span {
  animation: blink 1.4s infinite both;
  font-size: 20px;
  line-height: 10px;
  margin: 0 2px;
}
.bubble.typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.bubble.typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0% {
    opacity: 0.2;
  }
  20% {
    opacity: 1;
  }
  100% {
    opacity: 0.2;
  }
}

/* ── Review Banner ── */
.review-banner {
  padding: 14px 20px;
  background: rgba(79, 172, 254, 0.06);
  border-top: 1px solid rgba(79, 172, 254, 0.15);
}
.review-banner-content {
  display: flex;
  align-items: center;
  gap: 14px;
  max-width: 900px;
  margin: 0 auto;
}
.review-icon {
  font-size: 28px;
  flex-shrink: 0;
}
.review-banner-content strong {
  color: #4facfe;
  font-size: 0.95rem;
  display: block;
}
.review-banner-content p {
  color: #888;
  font-size: 0.8rem;
  margin: 2px 0 0;
}
.review-banner-content div {
  flex: 1;
}
.btn-new-interview {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.2s;
}
.btn-new-interview:hover {
  transform: scale(1.03);
}
.btn-view-report {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.2s;
}
.btn-view-report:hover {
  transform: scale(1.03);
}
.btn-view-report.generating {
  background: linear-gradient(135deg, #ff9800, #f44336);
}
.btn-view-report:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ═══════════════════════════════════ */
/* ── Skill Connection (Gamification) ── */
/* ═══════════════════════════════════ */
.skill-connection-section {
  margin-bottom: 28px;
  padding: 28px;
  background: linear-gradient(135deg, rgba(79, 172, 254, 0.04), rgba(0, 242, 254, 0.04));
  border: 1px solid rgba(79, 172, 254, 0.12);
  border-radius: 16px;
}
.skill-connection-section h3 {
  font-size: 16px;
  margin: 0 0 4px;
  color: #eee;
}
.sc-subtitle {
  color: #888;
  font-size: 13px;
  margin: 0 0 24px;
}

/* Overview: Ring + Stats */
.sc-overview {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 24px;
  padding: 20px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 14px;
}
.sc-ring-wrapper {
  position: relative;
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}
.sc-ring {
  width: 120px;
  height: 120px;
  transform: rotate(-90deg);
}
.sc-ring-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.06);
  stroke-width: 10;
}
.sc-ring-fill {
  fill: none;
  stroke: #4facfe;
  stroke-width: 10;
  stroke-linecap: round;
  stroke-dasharray: 314;
  transition: stroke-dashoffset 1s ease;
}
.sc-ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.sc-ring-percent {
  font-size: 22px;
  font-weight: 800;
  color: #4facfe;
}
.sc-ring-label {
  font-size: 10px;
  color: #888;
  margin-top: 2px;
}

.sc-stats {
  display: flex;
  gap: 24px;
  flex: 1;
  justify-content: center;
}
.sc-stat-item {
  text-align: center;
}
.sc-stat-value {
  display: block;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}
.sc-stat-value.earned { color: #4caf50; }
.sc-stat-value.total { color: #4facfe; }
.sc-stat-value.remaining { color: #ff9800; }
.sc-stat-label {
  font-size: 11px;
  color: #888;
  display: block;
  margin-top: 4px;
}
.sc-stat-divider {
  width: 1px;
  background: rgba(255, 255, 255, 0.08);
  align-self: stretch;
}

/* Category Bars */
.sc-categories {
  margin-bottom: 20px;
}
.sc-categories h4 {
  font-size: 13px;
  color: #aaa;
  margin: 0 0 12px;
}
.sc-cat-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.sc-cat-name {
  min-width: 80px;
  font-size: 12px;
  color: #bbb;
}
.sc-cat-bar-track {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  overflow: hidden;
}
.sc-cat-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.8s ease;
}
.sc-cat-bar-fill.high { background: linear-gradient(90deg, #4caf50, #81c784); }
.sc-cat-bar-fill.mid { background: linear-gradient(90deg, #ff9800, #ffb74d); }
.sc-cat-bar-fill.low { background: linear-gradient(90deg, #f44336, #e57373); }
.sc-cat-count {
  min-width: 40px;
  text-align: right;
  font-size: 12px;
  color: #aaa;
  font-weight: 600;
}

/* Recommended Skills */
.sc-recommended {
  margin-bottom: 20px;
}
.sc-recommended h4 {
  font-size: 13px;
  color: #aaa;
  margin: 0 0 12px;
}
.sc-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sc-skill-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(255, 152, 0, 0.08);
  border: 1px solid rgba(255, 152, 0, 0.15);
  border-radius: 10px;
  font-size: 12px;
}
.sc-skill-level {
  font-size: 16px;
}
.sc-skill-name {
  color: #eee;
  font-weight: 600;
}
.sc-skill-cat {
  color: #888;
  font-size: 11px;
}

/* Motivation CTA */
.sc-motivation {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  background: linear-gradient(135deg, rgba(79, 172, 254, 0.08), rgba(102, 126, 234, 0.08));
  border: 1px solid rgba(79, 172, 254, 0.15);
  border-radius: 12px;
}
.sc-motivation-text {
  flex: 1;
}
.sc-motivation-text strong {
  color: #4facfe;
  font-size: 14px;
  display: block;
  margin-bottom: 4px;
}
.sc-motivation-text p {
  color: #999;
  font-size: 12px;
  margin: 0;
  line-height: 1.5;
}
.sc-motivation-text p strong {
  color: #4facfe;
}
.sc-cta-btn {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.2s;
}
.sc-cta-btn:hover {
  transform: scale(1.03);
}
</style>
