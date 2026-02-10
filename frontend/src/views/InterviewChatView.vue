<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api/axios';
import { Send, Mic, StopCircle } from 'lucide-vue-next';

const route = useRoute();
const router = useRouter();
const interviewId = route.params.id;
const messages = ref([]);
const userInput = ref('');
const loading = ref(false);
const interviewInfo = ref(null);
const chatContainer = ref(null);

const fetchInterview = async () => {
    try {
        const res = await api.get(`/career/interview/${interviewId}/`);
        interviewInfo.value = res.data;
        messages.value = res.data.exchanges || [];
        scrollToBottom();
    } catch (e) {
        console.error("Failed to load interview", e);
        alert("면접 세션을 불러올 수 없습니다.");
        router.push('/portfolio');
    }
};

const sendAnswer = async () => {
    if (!userInput.value.trim()) return;
    
    // Optimistic Update (Show user message immediately)
    const currentExchange = messages.value[messages.value.length - 1];
    if (currentExchange) {
        currentExchange.answer = userInput.value; // Temporary display
    }
    
    loading.value = true;
    const answerText = userInput.value;
    userInput.value = '';
    scrollToBottom();
    
    try {
        const res = await api.post(`/career/interview/${interviewId}/chat/`, {
            answer: answerText
        });
        
        // Update current exchange with feedback & score
        if (currentExchange) {
            currentExchange.feedback = res.data.feedback;
            currentExchange.score = res.data.score;
        }
        
        // Add new question
        if (res.data.next_question) {
            messages.value.push({
                id: Date.now(), // Temporary ID
                question: res.data.next_question,
                answer: '',
                feedback: '',
                score: 0
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

const scrollToBottom = () => {
    nextTick(() => {
        if (chatContainer.value) {
            chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
        }
    });
};

onMounted(fetchInterview);

// [Optional] Voice Input Logic (Future)
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
                <span class="topic">{{ interviewInfo.portfolio_title }}</span>
                <button class="exit-btn" @click="router.push('/portfolio')">나가기</button>
            </div>
        </header>
        
        <!-- Chat Area -->
        <div class="chat-container" ref="chatContainer">
            <div v-for="(msg, index) in messages" :key="msg.id || index" class="message-group">
                
                <!-- AI Question -->
                <div class="ai-message">
                    <div class="avatar">🤖</div>
                    <div class="bubble question">
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
                
                <!-- Feedback (Only show if answer exists and isn't loading this specific msg) -->
                <div v-if="msg.feedback" class="feedback-message">
                    <div class="feedback-box">
                        <div class="feedback-header">
                            <span class="label">💡 면접관 피드백</span>
                            <span class="score-badge" :class="getScoreClass(msg.score)">
                                {{ msg.score }}점
                            </span>
                        </div>
                        <p>{{ msg.feedback }}</p>
                    </div>
                </div>
            </div>
            
            <!-- Loading Indicator -->
            <div v-if="loading" class="ai-message loading">
                <div class="avatar">🤖</div>
                <div class="bubble typing">
                    <span>.</span><span>.</span><span>.</span>
                </div>
            </div>
        </div>
        
        <!-- Input Area -->
        <div class="input-area">
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
                    <button class="send-btn" @click="sendAnswer" :disabled="loading || !userInput.trim()">
                        <Send size="20" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
// Helper for score class
function getScoreClass(score) {
    if (score >= 80) return 'high';
    if (score >= 50) return 'mid';
    return 'low';
}
</script>

<style scoped>
.chat-view {
    display: flex; flex-direction: column; height: 100vh;
    background: #1a1a2e; color: white;
}
.chat-header {
    padding: 15px 20px; background: rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    display: flex; justify-content: space-between; align-items: center;
}
.persona-badge { display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 1.1rem; }
.status { display: flex; align-items: center; gap: 15px; }
.topic { color: #888; font-size: 0.9rem; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.exit-btn { background: none; border: 1px solid #444; color: #aaa; padding: 5px 12px; border-radius: 4px; cursor: pointer; }

.chat-container {
    flex: 1; overflow-y: auto; padding: 20px; scroll-behavior: smooth;
}
.message-group { margin-bottom: 30px; }

.ai-message { display: flex; gap: 10px; margin-bottom: 10px; }
.user-message { display: flex; gap: 10px; justify-content: flex-end; margin-bottom: 10px; }
.avatar { font-size: 24px; margin-top: 5px; }

.bubble {
    max-width: 70%; padding: 12px 18px; border-radius: 18px; line-height: 1.5; font-size: 0.95rem;
    position: relative;
}
.bubble.question {
    background: #2d2d44; color: #eee; border-top-left-radius: 4px;
}
.bubble.answer {
    background: #4facfe; color: white; border-top-right-radius: 4px;
}

.feedback-message { display: flex; justify-content: flex-start; margin-left: 45px; max-width: 70%; }
.feedback-box {
    background: rgba(255, 255, 0, 0.05); border: 1px solid rgba(255, 255, 0, 0.2);
    padding: 12px; border-radius: 8px; width: 100%;
}
.feedback-header { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.8rem; color: #ffd700; font-weight: bold; }
.score-badge { padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.3); }
.score-badge.high { color: #4caf50; }
.score-badge.mid { color: #ff9800; }
.score-badge.low { color: #f44336; }

.input-area {
    padding: 20px; background: rgba(0, 0, 0, 0.2); border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.input-wrapper {
    background: #2d2d44; border-radius: 20px; padding: 10px; display: flex; gap: 10px; align-items: flex-end;
}
textarea {
    flex: 1; background: none; border: none; color: white; padding: 10px; outline: none; resize: none; height: 50px; font-size: 1rem;
}
.controls { display: flex; gap: 5px; }
.icon-btn, .send-btn {
    width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
}
.icon-btn { background: rgba(255, 255, 255, 0.1); color: #ccc; }
.send-btn { background: #4facfe; color: white; }
.send-btn:disabled { background: #555; cursor: not-allowed; }

/* Typing Animation */
.bubble.typing span {
    animation: blink 1.4s infinite both; font-size: 20px; line-height: 10px; margin: 0 2px;
}
.bubble.typing span:nth-child(2) { animation-delay: 0.2s; }
.bubble.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }
</style>
