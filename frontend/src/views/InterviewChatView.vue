<script setup>
import { ref, onMounted, nextTick, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../api/axios";
import { Send, Mic, StopCircle, Flag } from "lucide-vue-next";

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

const fetchInterview = async () => {
  try {
    const res = await api.get(`/career/interview/${interviewId}/`);
    interviewInfo.value = res.data;
    messages.value = res.data.exchanges || [];
    scrollToBottom();
  } catch (e) {
    console.error("Failed to load interview", e);
    alert("면접 세션을 불러올 수 없습니다.");
    router.push("/portfolio");
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

    if (res.data.next_question) {
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

// Rubric dimension labels
const dimensionLabels = {
  technical_depth: { label: "기술적 깊이", icon: "🔬" },
  logical_coherence: { label: "논리적 일관성", icon: "🧠" },
  communication: { label: "소통 능력", icon: "💬" },
  problem_solving: { label: "문제 해결력", icon: "🔧" },
};

const getScoreClass = (score) => {
  if (score >= 80) return "high";
  if (score >= 50) return "mid";
  return "low";
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

onMounted(fetchInterview);

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
      <div class="status">
        <span class="question-count">{{ answeredCount }}문항 완료</span>
        <span class="topic">{{ interviewInfo.portfolio_title }}</span>
        <button
          class="finish-btn"
          @click="finishInterview"
          :disabled="isFinishing || answeredCount === 0"
        >
          <Flag :size="16" />
          {{ isFinishing ? "처리 중..." : "면접 종료" }}
        </button>
        <button class="exit-btn" @click="router.push('/portfolio')">
          나가기
        </button>
      </div>
    </header>

    <!-- AI 활용 사전 고지 (AI 기본법 투명성 의무) -->
    <div class="ai-disclosure-banner" v-if="!showReport">
      <span class="ai-disclosure-icon">🤖</span>
      <span
        >이 서비스는 <strong>AI(인공지능)</strong>를 활용하여 면접 질문 생성 및
        답변 평가를 수행합니다. 모든 결과는 AI가 자동 생성한 참고
        자료입니다.</span
      >
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
              <span class="score-badge" :class="getScoreClass(msg.score)">
                {{ msg.score }}점
              </span>
            </div>
            <p class="feedback-text">
              {{ typeof msg.feedback === "string" ? msg.feedback : "" }}
            </p>

            <!-- Rubric Breakdown -->
            <div v-if="msg.rubric" class="rubric-grid">
              <div
                v-for="(val, key) in msg.rubric"
                :key="key"
                class="rubric-item"
              >
                <div class="rubric-label">
                  {{ dimensionLabels[key]?.icon }}
                  {{ dimensionLabels[key]?.label || key }}
                </div>
                <div class="rubric-bar-wrapper">
                  <div class="rubric-bar">
                    <div
                      class="rubric-fill"
                      :style="{ width: val.score + '%' }"
                      :class="getScoreClass(val.score)"
                    ></div>
                  </div>
                  <span class="rubric-score">{{ val.score }}</span>
                </div>
                <div class="rubric-comment">{{ val.comment }}</div>
              </div>
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
    <!-- Report View -->
    <!-- ══════════════════════════════════════ -->
    <div v-if="showReport && reportData" class="report-view">
      <div class="report-card">
        <h2>📊 면접 결과 리포트</h2>
        <p class="report-subtitle">
          {{ reportData.persona }} 면접 | {{ reportData.total_questions }}문항
        </p>

        <!-- Overall Score -->
        <div class="overall-score-section">
          <div
            class="big-score"
            :class="getScoreClass(reportData.overall_average)"
          >
            {{ reportData.overall_average }}
          </div>
          <div class="score-label">종합 점수</div>
        </div>

        <!-- Radar-style Dimension Chart (CSS-based) -->
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

        <!-- Disclaimer + 비결정성 고지 (AI 기본법) -->
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

    <!-- Input Area -->
    <div class="input-area" v-if="!showReport">
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
.chat-header {
  padding: 15px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.persona-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: bold;
  font-size: 1.1rem;
}
.status {
  display: flex;
  align-items: center;
  gap: 12px;
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
.rubric-item {
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

/* ── Report View ── */
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
  max-width: 700px;
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

.overall-score-section {
  text-align: center;
  margin-bottom: 36px;
}
.big-score {
  font-size: 64px;
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
  margin-bottom: 24px;
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
</style>
