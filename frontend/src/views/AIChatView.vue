<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { MessageSquare, Send, Trash2, Plus, BookOpen, ArrowLeft, Sparkles, Link2, Search, X } from 'lucide-vue-next';
import api from '../api/axios';
import { getChatSessions, createChatSession, getChatSession, deleteChatSession, askAITutor } from '../api/learning';

const router = useRouter();
const route = useRoute();

// State
const sessions = ref([]);
const activeSession = ref(null);
const messages = ref([]);
const newMessage = ref('');
const isLoading = ref(false);
const isSending = ref(false);
const chatContainer = ref(null);
const myLectures = ref([]);
const selectedLectureId = ref(null);
const showNewChat = ref(false);
const newChatTitle = ref('');

// RAG 원문 검색
const showSearchPanel = ref(false);
const searchQuery = ref('');
const searchResults = ref([]);
const isSearching = ref(false);

const searchRAG = async () => {
    const q = searchQuery.value.trim();
    if (!q) return;
    isSearching.value = true;
    try {
        const { data } = await api.get('/learning/rag/search/', {
            params: { q, lecture_id: selectedLectureId.value || undefined }
        });
        searchResults.value = Array.isArray(data) ? data : [];
    } catch (e) {
        searchResults.value = [];
        alert('검색 실패');
    }
    isSearching.value = false;
};

const toggleSearchPanel = () => {
    showSearchPanel.value = !showSearchPanel.value;
    if (showSearchPanel.value) { searchQuery.value = ''; searchResults.value = []; }
};

// Computed
const activeLectureName = computed(() => {
    if (!activeSession.value) return '';
    const lec = myLectures.value.find(l => l.id === activeSession.value.lecture);
    return lec ? lec.title : '';
});

// Load lectures
const fetchLectures = async () => {
    try {
        const { data } = await api.get('/learning/lectures/my/');
        myLectures.value = data;
        if (data.length > 0 && !selectedLectureId.value) {
            selectedLectureId.value = data[0].id;
        }
    } catch (e) { /* silent */ }
};

// Load sessions
const fetchSessions = async () => {
    isLoading.value = true;
    try {
        const data = await getChatSessions(selectedLectureId.value);
        sessions.value = Array.isArray(data) ? data : (data.results || []);
    } catch (e) { sessions.value = []; }
    isLoading.value = false;
};

// Select session
const selectSession = async (session) => {
    try {
        const data = await getChatSession(session.id);
        activeSession.value = data;
        messages.value = data.messages || [];
        await nextTick();
        scrollToBottom();
    } catch (e) { /* silent */ }
};

// New chat
const openNewChat = () => {
    showNewChat.value = true;
    newChatTitle.value = '';
};

const startNewChat = async () => {
    if (!selectedLectureId.value) return;
    try {
        const data = await createChatSession(
            selectedLectureId.value,
            newChatTitle.value || '새 대화'
        );
        showNewChat.value = false;
        await fetchSessions();
        await selectSession(data);
    } catch (e) { /* silent */ }
};

// Delete session
const removeSession = async (sessionId, e) => {
    e.stopPropagation();
    if (!confirm('이 대화를 삭제하시겠습니까?')) return;
    try {
        await deleteChatSession(sessionId);
        if (activeSession.value?.id === sessionId) {
            activeSession.value = null;
            messages.value = [];
        }
        await fetchSessions();
    } catch (e) { /* silent */ }
};

// Send message
const sendMessage = async () => {
    const text = newMessage.value.trim();
    if (!text || !activeSession.value || isSending.value) return;

    // Add user message immediately
    messages.value.push({
        id: Date.now(),
        sender: 'USER',
        message: text,
        created_at: new Date().toISOString(),
    });
    newMessage.value = '';
    isSending.value = true;
    await nextTick();
    scrollToBottom();

    try {
        const data = await askAITutor(activeSession.value.id, text);
        // Add AI response
        messages.value.push({
            id: data.id || Date.now() + 1,
            sender: 'AI',
            message: data.answer || data.message,
            sources: data.sources || [],
            created_at: new Date().toISOString(),
        });
    } catch (e) {
        messages.value.push({
            id: Date.now() + 1,
            sender: 'AI',
            message: '⚠️ 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.',
            sources: [],
            created_at: new Date().toISOString(),
        });
    }
    isSending.value = false;
    await nextTick();
    scrollToBottom();
};

const scrollToBottom = () => {
    if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
};

const formatTime = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
};

watch(selectedLectureId, () => {
    fetchSessions();
    activeSession.value = null;
    messages.value = [];
});

onMounted(() => {
    fetchLectures();
    fetchSessions();
});
</script>

<template>
    <div class="chat-view">
        <!-- Sidebar -->
        <aside class="chat-sidebar">
            <div class="sidebar-header">
                <button class="back-btn" @click="router.push('/dashboard')">
                    <ArrowLeft :size="18" /> 돌아가기
                </button>
                <h2><Sparkles :size="20" /> AI 튜터</h2>
            </div>

            <!-- Lecture selector -->
            <div class="lecture-select">
                <select v-model="selectedLectureId">
                    <option v-for="lec in myLectures" :key="lec.id" :value="lec.id">
                        {{ lec.title }}
                    </option>
                </select>
            </div>

            <button class="new-chat-btn" @click="openNewChat">
                <Plus :size="16" /> 새 대화
            </button>

            <!-- Session list -->
            <div class="session-list">
                <div v-for="s in sessions" :key="s.id"
                    class="session-item"
                    :class="{ active: activeSession?.id === s.id }"
                    @click="selectSession(s)">
                    <MessageSquare :size="16" />
                    <div class="session-info">
                        <span class="session-title">{{ s.title || '대화 #' + s.id }}</span>
                        <span class="session-date">{{ formatDate(s.created_at) }}</span>
                    </div>
                    <button class="delete-session" @click="removeSession(s.id, $event)">
                        <Trash2 :size="14" />
                    </button>
                </div>
                <div v-if="sessions.length === 0 && !isLoading" class="empty-sessions">
                    <p>대화 이력이 없습니다.<br>새 대화를 시작해보세요!</p>
                </div>
            </div>
        </aside>

        <!-- Chat area -->
        <main class="chat-main">
            <!-- No session selected -->
            <div v-if="!activeSession" class="chat-empty">
                <div class="empty-icon">🤖</div>
                <h2>AI 튜터와 대화하기</h2>
                <p>강의 내용에 대해 궁금한 점을 자유롭게 질문하세요.<br>
                    35,000+개의 학습 자료를 기반으로 답변합니다.</p>
                <button class="btn-start-chat" @click="openNewChat">
                    <Sparkles :size="18" /> 대화 시작하기
                </button>
            </div>

            <!-- Active chat -->
            <template v-else>
                <div class="chat-top-bar">
                    <h3>{{ activeSession.title || '대화' }}</h3>
                    <span class="chat-lecture-badge" v-if="activeLectureName">
                        <BookOpen :size="14" /> {{ activeLectureName }}
                    </span>
                </div>

                <div class="chat-messages" ref="chatContainer">
                    <!-- Welcome message -->
                    <div class="message system-msg">
                        <div class="msg-bubble system">
                            👋 안녕하세요! AI 튜터입니다. 강의 내용에 대해 궁금한 점을 물어보세요.
                        </div>
                    </div>

                    <div v-for="msg in messages" :key="msg.id"
                        class="message"
                        :class="{ 'user-msg': msg.sender === 'USER', 'ai-msg': msg.sender === 'AI' || msg.sender === 'SYSTEM' }">
                        <div class="msg-avatar" v-if="msg.sender !== 'USER'">🤖</div>
                        <div class="msg-content">
                            <div class="msg-bubble" :class="msg.sender.toLowerCase()">
                                <div v-html="renderMarkdown(msg.message)"></div>
                            </div>
                            <!-- Sources -->
                            <div v-if="msg.sources && msg.sources.length > 0" class="msg-sources">
                                <span class="sources-label"><Link2 :size="12" /> 참고 자료</span>
                                <a v-for="(src, idx) in msg.sources" :key="idx"
                                    :href="src.url" target="_blank" class="source-link">
                                    {{ src.title || src.url }}
                                </a>
                            </div>
                            <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
                        </div>
                    </div>

                    <!-- Typing indicator -->
                    <div v-if="isSending" class="message ai-msg">
                        <div class="msg-avatar">🤖</div>
                        <div class="msg-content">
                            <div class="msg-bubble ai typing">
                                <span class="dot"></span>
                                <span class="dot"></span>
                                <span class="dot"></span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Input -->
                <div class="chat-input-bar">
                    <input
                        v-model="newMessage"
                        type="text"
                        placeholder="궁금한 내용을 입력하세요..."
                        @keyup.enter="sendMessage"
                        :disabled="isSending"
                    />
                    <button class="search-toggle-btn" @click="toggleSearchPanel" :class="{ active: showSearchPanel }" title="원문 검색">
                        <Search :size="18" />
                    </button>
                    <button class="send-btn" @click="sendMessage" :disabled="!newMessage.trim() || isSending">
                        <Send :size="18" />
                    </button>
                </div>
            </template>
        </main>

        <!-- RAG 원문 검색 사이드패널 -->
        <aside v-if="showSearchPanel" class="search-panel">
            <div class="sp-header">
                <h3><Search :size="16" /> 학습 자료 원문 검색</h3>
                <button class="sp-close" @click="showSearchPanel = false"><X :size="18" /></button>
            </div>
            <div class="sp-input">
                <input v-model="searchQuery" placeholder="검색어 입력..." @keyup.enter="searchRAG" />
                <button class="sp-search-btn" @click="searchRAG" :disabled="isSearching">
                    {{ isSearching ? '...' : '검색' }}
                </button>
            </div>
            <div class="sp-results">
                <div v-if="isSearching" class="sp-loading">검색 중...</div>
                <div v-else-if="searchResults.length === 0 && searchQuery" class="sp-empty">결과 없음</div>
                <div v-for="(r, idx) in searchResults" :key="idx" class="sp-result-card">
                    <div class="sp-source">{{ r.source || 'LECTURE' }} · 유사도 {{ (1 - (r.distance || 0)).toFixed(2) }}</div>
                    <div class="sp-content">{{ r.content }}</div>
                    <div class="sp-meta" v-if="r.created_at">{{ new Date(r.created_at).toLocaleDateString() }}</div>
                </div>
            </div>
        </aside>

        <!-- New chat modal -->
        <div v-if="showNewChat" class="modal-overlay" @click.self="showNewChat = false">
            <div class="new-chat-modal">
                <h3><Sparkles :size="18" /> 새 대화 시작</h3>
                <input v-model="newChatTitle" placeholder="대화 주제 (예: React Hooks)" @keyup.enter="startNewChat" />
                <div class="modal-actions">
                    <button class="btn-cancel" @click="showNewChat = false">취소</button>
                    <button class="btn-confirm" @click="startNewChat">시작</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    methods: {
        renderMarkdown(text) {
            if (!text) return '';
            return text
                .replace(/## (.*)/g, '<h4>$1</h4>')
                .replace(/# (.*)/g, '<h3>$1</h3>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        }
    }
}
</script>

<style scoped lang="scss">
.chat-view {
    display: flex;
    height: 100vh;
    background: #0a0a0a;
    color: white;
}

// ═══ Sidebar ═══
.chat-sidebar {
    width: 300px;
    border-right: 1px solid #222;
    background: #111;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.sidebar-header {
    padding: 20px;
    border-bottom: 1px solid #222;
    h2 { font-size: 18px; display: flex; align-items: center; gap: 8px; margin: 12px 0 0; color: #fff; }
}

.back-btn {
    display: flex; align-items: center; gap: 6px;
    background: none; border: none; color: #888; cursor: pointer; font-size: 13px;
    padding: 0;
    &:hover { color: #4facfe; }
}

.lecture-select {
    padding: 12px 20px;
    select {
        width: 100%; padding: 10px; background: #1a1a1a; color: white;
        border: 1px solid #333; border-radius: 8px; font-size: 13px;
        &:focus { border-color: #4facfe; outline: none; }
    }
}

.new-chat-btn {
    margin: 0 20px 12px;
    padding: 10px;
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    border: none;
    border-radius: 8px;
    color: #000;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center; gap: 6px;
    transition: opacity 0.2s;
    &:hover { opacity: 0.9; }
}

.session-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px;
}

.session-item {
    display: flex; align-items: center; gap: 10px;
    padding: 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
    color: #aaa;
    &:hover { background: #1a1a1a; }
    &.active { background: #1e3a5f; color: white; }
}

.session-info {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column;
}
.session-title { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-date { font-size: 11px; color: #666; margin-top: 2px; }

.delete-session {
    background: none; border: none; color: #555; cursor: pointer; padding: 4px;
    opacity: 0; transition: opacity 0.2s;
    &:hover { color: #ff5555; }
}
.session-item:hover .delete-session { opacity: 1; }

.empty-sessions {
    text-align: center; padding: 40px 20px; color: #555;
    p { font-size: 13px; line-height: 1.6; }
}

// ═══ Chat Main ═══
.chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    .empty-icon { font-size: 64px; }
    h2 { font-size: 24px; color: #fff; }
    p { color: #888; text-align: center; line-height: 1.6; font-size: 14px; }
}

.btn-start-chat {
    padding: 12px 28px;
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    border: none; border-radius: 12px;
    color: #000; font-weight: 700; font-size: 15px;
    cursor: pointer; display: flex; align-items: center; gap: 8px;
    transition: transform 0.2s;
    &:hover { transform: scale(1.05); }
}

.chat-top-bar {
    padding: 16px 24px;
    border-bottom: 1px solid #222;
    display: flex; align-items: center; gap: 12px;
    h3 { font-size: 16px; margin: 0; }
}

.chat-lecture-badge {
    display: flex; align-items: center; gap: 4px;
    background: rgba(79, 172, 254, 0.1);
    color: #4facfe;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.message {
    display: flex;
    gap: 10px;
    max-width: 80%;
    &.user-msg {
        align-self: flex-end;
        flex-direction: row-reverse;
    }
    &.ai-msg, &.system-msg {
        align-self: flex-start;
    }
}

.msg-avatar {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: #1a1a1a;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.msg-content {
    display: flex; flex-direction: column; gap: 4px;
}

.msg-bubble {
    padding: 12px 16px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;

    &.user { background: #1e3a5f; color: white; border-bottom-right-radius: 4px; }
    &.ai { background: #1a1a1a; color: #ddd; border-bottom-left-radius: 4px; }
    &.system { background: #1a1a1a; color: #aaa; font-size: 13px; }

    code { background: #333; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #4facfe; }
    h3, h4 { margin: 8px 0 4px; color: #4facfe; }

    &.typing {
        display: flex; gap: 6px; padding: 14px 20px;
        .dot {
            width: 8px; height: 8px; background: #4facfe; border-radius: 50%;
            animation: typing 1.4s ease-in-out infinite;
            &:nth-child(2) { animation-delay: 0.2s; }
            &:nth-child(3) { animation-delay: 0.4s; }
        }
    }
}

@keyframes typing {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
}

.msg-sources {
    display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 4px;
}
.sources-label { font-size: 11px; color: #666; display: flex; align-items: center; gap: 4px; }
.source-link {
    font-size: 11px; color: #4facfe; background: rgba(79,172,254,0.1);
    padding: 2px 8px; border-radius: 10px; text-decoration: none;
    &:hover { background: rgba(79,172,254,0.2); }
}

.msg-time { font-size: 11px; color: #555; }

// ═══ Input Bar ═══
.chat-input-bar {
    padding: 16px 24px;
    border-top: 1px solid #222;
    display: flex; gap: 12px;
    background: #111;
    input {
        flex: 1; padding: 14px 18px;
        background: #1a1a1a; border: 1px solid #333; border-radius: 12px;
        color: white; font-size: 14px;
        &:focus { border-color: #4facfe; outline: none; }
        &::placeholder { color: #555; }
    }
}

.send-btn {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    border: none; border-radius: 12px;
    color: #000; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: opacity 0.2s;
    &:disabled { opacity: 0.3; cursor: not-allowed; }
    &:hover:not(:disabled) { opacity: 0.9; }
}

// ═══ Modal ═══
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.7); z-index: 3000;
    display: flex; align-items: center; justify-content: center;
}

.new-chat-modal {
    background: #1c1c1e; padding: 28px; border-radius: 16px;
    width: 400px; border: 1px solid #333;
    h3 { font-size: 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
    input {
        width: 100%; padding: 12px; background: #0a0a0a; border: 1px solid #333;
        border-radius: 8px; color: white; font-size: 14px; margin-bottom: 16px;
        &:focus { border-color: #4facfe; outline: none; }
    }
}

.modal-actions {
    display: flex; gap: 10px; justify-content: flex-end;
}
.btn-cancel {
    padding: 8px 20px; background: #333; border: none; border-radius: 8px;
    color: #aaa; cursor: pointer; &:hover { background: #444; }
}
.btn-confirm {
    padding: 8px 20px; background: #4facfe; border: none; border-radius: 8px;
    color: #000; font-weight: 600; cursor: pointer; &:hover { background: #3d9be9; }
}

// ═══ Search Toggle Button ═══
.search-toggle-btn {
    width: 48px; height: 48px;
    background: #1a1a1a; border: 1px solid #333; border-radius: 12px;
    color: #888; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
    &:hover { border-color: #4facfe; color: #4facfe; }
    &.active { background: rgba(79,172,254,0.15); border-color: #4facfe; color: #4facfe; }
}

// ═══ Search Panel ═══
.search-panel {
    width: 360px; border-left: 1px solid #222; background: #111;
    display: flex; flex-direction: column; overflow: hidden;
    animation: slideIn 0.2s ease;
}
@keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: none; opacity: 1; } }

.sp-header {
    padding: 16px 20px; border-bottom: 1px solid #222;
    display: flex; justify-content: space-between; align-items: center;
    h3 { font-size: 15px; margin: 0; display: flex; align-items: center; gap: 8px; color: #eee; }
}
.sp-close { background: none; border: none; color: #666; cursor: pointer; &:hover { color: #ff5555; } }

.sp-input {
    padding: 12px 16px; display: flex; gap: 8px;
    input {
        flex: 1; padding: 10px 14px; background: #1a1a1a; border: 1px solid #333;
        border-radius: 8px; color: #eee; font-size: 13px;
        &:focus { border-color: #4facfe; outline: none; }
    }
}
.sp-search-btn {
    padding: 8px 16px; background: #4facfe; color: #000; border: none;
    border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;
    &:disabled { opacity: 0.5; }
}

.sp-results { flex: 1; overflow-y: auto; padding: 0 16px 16px; }
.sp-loading, .sp-empty { text-align: center; padding: 40px 0; color: #666; font-size: 13px; }

.sp-result-card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px;
    padding: 14px; margin-top: 10px;
    &:hover { border-color: #333; }
}
.sp-source { font-size: 11px; color: #4facfe; font-weight: 600; margin-bottom: 6px; }
.sp-content {
    font-size: 13px; color: #ccc; line-height: 1.6; max-height: 120px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-word;
}
.sp-meta { font-size: 11px; color: #555; margin-top: 6px; }

@media (max-width: 768px) {
    .chat-sidebar { width: 260px; }
    .search-panel { width: 280px; }
}
</style>
