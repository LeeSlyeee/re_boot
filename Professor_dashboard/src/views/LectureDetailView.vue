<script setup>
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api/axios';
import { Bar, Doughnut } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement);

const route = useRoute();
const router = useRouter();
const students = ref([]);
const lectureId = route.params.id;
const lectureTitle = ref('');
const lectureCode = ref('');

// Tab Management
const activeTab = ref('monitor'); // 'monitor' | 'attendance' | 'quiz' | 'recording' | 'live'

const copyCode = async () => {
    try {
        await navigator.clipboard.writeText(lectureCode.value);
        alert(`입장 코드(${lectureCode.value})가 복사되었습니다.`);
    } catch (err) {
        console.error('Failed to copy: ', err);
    }
};

const chartData = ref({
  labels: [],
  datasets: [{ label: 'Average Score', backgroundColor: '#f87979', data: [] }]
});

const chartOptions = {
    responsive: true,
    maintainAspectRatio: false
};

const fetchDashboard = async () => {
    try {
        const lecRes = await api.get(`/learning/lectures/${lectureId}/`);
        lectureTitle.value = lecRes.data.title;
        lectureCode.value = lecRes.data.access_code;

        const res = await api.get(`/learning/lectures/${lectureId}/monitor/`);
        students.value = res.data;
        
        chartData.value = {
            labels: students.value.map(s => s.name),
            datasets: [
                {
                    label: '진도율 (%)',
                    backgroundColor: '#4facfe',
                    data: students.value.map(s => s.progress)
                }
            ]
        };
        
        await fetchChecklist(); 
    } catch (e) {
        console.error(e);
        if (e.response && e.response.status === 401) router.push('/login');
    }
};

// ── Checklist Management ──
const syllabi = ref([]);
const isAddingWeek = ref(false);
const newWeekTitle = ref('');
const newWeekDesc = ref('');
const editingObjective = ref(null);

const fetchChecklist = async () => {
    try {
        const res = await api.get(`/learning/checklist/?lecture_id=${lectureId}`);
        syllabi.value = res.data;
    } catch (e) {
        console.error("Failed to fetch checklist", e);
    }
};

const addWeek = async () => {
    if (!newWeekTitle.value) return;
    try {
        await api.post(`/learning/lectures/${lectureId}/syllabus/`, {
            week_number: syllabi.value.length + 1,
            title: newWeekTitle.value,
            description: newWeekDesc.value
        });
        newWeekTitle.value = '';
        newWeekDesc.value = '';
        isAddingWeek.value = false;
        await fetchChecklist();
    } catch (e) {
        alert("주차 추가 실패");
    }
};

const addObjective = async (weekId) => {
    const text = prompt("학습 목표를 입력하세요:");
    if (!text) return;
    try {
        await api.post(`/learning/syllabus/${weekId}/objective/`, { content: text });
        await fetchChecklist();
    } catch (e) {
        alert("목표 추가 실패");
    }
};

const deleteObjective = async (objId) => {
    if(!confirm("삭제하시겠습니까?")) return;
    try {
        await api.delete(`/learning/objective/${objId}/`);
        await fetchChecklist();
    } catch (e) {
        alert("삭제 실패");
    }
};

// ── Attendance Data ──
const attendanceData = ref(null);
const attendanceLoading = ref(false);
const attendanceChartData = ref({ labels: [], datasets: [] });

const fetchAttendance = async () => {
    if (attendanceData.value) return; // 이미 로드됨
    attendanceLoading.value = true;
    try {
        const res = await api.get(`/learning/lectures/${lectureId}/attendance/`);
        attendanceData.value = res.data;
        
        // 학생별 출석률 차트 데이터
        attendanceChartData.value = {
            labels: res.data.students.map(s => s.name),
            datasets: [{
                label: '출석률 (%)',
                backgroundColor: res.data.students.map(s => {
                    if (s.rate >= 80) return '#4caf50';
                    if (s.rate >= 50) return '#ff9800';
                    return '#f44336';
                }),
                data: res.data.students.map(s => s.rate),
                borderRadius: 6,
                borderSkipped: false
            }]
        };
    } catch (e) {
        console.error("출석률 조회 실패", e);
    } finally {
        attendanceLoading.value = false;
    }
};

// ── Quiz Analytics Data ──
const quizData = ref(null);
const quizLoading = ref(false);
const quizDistributionChart = ref({ labels: [], datasets: [] });
const quizStudentChart = ref({ labels: [], datasets: [] });

const fetchQuizAnalytics = async () => {
    if (quizData.value) return;
    quizLoading.value = true;
    try {
        const res = await api.get(`/learning/lectures/${lectureId}/quiz_analytics/`);
        quizData.value = res.data;
        
        // 점수 분포 도넛 차트
        const dist = res.data.score_distribution;
        quizDistributionChart.value = {
            labels: Object.keys(dist),
            datasets: [{
                data: Object.values(dist),
                backgroundColor: ['#f44336', '#ff9800', '#ffeb3b', '#4caf50', '#2196f3'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        };
        
        // 학생별 평균 점수 차트
        quizStudentChart.value = {
            labels: res.data.students.map(s => s.name),
            datasets: [{
                label: '평균 점수',
                backgroundColor: res.data.students.map(s => {
                    if (s.avg_score >= 80) return '#4caf50';
                    if (s.avg_score >= 60) return '#ff9800';
                    return '#f44336';
                }),
                data: res.data.students.map(s => s.avg_score),
                borderRadius: 6,
                borderSkipped: false
            }]
        };
    } catch (e) {
        console.error("퀴즈 분석 조회 실패", e);
    } finally {
        quizLoading.value = false;
    }
};

// Tab change handler
const switchTab = (tab) => {
    activeTab.value = tab;
    if (tab === 'attendance') fetchAttendance();
    if (tab === 'quiz') fetchQuizAnalytics();
    if (tab === 'recording') fetchRecordings();
    if (tab === 'live') fetchLiveStatus();
};

// ── Live Session State ──
const liveSession = ref(null);
const liveLoading = ref(false);
const liveSessionTitle = ref('');
const liveParticipants = ref([]);
const livePollingTimer = ref(null);
const materials = ref([]);
const materialUploading = ref(false);
const pulseStats = ref({ understand: 0, confused: 0, total: 0, understand_rate: 0 });

const fetchLiveStatus = async () => {
    try {
        const { data } = await api.get('/learning/live/active/');
        const current = data.find(s => s.lecture_id == lectureId);
        if (current) {
            liveSession.value = current;
            const detail = await api.get(`/learning/live/${current.id}/status/`);
            liveParticipants.value = detail.data.participants || [];
            liveSession.value = { ...liveSession.value, ...detail.data };
            startLivePolling();
        } else {
            liveSession.value = null;
        }
    } catch (e) { console.error('Live status fetch error:', e); }
    await fetchMaterials();
};

const createLiveSession = async () => {
    liveLoading.value = true;
    try {
        const { data } = await api.post('/learning/live/create/', {
            lecture_id: lectureId, title: liveSessionTitle.value || '',
        });
        liveSession.value = data;
        liveSessionTitle.value = '';
        startLivePolling();
    } catch (e) {
        if (e.response?.status === 409) {
            liveSession.value = e.response.data;
            startLivePolling();
        } else { alert('세션 생성 실패: ' + (e.response?.data?.error || '')); }
    } finally { liveLoading.value = false; }
};

const startLiveSession = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/start/`);
        liveSession.value = { ...liveSession.value, ...data };
    } catch (e) { alert('세션 시작 실패: ' + (e.response?.data?.error || '')); }
};

const endLiveSession = async () => {
    if (!liveSession.value || !confirm('세션을 종료하시겠습니까?')) return;
    try {
        await api.post(`/learning/live/${liveSession.value.id}/end/`);
        stopLivePolling();
        liveSession.value = null;
        liveParticipants.value = [];
    } catch (e) { alert('세션 종료 실패'); }
};

const startLivePolling = () => {
    stopLivePolling();
    livePollingTimer.value = setInterval(async () => {
        if (!liveSession.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSession.value.id}/status/`);
            liveSession.value = { ...liveSession.value, ...data };
            liveParticipants.value = data.participants || [];
            // 펄스 통계 동시 조회
            try {
                const pulse = await api.get(`/learning/live/${liveSession.value.id}/pulse-stats/`);
                pulseStats.value = pulse.data;
            } catch {}
            // 퀴즈 결과 동시 조회
            await fetchQuizResult();
            // Q&A 질문 동시 조회
            await fetchLiveQuestions();
        } catch (e) { /* ignore */ }
    }, 5000);
};

const stopLivePolling = () => {
    if (livePollingTimer.value) { clearInterval(livePollingTimer.value); livePollingTimer.value = null; }
};

// ── Quiz Control State ──
const activeQuizResult = ref(null);
const quizGenerating = ref(false);
const showManualQuizForm = ref(false);
const manualQuiz = ref({ question: '', options: ['', '', '', ''], correctIndex: '', explanation: '' });
const lastActiveQuizId = ref(null);

const generateAIQuiz = async () => {
    if (!liveSession.value) return;
    quizGenerating.value = true;
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/quiz/generate/`);
        lastActiveQuizId.value = data.id;
        alert(`AI 퀴즈 발동! (문제: ${data.question_text.substring(0, 40)}...)`);
    } catch (e) {
        alert('AI 퀴즈 생성 실패: ' + (e.response?.data?.error || ''));
    } finally { quizGenerating.value = false; }
};

const submitManualQuiz = async () => {
    if (!liveSession.value) return;
    const q = manualQuiz.value;
    if (!q.question || q.options.some(o => !o) || q.correctIndex === '') {
        alert('모제와 보기 4개, 정답을 모두 입력해주세요.'); return;
    }
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/quiz/create/`, {
            question_text: q.question,
            options: q.options,
            correct_answer: q.options[q.correctIndex],
            explanation: q.explanation,
        });
        lastActiveQuizId.value = data.id;
        showManualQuizForm.value = false;
        manualQuiz.value = { question: '', options: ['', '', '', ''], correctIndex: '', explanation: '' };
    } catch (e) { alert('퀴즈 생성 실패: ' + (e.response?.data?.error || '')); }
};

const fetchQuizResult = async () => {
    if (!liveSession.value || !lastActiveQuizId.value) return;
    try {
        const { data } = await api.get(`/learning/live/${liveSession.value.id}/quiz/${lastActiveQuizId.value}/results/`);
        activeQuizResult.value = data;
    } catch { /* ignore */ }
};

// ── Q&A State ──
const liveQuestions = ref([]);
const qaReplyText = ref({});

const fetchLiveQuestions = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.get(`/learning/live/${liveSession.value.id}/questions/`);
        liveQuestions.value = data;
    } catch { /* ignore */ }
};

const replyToQuestion = async (questionId) => {
    const text = qaReplyText.value[questionId];
    if (!text || !text.trim()) return;
    try {
        await api.post(`/learning/live/${liveSession.value.id}/questions/${questionId}/answer/`, {
            answer: text
        });
        qaReplyText.value[questionId] = '';
        await fetchLiveQuestions();
    } catch (e) { alert('답변 실패: ' + (e.response?.data?.error || '')); }
};
const copyLiveCode = async () => {
    if (!liveSession.value?.session_code) return;
    try { await navigator.clipboard.writeText(liveSession.value.session_code); alert('코드 복사 완료!'); } catch {}
};

const fetchMaterials = async () => {
    try { const { data } = await api.get(`/learning/materials/list/?lecture_id=${lectureId}`); materials.value = data; } catch {}
};

const uploadMaterial = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    materialUploading.value = true;
    try {
        const fd = new FormData(); fd.append('file', file); fd.append('lecture_id', lectureId); fd.append('title', file.name);
        await api.post('/learning/materials/upload/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        await fetchMaterials();
    } catch { alert('교안 업로드 실패'); }
    finally { materialUploading.value = false; e.target.value = ''; }
};

const deleteMaterial = async (id) => {
    if (!confirm('교안을 삭제하시겠습니까?')) return;
    try { await api.delete(`/learning/materials/${id}/delete/`); await fetchMaterials(); } catch { alert('삭제 실패'); }
};

// ── Recording Upload Data ──
const recordings = ref([]);
const recordingsLoading = ref(false);
const isUploading = ref(false);
const uploadProgress = ref(0);
const uploadError = ref('');
const uploadResult = ref(null);
const isDragOver = ref(false);
const showSummaryModal = ref(false);
const selectedSummary = ref('');

const fetchRecordings = async () => {
    recordingsLoading.value = true;
    try {
        const res = await api.get(`/learning/lectures/${lectureId}/recordings/`);
        recordings.value = res.data;
    } catch (e) {
        console.error('녹음 이력 조회 실패', e);
    } finally {
        recordingsLoading.value = false;
    }
};

const handleDrop = (e) => {
    isDragOver.value = false;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) uploadFile(files[0]);
};

const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) uploadFile(files[0]);
};

const uploadFile = async (file) => {
    // 파일 검증
    const validTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a', 'audio/m4a', 'audio/webm'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|webm|ogg)$/i)) {
        uploadError.value = '지원하지 않는 파일 형식입니다. (mp3, wav, m4a 지원)';
        return;
    }
    
    const maxSize = 150 * 1024 * 1024; // 150MB
    if (file.size > maxSize) {
        uploadError.value = `파일 크기가 150MB를 초과합니다. (현재: ${Math.round(file.size / 1024 / 1024)}MB)`;
        return;
    }
    
    isUploading.value = true;
    uploadError.value = '';
    uploadResult.value = null;
    uploadProgress.value = 10;
    
    const formData = new FormData();
    formData.append('audio_file', file);
    
    try {
        uploadProgress.value = 30;
        const res = await api.post(
            `/learning/lectures/${lectureId}/upload_recording/`,
            formData,
            {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 600000, // 10분 타임아웃 (1시간 강의 처리)
            }
        );
        uploadProgress.value = 100;
        uploadResult.value = res.data;
        
        // 이력 갱신
        await fetchRecordings();
    } catch (e) {
        console.error('녹음 업로드 실패', e);
        uploadError.value = e.response?.data?.error || '업로드 중 오류가 발생했습니다.';
    } finally {
        isUploading.value = false;
    }
};

const viewSummary = async (sessionId) => {
    try {
        const res = await api.get(`/learning/sessions/${sessionId}/`);
        const summaries = res.data.summaries || [];
        if (summaries.length > 0) {
            selectedSummary.value = summaries[0].content_text;
        } else {
            selectedSummary.value = '(요약본이 아직 생성되지 않았습니다)';
        }
        showSummaryModal.value = true;
    } catch (e) {
        alert('요약본을 불러올 수 없습니다.');
    }
};

const attendanceChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } }
    },
    plugins: {
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y}%` } }
    }
};

const quizBarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '점' } }
    }
};

const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { position: 'bottom' }
    }
};

onMounted(fetchDashboard);
</script>

<template>
    <div class="detail-view">
        <button class="back-btn" @click="router.push('/')">← 대시보드로 돌아가기</button>
        <div class="header-row">
            <h1>{{ lectureTitle }}</h1>
            <div class="code-badge" @click="copyCode" v-if="lectureCode">
                <span class="label">ENTRY CODE</span>
                <span class="value">{{ lectureCode }}</span>
                <span class="icon">❐</span>
            </div>
        </div>

        <!-- ── Tab Navigation ── -->
        <div class="tab-nav">
            <button 
                :class="['tab-btn', { active: activeTab === 'monitor' }]" 
                @click="switchTab('monitor')">
                📊 진도 모니터링
            </button>
            <button 
                :class="['tab-btn', { active: activeTab === 'attendance' }]" 
                @click="switchTab('attendance')">
                📋 출석률 현황
            </button>
            <button 
                :class="['tab-btn', { active: activeTab === 'quiz' }]" 
                @click="switchTab('quiz')">
                📝 퀴즈 분석
            </button>
            <button 
                :class="['tab-btn', { active: activeTab === 'recording' }]" 
                @click="switchTab('recording')">
                🎤 녹음 업로드
            </button>
            <button 
                :class="['tab-btn live-tab', { active: activeTab === 'live' }]" 
                @click="switchTab('live')">
                🟢 라이브 세션
            </button>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab 1: 진도 모니터링 (기존) -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'monitor'">
            <div class="chart-container" v-if="students.length > 0">
                <Bar :data="chartData" :options="chartOptions" />
            </div>

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 15%">이름</th>
                            <th style="width: 15%">상태</th>
                            <th style="width: 25%">진도율 (Progress)</th>
                            <th style="width: 45%">최근 획득 스킬 (Recent Skills)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="student in students" :key="student.id">
                            <td>
                                <div class="student-name">{{ student.name }}</div>
                                <div class="student-email">{{ student.email }}</div>
                            </td>
                            <td>
                                <span class="status-badge" :class="student.status">
                                    {{ student.status.toUpperCase() }}
                                </span>
                            </td>
                            <td>
                                <div class="progress-wrapper">
                                    <div class="progress-bar">
                                        <div class="fill" :style="{ width: student.progress + '%' }" :class="student.status"></div>
                                    </div>
                                    <span class="percent">{{ student.progress }}%</span>
                                </div>
                            </td>
                            <td>
                                <div class="skill-tags">
                                    <span v-for="skill in student.recent_skills" :key="skill" class="skill-tag">
                                        {{ skill }}
                                    </span>
                                    <span v-if="student.recent_skills.length === 0" class="no-skill">-</span>
                                </div>
                            </td>
                        </tr>
                        <tr v-if="students.length === 0">
                            <td colspan="4" style="text-align: center; color: #888; padding: 40px;">
                                수강생 데이터가 없습니다.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Syllabus Manager -->
            <div class="syllabus-manager">
                <h2 class="section-title">📅 강의 계획서 관리</h2>
                
                <div class="syllabus-list">
                    <div v-for="week in syllabi" :key="week.id" class="week-card">
                        <div class="week-header">
                            <h3>{{week.week_number}}주차: {{week.title}}</h3>
                            <button class="btn-micro" @click="addObjective(week.id)">+ 목표 추가</button>
                        </div>
                        <div class="objective-list">
                            <div v-for="obj in week.objectives" :key="obj.id" class="obj-item">
                                <span>- {{obj.content}}</span>
                                <span class="delete-x" @click="deleteObjective(obj.id)">×</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="add-week-form">
                    <h3>+ 주차 추가</h3>
                    <input v-model="newWeekTitle" placeholder="주차 주제 (예: React 기초)" />
                    <input v-model="newWeekDesc" placeholder="설명 (선택)" />
                    <button @click="addWeek">추가</button>
                </div>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab 2: 출석률 현황 -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'attendance'">
            <div v-if="attendanceLoading" class="loading-state">
                <div class="spinner"></div>
                <p>출석 데이터를 불러오는 중...</p>
            </div>

            <div v-else-if="attendanceData">
                <!-- Summary Cards -->
                <div class="summary-cards">
                    <div class="summary-card">
                        <div class="card-icon">👥</div>
                        <div class="card-value">{{ attendanceData.summary.total_students }}명</div>
                        <div class="card-label">총 수강생</div>
                    </div>
                    <div class="summary-card">
                        <div class="card-icon">📅</div>
                        <div class="card-value">{{ attendanceData.summary.total_dates }}일</div>
                        <div class="card-label">총 수업일</div>
                    </div>
                    <div class="summary-card highlight">
                        <div class="card-icon">📈</div>
                        <div class="card-value">{{ attendanceData.summary.overall_rate }}%</div>
                        <div class="card-label">전체 출석률</div>
                    </div>
                </div>

                <!-- Attendance Chart -->
                <div class="chart-container" v-if="attendanceData.students.length > 0">
                    <h3 class="chart-title">학생별 출석률</h3>
                    <Bar :data="attendanceChartData" :options="attendanceChartOptions" />
                </div>

                <!-- Attendance Table -->
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 20%">이름</th>
                                <th style="width: 15%">출석률</th>
                                <th style="width: 15%">출석 / 전체</th>
                                <th style="width: 50%">날짜별 출석</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="student in attendanceData.students" :key="student.id">
                                <td>
                                    <div class="student-name">{{ student.name }}</div>
                                    <div class="student-email">{{ student.email }}</div>
                                </td>
                                <td>
                                    <span class="rate-badge" :class="{
                                        high: student.rate >= 80,
                                        mid: student.rate >= 50 && student.rate < 80,
                                        low: student.rate < 50
                                    }">{{ student.rate }}%</span>
                                </td>
                                <td class="count-cell">
                                    {{ student.attended_count }} / {{ student.total_dates }}
                                </td>
                                <td>
                                    <div class="attendance-dots">
                                        <span 
                                            v-for="(date, idx) in attendanceData.dates" 
                                            :key="idx"
                                            class="dot"
                                            :class="{ present: student.daily[date], absent: !student.daily[date] }"
                                            :title="date + (student.daily[date] ? ' ✓ 출석' : ' ✗ 결석')"
                                        ></span>
                                    </div>
                                </td>
                            </tr>
                            <tr v-if="attendanceData.students.length === 0">
                                <td colspan="4" style="text-align:center; color:#888; padding:40px;">
                                    출석 데이터가 없습니다.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div v-else class="empty-state">
                <p>출석 데이터를 불러올 수 없습니다.</p>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab 3: 퀴즈 분석 -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'quiz'">
            <div v-if="quizLoading" class="loading-state">
                <div class="spinner"></div>
                <p>퀴즈 데이터를 분석하는 중...</p>
            </div>

            <div v-else-if="quizData">
                <!-- Summary Cards -->
                <div class="summary-cards">
                    <div class="summary-card">
                        <div class="card-icon">📝</div>
                        <div class="card-value">{{ quizData.summary.total_quizzes }}회</div>
                        <div class="card-label">총 응시 횟수</div>
                    </div>
                    <div class="summary-card">
                        <div class="card-icon">📊</div>
                        <div class="card-value">{{ quizData.summary.average_score }}점</div>
                        <div class="card-label">전체 평균</div>
                    </div>
                    <div class="summary-card highlight">
                        <div class="card-icon">✅</div>
                        <div class="card-value">{{ quizData.summary.pass_rate }}%</div>
                        <div class="card-label">합격률 (60점↑)</div>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="charts-row">
                    <!-- 학생별 평균 점수 -->
                    <div class="chart-container flex-2">
                        <h3 class="chart-title">학생별 평균 점수</h3>
                        <Bar :data="quizStudentChart" :options="quizBarOptions" />
                    </div>
                    <!-- 점수 분포 -->
                    <div class="chart-container flex-1">
                        <h3 class="chart-title">점수 분포</h3>
                        <Doughnut :data="quizDistributionChart" :options="doughnutOptions" />
                    </div>
                </div>

                <!-- 학생별 성적 테이블 -->
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 20%">이름</th>
                                <th style="width: 15%">응시 횟수</th>
                                <th style="width: 15%">평균 점수</th>
                                <th style="width: 50%">점수 추이</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="student in quizData.students" :key="student.id">
                                <td>
                                    <div class="student-name">{{ student.name }}</div>
                                </td>
                                <td>{{ student.quiz_count }}회</td>
                                <td>
                                    <span class="rate-badge" :class="{
                                        high: student.avg_score >= 80,
                                        mid: student.avg_score >= 60 && student.avg_score < 80,
                                        low: student.avg_score < 60
                                    }">{{ student.avg_score }}점</span>
                                </td>
                                <td>
                                    <div class="score-trend">
                                        <span 
                                            v-for="(score, idx) in student.scores" 
                                            :key="idx" 
                                            class="score-pill"
                                            :class="{
                                                high: score >= 80,
                                                mid: score >= 60 && score < 80,
                                                low: score < 60
                                            }"
                                        >{{ score }}</span>
                                        <span v-if="student.scores.length === 0" class="no-skill">-</span>
                                    </div>
                                </td>
                            </tr>
                            <tr v-if="quizData.students.length === 0">
                                <td colspan="4" style="text-align:center; color:#888; padding:40px;">
                                    퀴즈 데이터가 없습니다.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- 문항별 정답률 -->
                <div class="table-container" v-if="quizData.question_accuracy.length > 0" style="margin-top: 24px;">
                    <h3 class="section-title" style="padding: 20px 20px 0;">🎯 문항별 정답률 (상위 10문항)</h3>
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 60%">문항</th>
                                <th style="width: 20%">정답률</th>
                                <th style="width: 20%">응답 수</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(q, idx) in quizData.question_accuracy" :key="idx">
                                <td class="question-cell">{{ q.question_text }}</td>
                                <td>
                                    <div class="progress-wrapper">
                                        <div class="progress-bar">
                                            <div class="fill" 
                                                :style="{ width: q.accuracy + '%' }" 
                                                :class="{
                                                    good: q.accuracy >= 70,
                                                    warning: q.accuracy >= 40 && q.accuracy < 70,
                                                    critical: q.accuracy < 40
                                                }"></div>
                                        </div>
                                        <span class="percent">{{ q.accuracy }}%</span>
                                    </div>
                                </td>
                                <td class="count-cell">{{ q.total_answers }}명</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div v-else class="empty-state">
                <p>퀴즈 데이터를 불러올 수 없습니다.</p>
            </div>
        </div>

        <!-- ══════════════════════════════════════════ -->
        <!-- Tab 4: 녹음 업로드 -->
        <!-- ══════════════════════════════════════════ -->
        <div v-if="activeTab === 'recording'">
            <!-- 업로드 영역 -->
            <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'uploading': isUploading }"
                @dragover.prevent="isDragOver = true"
                @dragleave="isDragOver = false"
                @drop.prevent="handleDrop"
                @click="!isUploading && $refs.fileInput.click()"
            >
                <input 
                    ref="fileInput" 
                    type="file" 
                    accept=".mp3,.wav,.m4a,.webm,.ogg" 
                    style="display:none" 
                    @change="handleFileSelect" 
                />
                
                <div v-if="isUploading" class="upload-progress">
                    <div class="spinner"></div>
                    <p class="upload-status">🔄 강의 녹음 처리 중... (오디오 분할 → STT 변환 → AI 요약)</p>
                    <p class="upload-hint">⏳ 1시간 강의 기준 약 3~5분 소요</p>
                    <div class="progress-bar-upload">
                        <div class="fill-upload" :style="{ width: uploadProgress + '%' }"></div>
                    </div>
                </div>
                
                <div v-else>
                    <div class="upload-icon">🎤</div>
                    <p class="upload-text">강의 녹음 파일을 드래그하거나 클릭하여 업로드</p>
                    <p class="upload-hint">mp3, wav, m4a 지원 · 최대 150MB (1시간 강의 기준)</p>
                </div>
            </div>
            
            <!-- 업로드 결과 -->
            <div v-if="uploadError" class="upload-error">
                ❌ {{ uploadError }}
            </div>
            
            <div v-if="uploadResult" class="upload-success">
                <div class="success-header">
                    ✅ 처리 완료!
                </div>
                <div class="success-detail">
                    <span>🕛 강의 시간: {{ uploadResult.duration_minutes }}분</span>
                    <span>📝 STT 문자 수: {{ uploadResult.stt_length?.toLocaleString() }}자</span>
                    <span>🧩 처리 청크: {{ uploadResult.total_chunks }}개</span>
                </div>
            </div>
            
            <!-- 녹음 이력 -->
            <div class="table-container" style="margin-top: 24px;">
                <h3 class="section-title" style="padding: 20px 20px 0;">📎 처리된 녹음 이력</h3>
                <div v-if="recordingsLoading" class="loading-state">
                    <div class="spinner"></div>
                    <p>로딩 중...</p>
                </div>
                <table v-else>
                    <thead>
                        <tr>
                            <th style="width: 30%">파일명</th>
                            <th style="width: 10%">크기</th>
                            <th style="width: 10%">길이</th>
                            <th style="width: 15%">상태</th>
                            <th style="width: 15%">업로드 일시</th>
                            <th style="width: 20%">액션</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="rec in recordings" :key="rec.id">
                            <td class="filename-cell">{{ rec.filename }}</td>
                            <td>{{ rec.file_size_mb }}MB</td>
                            <td>{{ rec.duration_minutes ? rec.duration_minutes + '분' : '-' }}</td>
                            <td>
                                <span class="status-badge" :class="{
                                    good: rec.status === 'COMPLETED',
                                    warning: rec.status === 'PROCESSING' || rec.status === 'TRANSCRIBING' || rec.status === 'SUMMARIZING' || rec.status === 'SPLITTING',
                                    critical: rec.status === 'FAILED'
                                }">
                                    {{ rec.status === 'COMPLETED' ? '✅ 완료' : 
                                       rec.status === 'FAILED' ? '❌ 실패' : 
                                       '⏳ ' + rec.status }}
                                </span>
                            </td>
                            <td class="count-cell">{{ rec.created_at }}</td>
                            <td>
                                <button 
                                    v-if="rec.status === 'COMPLETED' && rec.session_id"
                                    class="btn-micro" 
                                    @click="viewSummary(rec.session_id)"
                                >📝 요약 보기</button>
                                <span v-else-if="rec.status === 'FAILED'" class="error-hint" :title="rec.error_message">{{ rec.error_message?.substring(0, 30) }}...</span>
                            </td>
                        </tr>
                        <tr v-if="recordings.length === 0">
                            <td colspan="6" style="text-align:center; color:#888; padding:40px;">
                                업로드된 녹음이 없습니다.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- 요약 보기 모달 -->
        <div v-if="showSummaryModal" class="modal-overlay" @click.self="showSummaryModal = false">
            <div class="modal-card summary-modal">
                <div class="modal-header">
                    <h2>📚 강의 요약</h2>
                    <button class="close-btn" @click="showSummaryModal = false">×</button>
                </div>
                <div class="modal-body">
                    <pre class="summary-content">{{ selectedSummary }}</pre>
                </div>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab 5: 라이브 세션 -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'live'" class="live-tab-content">
            
            <!-- 세션 없음: 생성 폼 -->
            <div v-if="!liveSession" class="live-create-section">
                <div class="create-card">
                    <h2>🟢 라이브 세션 시작</h2>
                    <p class="sub">학생들이 6자리 코드로 입장할 수 있는 실시간 수업 세션을 만듭니다.</p>
                    <input type="text" v-model="liveSessionTitle" placeholder="세션 제목 (선택)" class="session-title-input" />
                    <button class="btn-live-create" @click="createLiveSession" :disabled="liveLoading">
                        {{ liveLoading ? '생성 중...' : '세션 생성' }}
                    </button>
                </div>
            </div>

            <!-- 세션 활성: 코드 표시 + 컨트롤 -->
            <div v-else class="live-active-section">
                <!-- 상태 뱃지 -->
                <div class="live-status-bar">
                    <span class="status-badge" :class="liveSession.status">
                        {{ liveSession.status === 'WAITING' ? '⏳ 대기 중' : liveSession.status === 'LIVE' ? '🔴 진행 중' : '종료됨' }}
                    </span>
                    <span class="participant-count">
                        👥 {{ liveSession.active_participants || 0 }}명 참가 중
                    </span>
                </div>

                <!-- 대형 코드 디스플레이 -->
                <div class="code-display" @click="copyLiveCode">
                    <span class="code-label">입장 코드</span>
                    <span class="code-value">{{ liveSession.session_code }}</span>
                    <span class="code-hint">클릭하여 복사</span>
                </div>

                <!-- 컨트롤 버튼 -->
                <div class="live-controls">
                    <button v-if="liveSession.status === 'WAITING'" class="btn-live-start" @click="startLiveSession">
                        ▶️ 수업 시작
                    </button>
                    <button v-if="liveSession.status === 'LIVE'" class="btn-live-end" @click="endLiveSession">
                        ⏹️ 세션 종료
                    </button>
                </div>

                <!-- 이해도 펄스 게이지 (LIVE일 때만) -->
                <div v-if="liveSession.status === 'LIVE' && pulseStats.total > 0" class="pulse-gauge-section">
                    <h3>📊 실시간 이해도</h3>
                    <div class="pulse-gauge">
                        <div class="gauge-bar">
                            <div class="gauge-fill understand" :style="{ width: pulseStats.understand_rate + '%' }"></div>
                            <div class="gauge-fill confused" :style="{ width: (100 - pulseStats.understand_rate) + '%' }"></div>
                        </div>
                        <div class="gauge-labels">
                            <span class="label-understand">✅ 이해 {{ pulseStats.understand }}명 ({{ pulseStats.understand_rate }}%)</span>
                            <span class="label-confused">❓ 혼란 {{ pulseStats.confused }}명 ({{ (100 - pulseStats.understand_rate).toFixed(1) }}%)</span>
                        </div>
                    </div>
                </div>
                <div v-else-if="liveSession.status === 'LIVE'" class="pulse-gauge-section empty">
                    <p class="pulse-waiting">📊 아직 학생들의 이해도 응답이 없습니다...</p>
                </div>

                <!-- 체크포인트 퀴즈 컨트롤 (LIVE일 때만) -->
                <div v-if="liveSession.status === 'LIVE'" class="quiz-control-section">
                    <h3>📝 체크포인트 퀴즈</h3>
                    
                    <!-- 퀴즈 결과 표시 (활성 퀴즈 있을 때) -->
                    <div v-if="activeQuizResult" class="quiz-result-card">
                        <div class="quiz-result-header">
                            <span class="quiz-tag">{{ activeQuizResult.is_ai_generated ? '🤖 AI' : '✏️ 수동' }}</span>
                            <span class="quiz-accuracy">정답률 {{ activeQuizResult.accuracy }}%</span>
                        </div>
                        <p class="quiz-q">{{ activeQuizResult.question_text }}</p>
                        <div class="quiz-result-bar">
                            <div class="result-fill" :style="{ width: activeQuizResult.response_rate + '%' }"></div>
                        </div>
                        <p class="quiz-meta">{{ activeQuizResult.total_responses }}/{{ activeQuizResult.total_participants }}명 응답</p>
                    </div>

                    <!-- 퀴즈 발동 버튼 -->
                    <div class="quiz-action-row">
                        <button class="btn-quiz-ai" @click="generateAIQuiz" :disabled="quizGenerating">
                            {{ quizGenerating ? '🤖 생성 중...' : '🤖 AI 퀴즈 생성' }}
                        </button>
                        <button class="btn-quiz-manual" @click="showManualQuizForm = !showManualQuizForm">
                            ✏️ 직접 입력
                        </button>
                    </div>

                    <!-- 수동 입력 폼 -->
                    <div v-if="showManualQuizForm" class="manual-quiz-form">
                        <input v-model="manualQuiz.question" placeholder="문제를 입력하세요" class="quiz-input" />
                        <input v-for="(_, i) in 4" :key="i" v-model="manualQuiz.options[i]" :placeholder="'보기 ' + (i+1)" class="quiz-input small" />
                        <select v-model="manualQuiz.correctIndex" class="quiz-input small">
                            <option disabled value="">정답 선택</option>
                            <option v-for="(opt, i) in manualQuiz.options" :key="i" :value="i">{{ opt || '보기 ' + (i+1) }}</option>
                        </select>
                        <input v-model="manualQuiz.explanation" placeholder="해설 (선택)" class="quiz-input" />
                        <button class="btn-quiz-submit" @click="submitManualQuiz">퀴즈 발동!</button>
                    </div>
                </div>
                <!-- 참가자 목록 -->
                <div v-if="liveParticipants.length > 0" class="participants-list">
                    <h3>참가자 ({{ liveParticipants.length }}명)</h3>
                    <div class="participant-grid">
                        <div v-for="p in liveParticipants" :key="p.id" class="participant-chip" :class="{ active: p.is_active }">
                            <span class="dot" :class="{ online: p.is_active }"></span>
                            {{ p.username }}
                        </div>
                    </div>
                </div>
            </div>

                <!-- 실시간 Q&A 피드 (LIVE일 때만) -->
                <div v-if="liveSession.status === 'LIVE'" class="qa-feed-section">
                    <h3>💬 실시간 질문 ({{ liveQuestions.length }}건)</h3>
                    <div v-if="liveQuestions.length === 0" class="qa-empty">
                        학생들이 챗봇에 질문하면 여기에 익명으로 표시됩니다.
                    </div>
                    <div v-else class="qa-list">
                        <div v-for="q in liveQuestions" :key="q.id" class="qa-item" :class="{ answered: q.is_answered }">
                            <div class="qa-header">
                                <span class="qa-badge">익명</span>
                                <span class="qa-votes">👍 {{ q.upvotes }}</span>
                            </div>
                            <p class="qa-question">{{ q.question_text }}</p>
                            <div v-if="q.ai_answer" class="qa-ai-ref">
                                <span class="ai-tag">🤖 AI 답변</span>
                                <p>{{ q.ai_answer.substring(0, 100) }}{{ q.ai_answer.length > 100 ? '...' : '' }}</p>
                            </div>
                            <div v-if="q.is_answered" class="qa-instructor-answer">
                                <span class="instructor-tag">👨‍🏫 내 답변</span>
                                <p>{{ q.instructor_answer }}</p>
                            </div>
                            <div v-else class="qa-reply-form">
                                <input v-model="qaReplyText[q.id]" :placeholder="'답변 입력...'" class="qa-reply-input" @keyup.enter="replyToQuestion(q.id)" />
                                <button class="btn-qa-reply" @click="replyToQuestion(q.id)">답변</button>
                            </div>
                        </div>
                    </div>
                </div>

            <!-- 교안 업로드 영역 (항상 표시) -->
            <div class="materials-section">
                <h3>📄 교안 관리</h3>
                <div class="material-upload-area">
                    <label class="upload-label">
                        <input type="file" accept=".pdf,.ppt,.pptx,.md,.markdown" @change="uploadMaterial" hidden />
                        {{ materialUploading ? '업로드 중...' : '+ 교안 파일 업로드' }}
                    </label>
                </div>
                <div v-if="materials.length > 0" class="material-list">
                    <div v-for="m in materials" :key="m.id" class="material-item">
                        <span class="material-type">{{ m.file_type }}</span>
                        <span class="material-title">{{ m.title }}</span>
                        <button class="btn-material-delete" @click="deleteMaterial(m.id)">×</button>
                    </div>
                </div>
                <p v-else class="empty-text">아직 업로드된 교안이 없습니다.</p>
            </div>
        </div>

    </div>
</template>

<style scoped>
.detail-view { padding: 40px; max-width: 1200px; margin: 0 auto; color: #333; }
.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.header-row h1 { margin: 0; }
.code-badge {
    background: #e3f2fd; color: #1565c0; padding: 10px 20px; border-radius: 50px;
    display: flex; align-items: center; gap: 10px; cursor: pointer; transition: background 0.2s;
    font-size: 16px; border: 1px solid #bbdefb;
}
.code-badge:hover { background: #bbdefb; }
.code-badge .label { font-weight: normal; font-size: 13px; opacity: 0.8; }
.code-badge .value { font-weight: bold; font-size: 20px; letter-spacing: 2px; }
.back-btn { background: none; border: none; font-size: 16px; color: #007bff; cursor: pointer; margin-bottom: 20px; padding: 0; }

/* ── Tab Navigation ── */
.tab-nav {
    display: flex; gap: 4px; margin-bottom: 28px;
    background: #f1f3f5; padding: 4px; border-radius: 12px;
}
.tab-btn {
    flex: 1; padding: 12px 20px; border: none; border-radius: 10px;
    background: transparent; color: #666; font-size: 14px; font-weight: 600;
    cursor: pointer; transition: all 0.25s ease;
}
.tab-btn:hover { background: rgba(255,255,255,0.6); color: #333; }
.tab-btn.active {
    background: #fff; color: #1565c0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* ── Summary Cards ── */
.summary-cards {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px;
}
.summary-card {
    background: #fff; border-radius: 14px; padding: 24px; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #eee;
    transition: transform 0.2s;
}
.summary-card:hover { transform: translateY(-3px); }
.summary-card.highlight {
    background: linear-gradient(135deg, #e3f2fd, #bbdefb);
    border-color: #90caf9;
}
.card-icon { font-size: 28px; margin-bottom: 8px; }
.card-value { font-size: 28px; font-weight: 800; color: #1a1a2e; margin-bottom: 4px; }
.card-label { font-size: 13px; color: #888; }

/* ── Charts ── */
.chart-container { 
    height: 350px; margin-bottom: 24px; background: white; 
    padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); 
    border: 1px solid #eee;
}
.chart-title { margin: 0 0 16px; font-size: 16px; color: #333; }
.charts-row { display: flex; gap: 16px; margin-bottom: 24px; }
.charts-row .chart-container { margin-bottom: 0; }
.flex-2 { flex: 2; }
.flex-1 { flex: 1; }

/* ── Tables ── */
.table-container { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #eee; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 15px; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { background: #f8f9fa; font-weight: 600; font-size: 13px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }

/* ── Student Info ── */
.student-name { font-weight: 600; font-size: 14px; margin-bottom: 2px; color: #333; }
.student-email { font-size: 12px; color: #999; }

/* ── Status Badges ── */
.status-badge {
    padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;
    display: inline-block;
}
.status-badge.critical { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.status-badge.warning { background: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80; }
.status-badge.good { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

/* ── Rate Badges ── */
.rate-badge {
    padding: 5px 12px; border-radius: 20px; font-size: 13px; font-weight: 700;
    display: inline-block;
}
.rate-badge.high { background: #e8f5e9; color: #2e7d32; }
.rate-badge.mid { background: #fff3e0; color: #ef6c00; }
.rate-badge.low { background: #ffebee; color: #c62828; }

/* ── Progress ── */
.progress-wrapper { display: flex; align-items: center; gap: 10px; }
.progress-bar { flex: 1; height: 8px; background: #eee; border-radius: 10px; overflow: hidden; }
.progress-bar .fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.progress-bar .fill.critical { background: #c62828; }
.progress-bar .fill.warning { background: #ef6c00; }
.progress-bar .fill.good { background: #4caf50; }
.percent { font-size: 12px; font-weight: 600; min-width: 35px; text-align: right; }

/* ── Skills ── */
.skill-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.skill-tag {
    background: #e3f2fd; color: #1565c0; padding: 4px 8px; border-radius: 4px; font-size: 11px;
    border: 1px solid #bbdefb;
}
.no-skill { color: #ccc; font-size: 12px; }

/* ── Attendance Dots ── */
.attendance-dots { display: flex; gap: 4px; flex-wrap: wrap; }
.dot {
    width: 16px; height: 16px; border-radius: 4px;
    transition: transform 0.15s;
}
.dot:hover { transform: scale(1.3); cursor: help; }
.dot.present { background: #4caf50; }
.dot.absent { background: #ffcdd2; border: 1px solid #ef9a9a; }

.count-cell { font-weight: 600; color: #555; }

/* ── Score Trend ── */
.score-trend { display: flex; gap: 5px; flex-wrap: wrap; }
.score-pill {
    padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700;
}
.score-pill.high { background: #e8f5e9; color: #2e7d32; }
.score-pill.mid { background: #fff3e0; color: #ef6c00; }
.score-pill.low { background: #ffebee; color: #c62828; }

.question-cell { font-size: 13px; line-height: 1.5; color: #444; }

/* ── Syllabus Manager ── */
.syllabus-manager { margin-top: 40px; padding-top: 30px; border-top: 1px solid #eee; }
.section-title { font-size: 18px; margin-bottom: 20px; color: #333; }
.week-card {
    background: #f9f9f9; padding: 20px; margin-bottom: 16px;
    border-radius: 10px; border: 1px solid #eee;
}
.week-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.week-header h3 { margin: 0; font-size: 16px; color: #333; }
.btn-micro { padding: 4px 8px; font-size: 12px; cursor: pointer; border: 1px solid #ccc; background: white; border-radius: 4px; }
.objective-list { padding-left: 20px; }
.obj-item { margin-bottom: 5px; font-size: 14px; position: relative; }
.delete-x { color: #aaa; cursor: pointer; margin-left: 10px; font-weight: bold; display: none; }
.obj-item:hover .delete-x { display: inline; color: red; }
.add-week-form { margin-top: 24px; background: #f0f8ff; padding: 20px; border-radius: 10px; display: flex; gap: 10px; align-items: center; }
.add-week-form input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
.add-week-form button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }

/* ── Loading & Empty ── */
.loading-state { text-align: center; padding: 60px; color: #888; }
.spinner {
    width: 40px; height: 40px; margin: 0 auto 16px;
    border: 4px solid #eee; border-top-color: #4facfe;
    border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { text-align: center; padding: 60px; color: #999; }

/* ── Recording Upload Zone ── */
.upload-zone {
    border: 2px dashed #ccc; border-radius: 16px;
    padding: 60px 40px; text-align: center; cursor: pointer;
    transition: all 0.3s ease; background: #fafafa;
    margin-bottom: 20px;
}
.upload-zone:hover { border-color: #4facfe; background: #f0f7ff; }
.upload-zone.drag-over { border-color: #4facfe; background: #e3f2fd; transform: scale(1.01); }
.upload-zone.uploading { cursor: wait; border-color: #ff9800; background: #fff8e1; }

.upload-icon { font-size: 48px; margin-bottom: 12px; }
.upload-text { font-size: 16px; font-weight: 600; color: #333; margin-bottom: 6px; }
.upload-hint { font-size: 13px; color: #999; }
.upload-status { font-size: 15px; font-weight: 600; color: #ef6c00; margin-bottom: 4px; }

.upload-progress { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.progress-bar-upload {
    width: 60%; height: 8px; background: #eee; border-radius: 4px;
    overflow: hidden; margin-top: 8px;
}
.fill-upload {
    height: 100%; background: linear-gradient(90deg, #4facfe, #00f2fe);
    border-radius: 4px; transition: width 0.5s ease;
}

.upload-error {
    background: #ffebee; border: 1px solid #ef9a9a; color: #c62828;
    padding: 14px 18px; border-radius: 10px; font-size: 14px; margin-bottom: 16px;
}
.upload-success {
    background: #e8f5e9; border: 1px solid #a5d6a7;
    padding: 18px 22px; border-radius: 12px; margin-bottom: 16px;
}
.success-header { font-size: 18px; font-weight: 700; color: #2e7d32; margin-bottom: 10px; }
.success-detail { display: flex; gap: 20px; font-size: 13px; color: #555; flex-wrap: wrap; }

.filename-cell { font-size: 13px; color: #444; word-break: break-all; }
.error-hint { font-size: 11px; color: #c62828; cursor: help; }

/* ── Summary Modal ── */
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.5); z-index: 2000;
    display: flex; align-items: center; justify-content: center;
}
.modal-card.summary-modal {
    background: white; border-radius: 16px; width: 800px; max-width: 90vw;
    max-height: 80vh; overflow: hidden; display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 24px; border-bottom: 1px solid #eee;
}
.modal-header h2 { margin: 0; font-size: 20px; }
.close-btn {
    background: none; border: none; font-size: 28px; color: #999;
    cursor: pointer; padding: 0 4px; line-height: 1;
}
.close-btn:hover { color: #333; }
.modal-body { padding: 24px; overflow-y: auto; flex: 1; }
.summary-content {
    white-space: pre-wrap; word-break: break-word;
    font-family: 'Pretendard', sans-serif; font-size: 14px;
    line-height: 1.8; color: #333; margin: 0;
}

/* ── Live Session Tab ── */
.live-tab .active { color: #22c55e; }
.live-tab-content { padding: 20px 0; }

.live-create-section { display: flex; justify-content: center; padding: 40px 0; }
.create-card {
    text-align: center; padding: 40px; background: #f8fdf8; border-radius: 16px;
    border: 2px dashed #22c55e33; max-width: 480px; width: 100%;
}
.create-card h2 { margin: 0 0 8px; font-size: 22px; }
.create-card .sub { color: #888; font-size: 14px; margin-bottom: 24px; }
.session-title-input {
    width: 100%; padding: 12px 16px; border: 1px solid #ddd; border-radius: 8px;
    font-size: 14px; margin-bottom: 16px; box-sizing: border-box;
}
.btn-live-create {
    background: #22c55e; color: white; border: none; padding: 12px 32px;
    border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer;
    transition: background 0.2s;
}
.btn-live-create:hover { background: #16a34a; }
.btn-live-create:disabled { opacity: 0.6; cursor: not-allowed; }

.live-active-section { }
.live-status-bar {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 16px; background: #f9f9f9; border-radius: 8px; margin-bottom: 20px;
}
.status-badge {
    padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600;
}
.status-badge.WAITING { background: #fef3c7; color: #92400e; }
.status-badge.LIVE { background: #fee2e2; color: #991b1b; animation: pulse-live 2s infinite; }
.status-badge.ENDED { background: #e5e7eb; color: #6b7280; }
@keyframes pulse-live { 0%,100% { opacity:1; } 50% { opacity:0.7; } }

.participant-count { font-size: 14px; color: #555; }

.code-display {
    display: flex; flex-direction: column; align-items: center;
    padding: 32px; background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
    border-radius: 16px; margin-bottom: 20px; cursor: pointer; transition: transform 0.1s;
}
.code-display:hover { transform: scale(1.02); }
.code-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 2px; }
.code-value { font-size: 56px; font-weight: 800; color: #166534; letter-spacing: 12px; font-family: monospace; }
.code-hint { font-size: 11px; color: #aaa; margin-top: 8px; }

.live-controls { display: flex; gap: 12px; margin-bottom: 24px; }
.btn-live-start {
    flex: 1; padding: 14px; background: #22c55e; color: white; border: none;
    border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
}
.btn-live-start:hover { background: #16a34a; }
.btn-live-end {
    flex: 1; padding: 14px; background: #ef4444; color: white; border: none;
    border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
}
.btn-live-end:hover { background: #dc2626; }

.participants-list { margin-bottom: 24px; }
.participants-list h3 { font-size: 15px; color: #333; margin-bottom: 12px; }
.participant-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.participant-chip {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 14px; background: #f3f4f6; border-radius: 20px; font-size: 13px;
}
.participant-chip.active { background: #f0fdf4; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #d1d5db; }
.dot.online { background: #22c55e; }

.materials-section {
    margin-top: 24px; padding-top: 24px; border-top: 1px solid #eee;
}
.materials-section h3 { font-size: 15px; margin-bottom: 12px; }
.material-upload-area { margin-bottom: 16px; }
.upload-label {
    display: inline-block; padding: 10px 20px; background: #f3f4f6;
    border: 1px dashed #ccc; border-radius: 8px; cursor: pointer;
    font-size: 13px; color: #555; transition: background 0.2s;
}
.upload-label:hover { background: #e5e7eb; }
.material-list { display: flex; flex-direction: column; gap: 8px; }
.material-item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; background: #fafafa; border-radius: 8px;
}
.material-type {
    background: #dbeafe; color: #1e40af; padding: 2px 8px;
    border-radius: 4px; font-size: 11px; font-weight: 600;
}
.material-title { flex: 1; font-size: 13px; }
.btn-material-delete {
    background: none; border: none; color: #aaa; font-size: 18px;
    cursor: pointer; padding: 0 4px;
}
.btn-material-delete:hover { color: #ef4444; }
.empty-text { color: #aaa; font-size: 13px; }

/* ── Pulse Gauge ── */
.pulse-gauge-section { margin-bottom: 24px; padding: 16px; background: #fafafa; border-radius: 12px; }
.pulse-gauge-section h3 { font-size: 14px; margin: 0 0 12px; color: #333; }
.pulse-gauge-section.empty { text-align: center; }
.pulse-waiting { color: #aaa; font-size: 13px; margin: 0; }

.gauge-bar {
    display: flex; height: 28px; border-radius: 14px; overflow: hidden;
    background: #e5e7eb; margin-bottom: 8px;
}
.gauge-fill { transition: width 0.5s ease; }
.gauge-fill.understand { background: linear-gradient(90deg, #22c55e, #4ade80); }
.gauge-fill.confused { background: linear-gradient(90deg, #f87171, #ef4444); }

.gauge-labels { display: flex; justify-content: space-between; font-size: 12px; }
.label-understand { color: #16a34a; font-weight: 600; }
.label-confused { color: #dc2626; font-weight: 600; }

/* ── Quiz Control ── */
.quiz-control-section {
    margin-bottom: 24px; padding: 16px; background: #fafafa; border-radius: 12px;
}
.quiz-control-section h3 { font-size: 14px; margin: 0 0 12px; }

.quiz-result-card {
    padding: 12px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;
    margin-bottom: 12px;
}
.quiz-result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.quiz-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #dbeafe; color: #1e40af; }
.quiz-accuracy { font-size: 14px; font-weight: 700; color: #166534; }
.quiz-q { font-size: 13px; margin: 0 0 8px; color: #333; }
.quiz-result-bar { height: 8px; border-radius: 4px; background: #e5e7eb; }
.result-fill { height: 100%; border-radius: 4px; background: #3b82f6; transition: width 0.5s; }
.quiz-meta { font-size: 11px; color: #888; margin: 4px 0 0; }

.quiz-action-row { display: flex; gap: 8px; margin-bottom: 12px; }
.btn-quiz-ai, .btn-quiz-manual {
    flex: 1; padding: 10px; border: none; border-radius: 8px; font-size: 13px;
    font-weight: 600; cursor: pointer; transition: background 0.2s;
}
.btn-quiz-ai { background: #eef2ff; color: #4338ca; }
.btn-quiz-ai:hover { background: #e0e7ff; }
.btn-quiz-ai:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-quiz-manual { background: #f3f4f6; color: #374151; }
.btn-quiz-manual:hover { background: #e5e7eb; }

.manual-quiz-form { display: flex; flex-direction: column; gap: 8px; }
.quiz-input {
    padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px;
    font-size: 13px; width: 100%; box-sizing: border-box;
}
.quiz-input.small { padding: 8px 12px; }
.btn-quiz-submit {
    padding: 10px; background: #f59e0b; color: white; border: none;
    border-radius: 8px; font-weight: 600; cursor: pointer;
}
.btn-quiz-submit:hover { background: #d97706; }

/* ── Q&A Feed ── */
.qa-feed-section {
    margin-bottom: 24px; padding: 16px; background: #fafafa; border-radius: 12px;
}
.qa-feed-section h3 { font-size: 14px; margin: 0 0 12px; }
.qa-empty { color: #aaa; font-size: 13px; text-align: center; padding: 20px; }

.qa-list { display: flex; flex-direction: column; gap: 12px; max-height: 400px; overflow-y: auto; }
.qa-item {
    padding: 12px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;
    transition: border-color 0.2s;
}
.qa-item.answered { border-color: #22c55e; background: #f0fdf4; }
.qa-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.qa-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #f3e8ff; color: #7c3aed; }
.qa-votes { font-size: 12px; color: #888; }
.qa-question { font-size: 13px; color: #333; margin: 0 0 8px; font-weight: 500; }

.qa-ai-ref {
    padding: 8px; background: #eff6ff; border-radius: 6px; margin-bottom: 8px;
}
.ai-tag { font-size: 10px; color: #3b82f6; font-weight: 600; }
.qa-ai-ref p { font-size: 11px; color: #666; margin: 4px 0 0; }

.qa-instructor-answer { padding: 8px; background: #f0fdf4; border-radius: 6px; }
.instructor-tag { font-size: 10px; color: #16a34a; font-weight: 600; }
.qa-instructor-answer p { font-size: 12px; color: #333; margin: 4px 0 0; }

.qa-reply-form { display: flex; gap: 8px; }
.qa-reply-input {
    flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px;
    font-size: 12px;
}
.btn-qa-reply {
    padding: 8px 16px; background: #3b82f6; color: white; border: none;
    border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
}
.btn-qa-reply:hover { background: #2563eb; }
</style>
