<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';
import { getPortfolios } from '../api/career';
import { BookOpen, User, Briefcase, Zap, Globe, AlertTriangle } from 'lucide-vue-next';

const router = useRouter();
const portfolios = ref([]);
const selectedPortfolio = ref(null);
const selectedPersona = ref('TECH_LEAD');
const loading = ref(false);

const personas = [
    { id: 'TECH_LEAD', name: '깐깐한 기술 팀장', desc: '기술적 깊이와 아키텍처를 집요하게 검증합니다.', icon: BookOpen, color: '#4facfe' },
    { id: 'FRIENDLY_SENIOR', name: '친절한 사수', desc: '잠재력과 학습 태도, 팀 적응력을 봅니다.', icon: User, color: '#43e97b' },
    { id: 'HR_MANAGER', name: '인사 담당자', desc: '컬처핏, 커뮤니케이션, 갈등 해결 능력을 봅니다.', icon: Briefcase, color: '#fa709a' },
    { id: 'STARTUP_CEO', name: '스타트업 대표', desc: '비즈니스 임팩트와 빠른 문제 해결력을 중시합니다.', icon: Zap, color: '#fddb92' },
    { id: 'BIG_TECH', name: '글로벌 빅테크', desc: 'CS 기초(자료구조/알고리즘)와 대규모 시스템 설계를 봅니다.', icon: Globe, color: '#a18cd1' },
    { id: 'PRESSURE', name: '압박 면접관', desc: '논리적 허점을 파고들며 위기 대처 능력을 테스트합니다.', icon: AlertTriangle, color: '#ff0844' },
];

onMounted(async () => {
    try {
        portfolios.value = await getPortfolios();
        if (portfolios.value.length > 0) {
            selectedPortfolio.value = portfolios.value[0].id;
        }
    } catch (e) {
        console.error("Failed to load portfolios", e);
    }
});

const startInterview = async () => {
    if (!selectedPortfolio.value) {
        alert("기반이 될 포트폴리오를 선택해주세요.");
        return;
    }
    
    loading.value = true;
    try {
        const res = await api.post('/career/interview/start/', {
            portfolio_id: selectedPortfolio.value,
            persona: selectedPersona.value
        });
        
        // Redirect to chat
        const interviewId = res.data.interview_id;
        router.push(`/interview/${interviewId}`);
        
    } catch (e) {
        console.error(e);
        alert("면접 세션 생성 실패: " + (e.response?.data?.error || e.message));
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <div class="setup-container">
        <header class="page-header">
            <h1>🎙️ AI 모의 면접 (Mock Interview)</h1>
            <p>작성된 포트폴리오와 스킬셋을 기반으로 실전 같은 기술 면접을 경험해보세요.</p>
        </header>
        
        <main class="glass-panel">
            <!-- Step 1: Portfolio -->
            <section class="step-section">
                <h2>1. 어떤 포트폴리오로 면접을 볼까요?</h2>
                <div class="portfolio-selector">
                    <select v-model="selectedPortfolio" class="glass-select">
                        <option v-for="p in portfolios" :key="p.id" :value="p.id">
                            {{ p.title }} ({{ p.portfolio_type_display }}) - {{ p.created_at }}
                        </option>
                    </select>
                    <p v-if="portfolios.length === 0" class="empty-msg">
                        생성된 포트폴리오가 없습니다. '커리어 포트폴리오' 메뉴에서 먼저 문서를 생성해주세요.
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
            
            <!-- Action -->
            <div class="action-footer">
                <button class="start-btn" @click="startInterview" :disabled="loading || portfolios.length === 0">
                    <span v-if="loading">면접장 준비 중... ⏳</span>
                    <span v-else>면접 시작하기 🚀</span>
                </button>
            </div>
        </main>
    </div>
</template>

<style scoped>
.setup-container {
    max-width: 1000px; margin: 0 auto; padding: 40px 20px; color: white;
}
.page-header { text-align: center; margin-bottom: 40px; }
.page-header h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 10px; background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.page-header p { color: #aaa; font-size: 1.1rem; }

.glass-panel {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(16px);
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 40px;
}

.step-section { margin-bottom: 40px; }
.step-section h2 { font-size: 1.2rem; margin-bottom: 20px; border-left: 4px solid #4facfe; padding-left: 15px; }

.glass-select {
    width: 100%; padding: 15px; font-size: 1rem; border-radius: 12px;
    background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.2);
    color: white; outline: none; cursor: pointer;
}
.empty-msg { color: #ff6b6b; margin-top: 10px; font-size: 0.9rem; }

/* Persona Grid */
.persona-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;
}
.persona-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px; padding: 25px;
    cursor: pointer; transition: all 0.3s ease;
    position: relative; overflow: hidden;
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
    width: 50px; height: 50px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 15px;
}
.persona-card h3 { margin: 0 0 10px 0; font-size: 1.1rem; }
.persona-card p { margin: 0; font-size: 0.9rem; color: #ccc; line-height: 1.4; }

.action-footer { text-align: center; margin-top: 20px; }
.start-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border: none; padding: 16px 48px; font-size: 1.2rem; font-weight: bold;
    border-radius: 50px; cursor: pointer; transition: transform 0.2s;
    box-shadow: 0 10px 20px rgba(0,0,0,0.3);
}
.start-btn:hover:not(:disabled) { transform: scale(1.05); }
.start-btn:disabled { opacity: 0.6; cursor: not-allowed; filter: grayscale(100%); }
</style>
