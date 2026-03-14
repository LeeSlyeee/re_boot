<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api/axios';
import { useToast } from '../composables/useToast';
const { showToast } = useToast();

import { Bar, Doughnut } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement);

const route = useRoute();
const router = useRouter();
const students = ref([]);
const lectureId = route.params.id;
const lectureTitle = ref('');
const lectureCode = ref('');

// [3-1] 강의명 인라인 수정
const isEditingTitle = ref(false);
const editTitleValue = ref('');

const startEditTitle = () => {
    editTitleValue.value = lectureTitle.value;
    isEditingTitle.value = true;
};

const saveLectureTitle = async () => {
    const newTitle = editTitleValue.value.trim();
    if (!newTitle || newTitle === lectureTitle.value) {
        isEditingTitle.value = false;
        return;
    }
    try {
        await api.patch(`/learning/lectures/${lectureId}/`, { title: newTitle });
        lectureTitle.value = newTitle;
        showToast('강의명이 수정되었습니다.', 'success');
    } catch(e) {
        showToast('강의명 수정 실패', 'error');
    }
    isEditingTitle.value = false;
};

// Tab Management
const activeTab = ref('monitor'); // 'monitor' | 'attendance' | 'quiz' | 'recording' | 'live' | 'diagnostic' | 'review'

const copyCode = async () => {
    try {
        await navigator.clipboard.writeText(lectureCode.value);
        showToast(`입장 코드(${lectureCode.value}, 'success')가 복사되었습니다.`);
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
            description: ''
        });
        newWeekTitle.value = '';

        isAddingWeek.value = false;
        await fetchChecklist();
    } catch (e) {
        showToast("주차 추가 실패", 'error');
    }
};

const addObjective = async (weekId) => {
    const text = prompt("학습 목표를 입력하세요:");
    if (!text) return;
    try {
        await api.post(`/learning/syllabus/${weekId}/objective/`, { content: text });
        await fetchChecklist();
    } catch (e) {
        showToast("목표 추가 실패", 'error');
    }
};

const deleteObjective = async (objId) => {
    if(!confirm("삭제하시겠습니까?")) return;
    try {
        await api.delete(`/learning/objectives/${objId}/`);
        await fetchChecklist();
    } catch (e) {
        showToast("삭제 실패", 'error');
    }
};

// [3-3] 강의 계획서 인라인 수정
const updateWeekTitle = async (week, newTitle) => {
    if (!newTitle.trim() || newTitle === week.title) return;
    try {
        await api.patch(`/learning/syllabus/${week.id}/`, { title: newTitle });
        week.title = newTitle;
    } catch(e) {
        showToast('주차 제목 수정 실패', 'error');
    }
};

const updateObjective = async (obj, newContent) => {
    if (!newContent.trim() || newContent === obj.content) return;
    try {
        await api.patch(`/learning/objectives/${obj.id}/`, { content: newContent });
        obj.content = newContent;
    } catch(e) {
        showToast('목표 수정 실패', 'error');
    }
};

// [3-2] 파일 업로드
const uploadSyllabusFile = async (weekId, event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await api.post(`/learning/syllabus/${weekId}/upload-file/`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        showToast('파일이 업로드되었습니다.', 'success');
        // 강제 리로드
        await fetchChecklist();
    } catch(e) {
        showToast('파일 업로드 실패', 'error');
    }
    // input 초기화
    event.target.value = '';
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
const quizDistributionChart = ref(null);
const quizStudentChart = ref(null);

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
    if (tab === 'diagnostic') fetchDiagnostics();
    if (tab === 'analytics') loadAnalytics();
    if (tab === 'review') fetchPendingReviewRoutes();
};

// ── Phase 2: 복습 루트 관리 ──
const pendingReviewRoutes = ref([]);
const reviewRoutesLoading = ref(false);

const fetchPendingReviewRoutes = async () => {
    reviewRoutesLoading.value = true;
    try {
        const { data } = await api.get('/learning/review-routes/pending/');
        pendingReviewRoutes.value = data.routes || data || [];
    } catch (e) { pendingReviewRoutes.value = []; }
    reviewRoutesLoading.value = false;
};

const approveReviewRoute = async (routeId) => {
    try {
        await api.post(`/learning/review-routes/${routeId}/approve/`);
        pendingReviewRoutes.value = pendingReviewRoutes.value.filter(r => r.id !== routeId);
    } catch (e) { showToast('승인 실패: ' + (e.response?.data?.error || '', 'error')); }
};

const editReviewRouteTitle = async (routeId) => {
    const route = pendingReviewRoutes.value.find(r => r.id === routeId);
    if (!route) return;
    const newTitle = prompt('복습 루트 이름 수정:', route.title);
    if (!newTitle || newTitle === route.title) return;
    try {
        const { data } = await api.patch(`/learning/review-routes/${routeId}/`, { title: newTitle });
        route.title = data.title || newTitle;
    } catch (e) { showToast('수정 실패', 'error'); }
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
        } else { showToast('세션 생성 실패: ' + (e.response?.data?.error || '', 'error')); }
    } finally { liveLoading.value = false; }
};

const startLiveSession = async () => {
    if (!liveSession.value) return;

    // 수업 시작 전 라즈베리파이 연결 시도 (입력된 IP가 있으면)
    if (rpiHost.value.trim()) {
        rpiConnecting.value = true;
        try {
            const { data: rpiData } = await api.post('/learning/live/rpi-status/', {
                host: rpiHost.value.trim(),
                port: parseInt(rpiPort.value) || 9999,
            });
            rpiConnected.value = rpiData.rpi_connected;
            if (rpiData.rpi_connected) {
                showToast(`🟢 라즈베리파이 연결 성공 (${rpiHost.value})`, 'success');
            } else {
                showToast('🔴 라즈베리파이 미연결 — 로컬 모드로 수업 시작', 'warning');
            }
        } catch (e) { /* 연결 실패해도 수업은 시작 */ }
        rpiConnecting.value = false;
    }

    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/start/`);
        liveSession.value = { ...liveSession.value, ...data };
    } catch (e) { showToast('세션 시작 실패: ' + (e.response?.data?.error || '', 'error')); }
};

const endLiveSession = async () => {
    if (!liveSession.value || !confirm('세션을 종료하시겠습니까?')) return;
    try {
        await api.post(`/learning/live/${liveSession.value.id}/end/`);
        stopLivePolling();
        stopSTT();

        // 로컬 WebSocket Agent에 마이크 클라이언트 종료 요청
        if (kwsAgentWs && kwsAgentWs.readyState === WebSocket.OPEN) {
            kwsAgentWs.send(JSON.stringify({ action: 'shutdown' })); // stop 대신 shutdown으로 변경
            // 프로세스가 완전히 종료될 시간을 약간 벌어준 뒤 소켓 닫음 (옵션)
            setTimeout(() => {
                if (kwsAgentWs) kwsAgentWs.close();
            }, 100);
        }
        kwsAgentWs = null;
        kwsAgentConnected.value = false;

        // 세션 종료 후 상태 유지 → 인사이트 폴링 시작
        liveSession.value = { ...liveSession.value, status: 'ENDED' };
        startInsightPolling();
    } catch (e) { showToast('세션 종료 실패', 'error'); }
};

// ── 인사이트 리포트 폴링 ──
const insightData = ref(null);
const insightPolling = ref(null);

const fetchInsight = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.get(`/learning/live/${liveSession.value.id}/note/`);
        if (data.status === 'DONE') {
            insightData.value = data;
            if (insightPolling.value) { clearInterval(insightPolling.value); insightPolling.value = null; }
        }
    } catch {}
};

const startInsightPolling = () => {
    fetchInsight();
    insightPolling.value = setInterval(fetchInsight, 3000);
};

const renderInsightMarkdown = (text) => {
    if (!text) return '';
    return text
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/\n/g, '<br/>');
};

const renderMarkdown = (text) => {
    if (!text) return '';
    let html = text;
    // 코드블록 (```)
    html = html.replace(/```([\s\S]*?)```/g, '<pre style="background:#f3f4f6;padding:12px;border-radius:8px;overflow-x:auto;font-size:13px;">$1</pre>');
    // 인라인 코드
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 헤더
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // 볼드 / 이탤릭
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // 테이블 (간단 지원)
    html = html.replace(/\|(.+)\|/g, (match) => {
        if (match.includes('---')) return '';
        const cells = match.split('|').filter(c => c.trim());
        const cellHtml = cells.map(c => `<td style="border:1px solid #e5e7eb;padding:6px 10px;">${c.trim()}</td>`).join('');
        return `<tr>${cellHtml}</tr>`;
    });
    // 리스트
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^• (.+)$/gm, '<li>$1</li>');
    // 블록인용
    html = html.replace(/^> (.+)$/gm, '<blockquote style="border-left:3px solid #4facfe;padding-left:12px;color:#636b72;margin:8px 0;">$1</blockquote>');
    // 수평선
    html = html.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">');
    // 줄바꿈
    html = html.replace(/\n/g, '<br/>');
    return html;
};

// ── Step E: 승인 + 교안 매핑 ──
const makePublicForAbsent = ref(true);
const selectedMaterialIds = ref([]);
const noteDistributionScope = ref('ALL');  // B4: 배포 범위

const approveNote = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/note/approve/`, {
            is_public: makePublicForAbsent.value,
            scope: noteDistributionScope.value,  // B4: 배포 범위 전송
        });
        if (data.ok) {
            insightData.value = { ...insightData.value, is_approved: true, is_public: data.is_public };
            showToast(`노트가 승인되었습니다. (범위: ${data.scope}, 'success')`);
        }
    } catch (e) { showToast('승인 실패: ' + (e.response?.data?.error || '', 'error')); }
};

const linkMaterials = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/note/materials/`, {
            material_ids: selectedMaterialIds.value,
        });
        showToast(`${data.linked_count}개 교안이 연결되었습니다.`, 'success');
    } catch (e) { showToast('교안 연결 실패', 'error'); }
};

// ── Phase 2-1: Weak Zone ──
const weakZones = ref([]);

const fetchWeakZones = async () => {
    if (!liveSession.value) return;
    try {
        const { data } = await api.get(`/learning/live/${liveSession.value.id}/weak-zones/`);
        weakZones.value = data.weak_zones || [];
    } catch (e) { /* silent */ }
};

const pushWeakZone = async (wzId, materialId = null) => {
    try {
        const body = materialId ? { material_id: materialId } : {};
        await api.post(`/learning/live/${liveSession.value.id}/weak-zones/${wzId}/push/`, body);
        await fetchWeakZones();
    } catch (e) { showToast('보충 자료 전송 실패', 'error'); }
};

const dismissWeakZone = async (wzId) => {
    try {
        await api.post(`/learning/live/${liveSession.value.id}/weak-zones/${wzId}/dismiss/`);
        await fetchWeakZones();
    } catch (e) { showToast('거부 실패', 'error'); }
};

const activeWeakZones = computed(() => weakZones.value.filter(w => w.status === 'DETECTED'));

// ── Phase 2-4: Formative Assessment ──
const formativeStatus = ref(null);
const formativeCount = ref(0);
const formativeGenerating = ref(false);

const generateFormative = async () => {
    if (!liveSession.value) return;
    formativeGenerating.value = true;
    try {
        const { data } = await api.post(`/learning/formative/${liveSession.value.id}/generate/`);
        formativeStatus.value = data.status;
        formativeCount.value = data.total_questions;
    } catch (e) {
        showToast('형성평가 문항 생성 실패', 'error');
    } finally {
        formativeGenerating.value = false;
    }
};

// ── Phase 2-2: Adaptive Content ──
const adaptiveGenerating = ref({});
const adaptiveContents = ref({});
const adaptivePreview = ref(null); // { materialId, level, title, content, status, acId }

const generateAdaptive = async (materialId) => {
    adaptiveGenerating.value = { ...adaptiveGenerating.value, [materialId]: true };
    try {
        const { data } = await api.post(`/learning/materials/${materialId}/generate-adaptive/`);
        adaptiveContents.value = { ...adaptiveContents.value, [materialId]: data.levels };
        // 생성 후 전체 내용 다시 fetch (content 포함)
        await fetchAdaptiveContents(materialId);
    } catch (e) {
        showToast('AI 변형 생성 실패: ' + (e.response?.data?.error || e.message, 'error'));
    }
    adaptiveGenerating.value = { ...adaptiveGenerating.value, [materialId]: false };
};

const fetchAdaptiveContents = async (materialId) => {
    try {
        const { data } = await api.get(`/learning/materials/${materialId}/adaptive/`);
        adaptiveContents.value = { ...adaptiveContents.value, [materialId]: data.adaptive_contents };
    } catch (e) { /* silent */ }
};

// 교안 로드 후 기존 변형도 자동 로드
const fetchAllAdaptive = async () => {
    for (const m of materials.value) {
        await fetchAdaptiveContents(m.id);
    }
};

const approveAdaptive = async (acId, materialId) => {
    try {
        await api.post(`/learning/adaptive/${acId}/approve/`);
        await fetchAdaptiveContents(materialId);
        if (adaptivePreview.value && adaptivePreview.value.acId === acId) {
            adaptivePreview.value.status = 'APPROVED';
        }
    } catch (e) { showToast('승인 실패', 'error'); }
};

const openAdaptivePreview = (ac, materialId) => {
    adaptivePreview.value = {
        materialId,
        level: ac.level,
        title: ac.title || `Level ${ac.level}`,
        content: ac.content || ac.content_preview || '(내용 없음)',
        status: ac.status,
        acId: ac.id,
    };
};

const closeAdaptivePreview = () => {
    adaptivePreview.value = null;
};

// ── Phase 3: Analytics State ──
const analyticsSubTab = ref('overview');
const analyticsLoading = ref(false);
const analyticsOverview = ref(null);
const weakInsights = ref(null);
const aiSuggestions = ref(null);
const qualityReport = ref(null);

// 메시지 모달
const showMsgModal = ref(false);
const msgTarget = ref(null);
const msgTitle = ref('');
const msgContent = ref('');

// 그룹 메시지
const groupMsgLevel = ref(0);
const groupMsgTitle = ref('');
const groupMsgContent = ref('');

// Analytics computed charts
const levelChartData = computed(() => {
    if (!analyticsOverview.value?.level_distribution) return null;
    const dist = analyticsOverview.value.level_distribution;
    return {
        labels: ['Beginner', 'Intermediate', 'Advanced'],
        datasets: [{
            data: [dist.BEGINNER || 0, dist.INTERMEDIATE || 0, dist.ADVANCED || 0],
            backgroundColor: ['#ef5350', '#ffa726', '#66bb6a'],
        }]
    };
});

const sessionComparisonChart = computed(() => {
    if (!weakInsights.value?.session_comparison?.length) return null;
    const sc = weakInsights.value.session_comparison;
    return {
        labels: sc.map(s => s.session_title),
        datasets: [
            { label: '이해율', data: sc.map(s => s.understand_rate), backgroundColor: '#42a5f5' },
            { label: '퀴즈 정답률', data: sc.map(s => s.quiz_accuracy), backgroundColor: '#66bb6a' },
            { label: '형성평가 평균', data: sc.map(s => s.formative_avg), backgroundColor: '#ffa726' },
        ]
    };
});

// Analytics fetch
const fetchAnalyticsOverview = async () => {
    try {
        const { data } = await api.get(`/learning/professor/${lectureId}/analytics/overview/`);
        analyticsOverview.value = data;
    } catch (e) { console.error('overview fetch error', e); }
};
const fetchWeakInsights = async () => {
    try {
        const { data } = await api.get(`/learning/professor/${lectureId}/analytics/weak-insights/`);
        weakInsights.value = data;
    } catch (e) { console.error('weak insights fetch error', e); }
};
const fetchAISuggestions = async () => {
    try {
        const { data } = await api.get(`/learning/professor/${lectureId}/analytics/ai-suggestions/`);
        aiSuggestions.value = data;
    } catch (e) { console.error('ai suggestions fetch error', e); }
};
const fetchQualityReport = async () => {
    try {
        const { data } = await api.get(`/learning/professor/${lectureId}/analytics/quality-report/`);
        qualityReport.value = data;
    } catch (e) { console.error('quality report fetch error', e); }
};

const loadAnalytics = async () => {
    analyticsLoading.value = true;
    await Promise.all([
        fetchAnalyticsOverview(),
        fetchWeakInsights(),
        fetchAISuggestions(),
        fetchQualityReport(),
    ]);
    analyticsLoading.value = false;
};

// 메시지 발송
const openMessage = (student) => {
    msgTarget.value = student;
    msgTitle.value = '';
    msgContent.value = '';
    showMsgModal.value = true;
};

const sendDirectMessage = async () => {
    try {
        await api.post(`/learning/professor/${lectureId}/send-message/`, {
            student_ids: [msgTarget.value.id],
            title: msgTitle.value,
            content: msgContent.value,
            message_type: 'FEEDBACK',
        });
        showToast('메시지 발송 완료', 'success');
        showMsgModal.value = false;
    } catch (e) { showToast('메시지 발송 실패', 'error'); }
};

const sendGroupMessage = async () => {
    try {
        await api.post(`/learning/professor/${lectureId}/send-group-message/`, {
            target_level: groupMsgLevel.value,
            title: groupMsgTitle.value,
            content: groupMsgContent.value,
            message_type: 'NOTICE',
        });
        showToast('그룹 메시지 발송 완료', 'success');
        groupMsgTitle.value = '';
        groupMsgContent.value = '';
    } catch (e) { showToast('발송 실패', 'error'); }
};

// AI 제안 액션
const handleSuggestion = async (type, id, action) => {
    try {
        await api.post(`/learning/professor/${lectureId}/analytics/ai-suggestions/`, {
            type, id, action,
        });
        await fetchAISuggestions();
    } catch (e) { showToast('처리 실패', 'error'); }
};

// 재분류 적용
const applyRedistribution = async () => {
    if (!qualityReport.value?.level_redistribution?.changes?.length) return;
    if (!confirm('레벨 재분류를 일괄 적용하시겠습니까?')) return;
    try {
        await api.post(`/learning/professor/${lectureId}/apply-redistribution/`, {
            changes: qualityReport.value.level_redistribution.changes,
        });
        showToast('레벨 재분류 적용 완료', 'success');
        await loadAnalytics();
    } catch (e) { showToast('적용 실패', 'error'); }
};

const startLivePolling = () => {
    stopLivePolling();
    fetchRpiStatus();  // 라즈베리파이 연결 상태 초기 조회
    livePollingTimer.value = setInterval(async () => {
        if (!liveSession.value) return;
        try {
            const { data } = await api.get(`/learning/live/${liveSession.value.id}/status/`);
            liveSession.value = { ...liveSession.value, ...data };
            liveParticipants.value = data.participants || [];
            // 세션이 종료/일시정지 상태로 변경된 경우 → 잔여 퀴즈 제안 즉시 클리어
            if (data.status && data.status !== 'LIVE') {
                if (quizSuggestion.value) {
                    console.log('[Polling] 세션이 LIVE가 아님 → 퀴즈 제안 클리어');
                    quizSuggestion.value = null;
                }
                return; // ENDED 세션에서 더 이상 폴링 불필요
            }
            // 펄스 통계 동시 조회
            try {
                const pulse = await api.get(`/learning/live/${liveSession.value.id}/pulse-stats/`);
                pulseStats.value = pulse.data;
            } catch {}
            // 퀴즈 결과 동시 조회
            await fetchQuizResult();
            // Q&A 질문 동시 조회
            await fetchLiveQuestions();
            // AI 퀴즈 제안 체크
            if (!quizSuggestion.value) await fetchQuizSuggestion();
            // Phase 2-1: Weak Zone 체크
            await fetchWeakZones();
        } catch (e) { /* ignore */ }
    }, 5000);
};

const stopLivePolling = () => {
    if (livePollingTimer.value) { clearInterval(livePollingTimer.value); livePollingTimer.value = null; }
};



// ── 🔌 라즈베리파이 연결 관리 ──
const rpiHost = ref('172.16.206.43');
const rpiPort = ref('9999');
const rpiConnected = ref(false);
const rpiConnecting = ref(false);

// WebSocket Agent 연결 (교수 PC 로컬)
let kwsAgentWs = null;
const kwsAgentConnected = ref(false);

const fetchRpiStatus = async () => {
    try {
        const { data } = await api.get('/learning/live/rpi-status/');
        rpiConnected.value = data.rpi_connected;
        rpiHost.value = data.rpi_host || rpiHost.value;
        rpiPort.value = String(data.rpi_port || rpiPort.value);
    } catch (e) { /* silent */ }
};

const connectRpi = async () => {
    if (!rpiHost.value.trim()) { showToast('IP를 입력해주세요.', 'warning'); return; }
    rpiConnecting.value = true;
    try {
        const { data } = await api.post('/learning/live/rpi-status/', {
            host: rpiHost.value.trim(),
            port: parseInt(rpiPort.value) || 9999,
            manual_launch: true,
        });
        rpiConnected.value = data.rpi_connected;

        // 라즈베리파이 연결 확인 후 KWS Agent에 WebSocket만 연결 (오디오는 DSCNN/STT 버튼 클릭 시 시작)
        if (data.rpi_connected) {
            try {
                kwsAgentWs = new WebSocket('ws://localhost:5555');
                kwsAgentWs.onopen = () => {
                    kwsAgentConnected.value = true;
                    console.log('[KWS Agent] WebSocket 연결 완료 (대기 중)');
                };
                kwsAgentWs.onmessage = (event) => {
                    const resp = JSON.parse(event.data);
                    console.log('[KWS Agent]', resp);
                };
                kwsAgentWs.onclose = () => { kwsAgentConnected.value = false; };
                kwsAgentWs.onerror = () => {
                    kwsAgentConnected.value = false;
                    showToast('⚠️ KWS Agent 미실행 — PC에서 KWS Agent를 실행해주세요.', 'warning');
                };
            } catch (e) {
                console.error('KWS Agent 연결 실패:', e);
            }
        }

        showToast(
            data.rpi_connected
                ? `🟢 라즈베리파이 연결 성공 (${rpiHost.value})`
                : `🔴 연결 실패 — 로컬 모드로 동작`,
            data.rpi_connected ? 'success' : 'warning'
        );
    } catch (e) {
        showToast('연결 요청 실패: ' + (e.response?.data?.error || e.message), 'error');
    }
    rpiConnecting.value = false;
};

// ── STT (Web Speech API) ──
const sttActive = ref(false);
const dscnnOnlyActive = ref(false);  // DSCNN Only 모드 활성화 여부

const sttRecognition = ref(null);
const sttLastText = ref('');
let sttLastProcessedIndex = 0;  // 마지막으로 처리(전송)한 result 인덱스
let sttPendingInterim = '';     // 아직 isFinal이 안 된 interim 텍스트

const flushPendingSTT = async () => {
    // 세션 재시작/종료 시 아직 전송되지 않은 interim 텍스트를 강제 전송
    if (sttPendingInterim && liveSession.value) {
        const text = sttPendingInterim.trim();
        sttPendingInterim = '';
        if (text.length > 2) {  // 의미 없는 짧은 조각 필터
            try {
                await api.post(`/learning/live/${liveSession.value.id}/stt/`, { text });
                console.log('🔄 Flush interim STT:', text);
            } catch (e) { console.error('❌ Flush STT 실패:', e); }
        }
    }
};

const startSTT = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showToast('이 브라우저는 음성 인식을 지원하지 않습니다. Chrome을 사용해주세요.', 'warning');
        return;
    }
    // KWS Agent에 START 명령 전송 (카운터 부분에서만)
    if (kwsAgentWs?.readyState === WebSocket.OPEN && !dscnnOnlyActive.value) {
        kwsAgentWs.send(JSON.stringify({
            action: 'start',
            ip: rpiHost.value.trim(),
            port: parseInt(rpiPort.value) || 9999
        }));
        console.log('[KWS Agent] START 명령 전송 (STT+DSCNN)');
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'ko-KR';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        console.log('🎙️ STT 시작됨');
        sttLastText.value = '🎙️ 마이크 대기 중... 말씀해주세요';
        sttLastProcessedIndex = 0;
        sttPendingInterim = '';
    };

    recognition.onresult = async (event) => {
        // 모든 미처리 결과를 순회 (잘림 방지)
        for (let i = sttLastProcessedIndex; i < event.results.length; i++) {
            const result = event.results[i];
            const text = result[0].transcript.trim();

            if (result.isFinal) {
                // 최종 확정된 텍스트 → 서버로 전송
                sttPendingInterim = '';  // interim 클리어
                sttLastText.value = text;
                console.log('📝 STT Final:', text);

                if (text && liveSession.value) {
                    try {
                        await api.post(`/learning/live/${liveSession.value.id}/stt/`, { text });
                        console.log('✅ STT 전송 완료');
                    } catch (e) { console.error('❌ STT 전송 실패:', e); }
                }
                sttLastProcessedIndex = i + 1;  // 이 결과는 처리 완료
            } else {
                // 중간 결과 → 화면에만 표시 + pending 보관
                sttPendingInterim = text;
                sttLastText.value = text + ' ...';
            }
        }
    };

    recognition.onerror = (e) => {
        console.error('❌ STT Error:', e.error, e.message);
        sttLastText.value = `❌ 에러: ${e.error}`;
        // no-speech는 자동 재시작되므로 무시
        if (e.error !== 'no-speech' && e.error !== 'aborted') {
            sttActive.value = false;
        }
    };

    recognition.onend = async () => {
        console.log('🔄 STT 세션 종료');
        // [핵심 수정] 세션 종료 전 미전송 interim 텍스트 강제 전송
        await flushPendingSTT();

        if (sttActive.value && liveSession.value?.status === 'LIVE') {
            // 짧은 딜레이 후 재시작 (브라우저 안정성)
            setTimeout(() => {
                try {
                    sttLastProcessedIndex = 0;
                    recognition.start();
                } catch (e) {
                    console.error('STT 재시작 실패:', e);
                    sttActive.value = false;
                }
            }, 100);
        }
    };

    recognition.start();
    sttRecognition.value = recognition;
    sttActive.value = true;
};

const stopSTT = () => {
    if (sttRecognition.value) {
        flushPendingSTT();
        sttRecognition.value.stop();
        sttRecognition.value = null;
    }
    sttActive.value = false;
    // DSCNN Only가 비활성화일 때만 STOP (DSCNN도 함께 트는 중이려면 안 끊음)
    if (!dscnnOnlyActive.value && kwsAgentWs?.readyState === WebSocket.OPEN) {
        kwsAgentWs.send(JSON.stringify({ action: 'stop' }));
        console.log('[KWS Agent] STOP 명령 전송');
    }
};

// ── DSCNN Only 모드: STT 없이 KWS 웹훅만 대기 ──
const startDSCNNOnly = () => {
    dscnnOnlyActive.value = true;
    sttLastText.value = '🧠 DSCNN 감지 대기 중... 키워드를 말씀해주세요';
    // KWS Agent에 START 명령 전송
    if (kwsAgentWs?.readyState === WebSocket.OPEN && !sttActive.value) {
        kwsAgentWs.send(JSON.stringify({
            action: 'start',
            ip: rpiHost.value.trim(),
            port: parseInt(rpiPort.value) || 9999
        }));
        console.log('[KWS Agent] START 명령 전송 (DSCNN Only)');
    }
    showToast('🧠 DSCNN Only 모드 시작 — KWS 키워드 감지 대기 중', 'success');
};
const stopDSCNNOnly = () => {
    dscnnOnlyActive.value = false;
    sttLastText.value = '';
    // STT가 비활성화일 때만 STOP
    if (!sttActive.value && kwsAgentWs?.readyState === WebSocket.OPEN) {
        kwsAgentWs.send(JSON.stringify({ action: 'stop' }));
        console.log('[KWS Agent] STOP 명령 전송');
    }
    showToast('DSCNN Only 모드 종료', 'info');
};

// ── 퀴즈 제안 (AI 자동 생성 → 교수자 승인) ──
const quizSuggestion = ref(null);

const fetchQuizSuggestion = async () => {
    if (!liveSession.value || liveSession.value.status !== 'LIVE') return;
    try {
        const { data } = await api.get(`/learning/live/${liveSession.value.id}/quiz/suggestion/`);
        if (data && data.id) {
            quizSuggestion.value = data;
        }
    } catch (e) {
        console.error('[fetchQuizSuggestion] Error:', e);
    }
};

const approveQuizSuggestion = async () => {
    if (!quizSuggestion.value) return;
    try {
        const { data } = await api.post(`/learning/live/${liveSession.value.id}/quiz/${quizSuggestion.value.id}/approve/`, {
            time_limit: 60
        });
        lastActiveQuizId.value = data?.id || null;
        quizSuggestion.value = null;
        showToast('✅ 퀴즈 발동!', 'success');
        // STT/DSCNN은 중단하지 않고 계속 유지
    } catch (e) { showToast('퀴즈 발동 실패: ' + (e.response?.data?.error || ''), 'error'); }
};

const dismissQuizSuggestion = async () => {
    if (quizSuggestion.value && liveSession.value) {
        try {
            await api.post(`/learning/live/${liveSession.value.id}/quiz/${quizSuggestion.value.id}/dismiss/`);
        } catch {}
    }
    quizSuggestion.value = null;
    // 퀴즈 제안 무시 시에는 STT/KWS를 중단하지 않음 (교수자는 계속 강의 중)
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
        showToast(`AI 퀴즈 발동! (문제: ${data.question_text.substring(0, 40)}...)`, 'success');
        // STT/DSCNN은 중단하지 않고 계속 유지
    } catch (e) {
        showToast('AI 퀴즈 생성 실패: ' + (e.response?.data?.error || ''), 'error');
    } finally { quizGenerating.value = false; }
};

// ── Phase 1: 진단 분석 ──
const diagnosticData = ref(null);
const diagnosticLoading = ref(false);

const fetchDiagnostics = async () => {
    diagnosticLoading.value = true;
    try {
        const { data } = await api.get(`/learning/professor/${lectureId}/diagnostics/`);
        diagnosticData.value = data;
    } catch (e) { console.error('진단 데이터 로드 실패:', e); }
    diagnosticLoading.value = false;
};

const levelDonutData = computed(() => {
    if (!diagnosticData.value) return null;
    const d = diagnosticData.value.level_distribution;
    return {
        labels: ['Level 1 (초보)', 'Level 2 (기초)', 'Level 3 (심화)'],
        datasets: [{
            data: [d.level_1, d.level_2, d.level_3],
            backgroundColor: ['#f59e0b', '#3b82f6', '#8b5cf6'],
            borderWidth: 0,
        }]
    };
});

const donutOptions = {
    responsive: true,
    plugins: {
        legend: { position: 'bottom', labels: { font: { size: 12 }, padding: 16 } },
    },
    cutout: '65%',
};

const weakSkillColor = (rate) => {
    if (rate >= 70) return '#ef4444';
    if (rate >= 50) return '#f59e0b';
    if (rate >= 30) return '#eab308';
    return '#22c55e';
};

const submitManualQuiz = async () => {
    if (!liveSession.value) return;
    const q = manualQuiz.value;
    if (!q.question || q.options.some(o => !o) || q.correctIndex === '') {
        showToast('모제와 보기 4개, 정답을 모두 입력해주세요.', 'warning'); return;
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
        showToast('✅ 퀴즈 발동!', 'success');
        // STT/DSCNN은 중단하지 않고 계속 유지
    } catch (e) { showToast('퀴즈 생성 실패: ' + (e.response?.data?.error || ''), 'error'); }
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
    } catch (e) { showToast('답변 실패: ' + (e.response?.data?.error || '', 'error')); }
};
const copyLiveCode = async () => {
    if (!liveSession.value?.session_code) return;
    try { await navigator.clipboard.writeText(liveSession.value.session_code); showToast('코드 복사 완료!', 'success'); } catch {}
};



// 펄스 50% 미만 경고
const pulseWarning = computed(() => {
    const rate = pulseStats.value?.understand_rate || 0;
    const total = pulseStats.value?.total || 0;
    return total > 0 && rate < 50;
});

const fetchMaterials = async () => {
    try {
        const { data } = await api.get(`/learning/materials/list/?lecture_id=${lectureId}`);
        materials.value = data;
        // 기존 변형 자동 로드
        await fetchAllAdaptive();
    } catch {}
};

const uploadMaterial = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    materialUploading.value = true;
    try {
        const fd = new FormData(); fd.append('file', file); fd.append('lecture_id', lectureId); fd.append('title', file.name);
        await api.post('/learning/materials/upload/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        await fetchMaterials();
    } catch { showToast('교안 업로드 실패', 'error'); }
    finally { materialUploading.value = false; e.target.value = ''; }
};

const deleteMaterial = async (id) => {
    if (!confirm('교안을 삭제하시겠습니까?')) return;
    try { await api.delete(`/learning/materials/${id}/delete/`); await fetchMaterials(); } catch { showToast('삭제 실패', 'error'); }
};

// A4: 퀴즈 결과 프로젝터 공유 (전체화면)
const projectQuizResult = () => {
    const el = document.querySelector('.quiz-result-card');
    if (!el) { showToast('표시할 퀴즈 결과가 없습니다.', 'warning'); return; }
    if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
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

// ── RAG Re-indexing ──
const reindexing = ref(false);
const reindexResult = ref(null);

const reindexSession = async (sessionId) => {
    if (!confirm('이 세션의 학습 데이터를 재인덱싱하시겠습니까?')) return;
    reindexing.value = true;
    reindexResult.value = null;
    try {
        const { data } = await api.post('/learning/rag/index-session/', { session_id: sessionId });
        reindexResult.value = data;
        showToast(`✅ 재인덱싱 완료 (${data.indexed_count || 0}건 인덱싱됨, 'success')`);
    } catch (e) {
        showToast('재인덱싱 실패: ' + (e.response?.data?.error || e.message, 'error'));
    }
    reindexing.value = false;
};

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
        showToast('요약본을 불러올 수 없습니다.', 'warning');
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
            <!-- [3-1] 강의명 인라인 수정 -->
            <div v-if="isEditingTitle" style="display:flex; align-items:center; gap:8px;">
                <input v-model="editTitleValue" @keyup.enter="saveLectureTitle" @blur="saveLectureTitle" 
                    style="font-size:24px; font-weight:700; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.3); border-radius:8px; padding:6px 12px; color:white; outline:none; width:100%;" 
                    autofocus />
            </div>
            <h1 v-else style="cursor:pointer;" @dblclick="startEditTitle">
                {{ lectureTitle }}
                <span @click="startEditTitle" style="font-size:16px; cursor:pointer; opacity:0.5; margin-left:8px;" title="강의명 수정">✏️</span>
            </h1>
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
            <button 
                :class="['tab-btn', { active: activeTab === 'diagnostic' }]" 
                @click="switchTab('diagnostic')">
                📋 수준 진단
            </button>
            <button 
                :class="['tab-btn', { active: activeTab === 'analytics' }]" 
                @click="switchTab('analytics')">
                📈 학습 분석
            </button>
            <button 
                :class="['tab-btn', { active: activeTab === 'review' }]" 
                @click="switchTab('review')">
                🔄 복습 루트
            </button>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab 1: 진도 모니터링 (기존) -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'monitor'">
            <!-- 🚨 위험 학생 신호등 카드 -->
            <div class="traffic-light-cards" v-if="students.length > 0">
                <div class="tl-card tl-critical">
                    <span class="tl-icon">🔴</span>
                    <span class="tl-count">{{ students.filter(s => s.status === 'critical').length }}</span>
                    <span class="tl-label">위험 (30%↓)</span>
                </div>
                <div class="tl-card tl-warning">
                    <span class="tl-icon">🟡</span>
                    <span class="tl-count">{{ students.filter(s => s.status === 'warning').length }}</span>
                    <span class="tl-label">주의 (30~60%)</span>
                </div>
                <div class="tl-card tl-good">
                    <span class="tl-icon">🟢</span>
                    <span class="tl-count">{{ students.filter(s => s.status === 'good').length }}</span>
                    <span class="tl-label">양호 (60%↑)</span>
                </div>
            </div>

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
                                    {{ student.status === 'critical' ? '🔴 위험' : student.status === 'warning' ? '🟡 주의' : '🟢 양호' }}
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
                            <td colspan="4" style="text-align: center; color: #636b72; padding: 40px;">
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
                            <h3 style="display: flex; align-items: center; gap: 8px; flex: 1;">
                                <span style="white-space: nowrap;">{{week.week_number}}주차:</span>
                                <input :value="week.title" 
                                    @blur="e => updateWeekTitle(week, e.target.value)" 
                                    @keyup.enter="e => e.target.blur()"
                                    style="background:transparent; border:none; border-bottom:1px dashed rgba(0,0,0,0.2); font-size:inherit; font-weight:inherit; color:inherit; padding:2px 4px; outline:none; flex: 1; min-width: 0;" />
                            </h3>
                            <button class="btn-micro" @click="addObjective(week.id)">+ 목표 추가</button>
                        </div>
                        <div class="objective-list">
                            <div v-for="obj in week.objectives" :key="obj.id" class="obj-item">
                                <span>-</span>
                                <input :value="obj.content" 
                                    @blur="e => updateObjective(obj, e.target.value)" 
                                    @keyup.enter="e => e.target.blur()"
                                    style="background:transparent; border:none; border-bottom:1px dashed rgba(0,0,0,0.15); flex:1; font-size:14px; color:#333; padding:2px 4px; outline:none;" />
                                <span class="delete-x" @click="deleteObjective(obj.id)">×</span>
                            </div>
                        </div>
                        <!-- [3-2] 파일 첨부 UI -->
                        <div class="file-section" style="margin-top:8px; padding-top:8px; border-top:1px dashed rgba(0,0,0,0.1);">
                            <div v-if="week.file_url" style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                                <a :href="week.file_url" target="_blank" style="color:#4facfe; font-size:13px; text-decoration:underline;">📎 {{ week.file_name || '첨부파일' }}</a>
                            </div>
                            <label :for="'file-upload-' + week.id" class="btn-micro" style="cursor:pointer; font-size:12px;">
                                📤 {{ week.file_url ? '파일 교체' : '파일 첨부' }}
                            </label>
                            <input :id="'file-upload-' + week.id" type="file" style="display:none;" @change="uploadSyllabusFile(week.id, $event)" />
                        </div>
                    </div>
                </div>
                
                <div class="add-week-form">
                    <h3>+ 주차 추가</h3>
                    <input v-model="newWeekTitle" placeholder="주차 주제 (예: React 기초)" style="flex: 1;" />
                    <button style="white-space: nowrap;" @click="addWeek">추가</button>
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
                                <td colspan="4" style="text-align:center; color:#636b72; padding:40px;">
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
                        <Bar v-if="quizStudentChart" :data="quizStudentChart" :options="quizBarOptions" />
                    </div>
                    <!-- 점수 분포 -->
                    <div class="chart-container flex-1">
                        <h3 class="chart-title">점수 분포</h3>
                        <Doughnut v-if="quizDistributionChart" :data="quizDistributionChart" :options="doughnutOptions" />
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
                                <td colspan="4" style="text-align:center; color:#636b72; padding:40px;">
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
                                <button 
                                    v-if="rec.status === 'COMPLETED' && rec.session_id"
                                    class="btn-micro" 
                                    style="margin-left:4px;"
                                    @click="reindexSession(rec.session_id)"
                                    :disabled="reindexing"
                                >🔄 재인덱싱</button>
                                <span v-else-if="rec.status === 'FAILED'" class="error-hint" :title="rec.error_message">{{ rec.error_message?.substring(0, 30) }}...</span>
                            </td>
                        </tr>
                        <tr v-if="recordings.length === 0">
                            <td colspan="6" style="text-align:center; color:#636b72; padding:40px;">
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
                    <span v-if="liveSession.week_number" class="week-badge">📅 {{ liveSession.week_number }}차시</span>
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

                <!-- 🔌 수업 시작 전 라즈베리파이 설정 -->
                <div v-if="liveSession.status === 'WAITING'" class="rpi-panel rpi-setup">
                    <div class="rpi-header">
                        <span>🔌 DS-CNN 라즈베리파이 연결 (선택)</span>
                        <span :class="['rpi-dot', rpiConnected ? 'connected' : 'disconnected']">
                            {{ rpiConnected ? '🟢 연결됨' : '⚪ 미설정' }}
                        </span>
                    </div>
                    <p class="rpi-desc">라즈베리파이 IP를 입력하면 수업 시작 시 자동 연결됩니다. 비워두면 로컬 모드로 동작합니다.</p>
                    <div class="rpi-controls">
                        <input v-model="rpiHost" placeholder="IP (예: 172.16.206.43)" class="rpi-input" />
                        <input v-model="rpiPort" placeholder="포트" class="rpi-input rpi-port" />
                        <button class="rpi-btn rpi-btn-test" @click="connectRpi" :disabled="rpiConnecting">
                            {{ rpiConnecting ? '테스트 중...' : '연결' }}
                        </button>
                    </div>
                </div>

                <!-- 컨트롤 버튼 -->
                <div class="live-controls">
                    <button v-if="liveSession.status === 'WAITING'" class="btn-live-start" @click="startLiveSession">
                        ▶️ 수업 시작
                    </button>
                    <button v-if="liveSession.status === 'LIVE'" class="btn-live-end" @click="endLiveSession">
                        ⏹️ 세션 종료
                    </button>
                    <!-- STT+DSCNN 복합 모드 -->
                    <button v-if="liveSession.status === 'LIVE' && !sttActive && !dscnnOnlyActive"
                            class="btn-stt-dscnn-start" @click="startSTT">
                        🎙️ STT+DSCNN
                    </button>
                    <button v-if="liveSession.status === 'LIVE' && sttActive"
                            class="btn-stt-dscnn-stop" @click="stopSTT">
                        🔴 STT+DSCNN 인식 중...
                    </button>
                    <!-- DSCNN Only 모드 -->
                    <button v-if="liveSession.status === 'LIVE' && !dscnnOnlyActive && !sttActive"
                            class="btn-dscnn-start" @click="startDSCNNOnly">
                        🧠 DSCNN
                    </button>
                    <button v-if="liveSession.status === 'LIVE' && dscnnOnlyActive"
                            class="btn-dscnn-stop" @click="stopDSCNNOnly">
                        🟡 DSCNN 감지 중...
                    </button>
                </div>

                <!-- 현재 모드 표시 -->
                <div v-if="sttActive || dscnnOnlyActive" class="stt-preview">
                    <span class="stt-label" v-if="sttActive">🎙️ STT+DSCNN:</span>
                    <span class="stt-label" v-else>🧠 DSCNN Only:</span>
                    <span class="stt-text">{{ sttLastText }}</span>
                </div>

                <!-- 🔌 수업 중 라즈베리파이 상태 (연결됨일 때 간략 표시) -->
                <div v-if="liveSession && liveSession.status === 'LIVE'" class="rpi-status-mini">
                    <span>🔌 DS-CNN:</span>
                    <span :class="rpiConnected ? 'rpi-on' : 'rpi-off'">
                        {{ rpiConnected ? `🟢 ${rpiHost} 연결됨` : '로컬 모드' }}
                    </span>
                    <button v-if="!rpiConnected" class="rpi-btn-mini" @click="connectRpi">
                        재연결
                    </button>
                </div>

                <!-- AI 퀴즈 제안 스마트 팝업 -->
                <div v-if="quizSuggestion" class="quiz-suggestion-popup">
                    <div class="suggestion-header">
                        <span>🤖 AI 퀴즈 준비 완료!</span>
                        <span class="suggestion-hint">방금 설명하신 내용 기반</span>
                    </div>
                    <p class="suggestion-question">{{ quizSuggestion.question_text }}</p>
                    <div class="suggestion-options">
                        <span v-for="(opt, i) in quizSuggestion.options" :key="i" class="suggestion-opt" :class="{ correct: opt === quizSuggestion.correct_answer }">
                            {{ opt }}
                        </span>
                    </div>
                    <div class="suggestion-actions">
                        <button class="btn-approve" @click="approveQuizSuggestion">✅ 발동하기</button>
                        <button class="btn-dismiss" @click="dismissQuizSuggestion">✕ 무시</button>
                    </div>
                </div>

                <!-- 이해도 펄스 게이지 (LIVE일 때만) -->
                <div v-if="liveSession.status === 'LIVE' && pulseStats.total > 0" class="pulse-gauge-section" :class="{ warning: pulseWarning }">
                    <h3>📊 실시간 이해도</h3>
                    <div v-if="pulseWarning" class="pulse-alert">
                        ⚠️ 이해도가 50% 미만입니다! 보충 설명을 권장합니다.
                    </div>
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
                        <button class="btn-projector" @click="projectQuizResult" title="전체화면으로 공유">📺 프로젝터 공유</button>
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
                            <span v-if="p.level" class="level-badge" :class="'level-' + p.level">Lv{{ p.level }}</span>
                        </div>
                    </div>
                </div>
            </div>

                <!-- 실시간 Q&A 피드 (LIVE일 때만) -->
                <div v-if="liveSession && liveSession.status === 'LIVE'" class="qa-feed-section">
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

                <!-- Phase 2-1: Weak Zone 관리 패널 -->
                <div v-if="liveSession && liveSession.status === 'LIVE'" class="weak-zone-panel">
                    <h3>
                        ⚠️ Weak Zone
                        <span v-if="activeWeakZones.length > 0" class="wz-badge">{{ activeWeakZones.length }}</span>
                    </h3>
                    <div v-if="weakZones.length === 0" class="wz-empty">감지된 취약 구간이 없습니다.</div>
                    <div v-else class="wz-list">
                        <div v-for="wz in weakZones" :key="wz.id" class="wz-item" :class="'wz-status-' + wz.status.toLowerCase()">
                            <div class="wz-item-header">
                                <span class="wz-student">{{ wz.student_name }}</span>
                                <span class="wz-trigger-badge">{{ wz.trigger_type === 'QUIZ_WRONG' ? '📝 오답' : wz.trigger_type === 'PULSE_CONFUSED' ? '❓ 혼란' : '⚡ 복합' }}</span>
                                <span class="wz-status-tag">{{ wz.status }}</span>
                            </div>
                            <p v-if="wz.ai_suggested_content" class="wz-ai-preview">{{ wz.ai_suggested_content.slice(0, 100) }}...</p>
                            <div v-if="wz.status === 'DETECTED'" class="wz-item-actions">
                                <button class="wz-btn-push" @click="pushWeakZone(wz.id)">📤 AI 설명 전송</button>
                                <button class="wz-btn-dismiss" @click="dismissWeakZone(wz.id)">무시</button>
                            </div>
                        </div>
                    </div>
                </div>

            <!-- 교안 업로드 영역 (라이브 세션 생성 후 표시) -->
            <div v-if="liveSession" class="materials-section">
                <h3>📄 교안 관리</h3>
                <div class="material-upload-area">
                    <label class="upload-label">
                        <input type="file" accept=".pdf,.ppt,.pptx,.doc,.docx,.md,.markdown,.txt,.hwp" @change="uploadMaterial" hidden />
                        {{ materialUploading ? '업로드 중...' : '+ 교안 파일 업로드' }}
                    </label>
                </div>
                <div v-if="materials.length > 0" class="material-list">
                    <div v-for="m in materials" :key="m.id" class="material-card">
                        <div class="material-card-header">
                            <span class="material-type">{{ m.file_type }}</span>
                            <span class="material-title">{{ m.title }}</span>
                            <button class="btn-adaptive-gen" @click="generateAdaptive(m.id)" :disabled="adaptiveGenerating[m.id]" title="레벨별 AI 변형 생성">
                                {{ adaptiveGenerating[m.id] ? '⏳ 생성 중...' : '🤖 AI 변형 생성' }}
                            </button>
                            <button class="btn-material-delete" @click="deleteMaterial(m.id)" title="삭제">✕</button>
                        </div>

                        <!-- 레벨별 변형 카드 -->
                        <div v-if="adaptiveContents[m.id] && adaptiveContents[m.id].length > 0" class="adaptive-card-list">
                            <div v-for="ac in adaptiveContents[m.id]" :key="ac.id" 
                                 class="adaptive-card-item" :class="'ac-card-' + ac.status.toLowerCase()"
                                 @click="openAdaptivePreview(ac, m.id)">
                                <span class="ac-card-icon" :class="'ac-icon-' + ac.level">{{
                                    ac.level === 1 ? '🌱' : ac.level === 2 ? '📚' : '🚀'
                                }}</span>
                                <div class="ac-card-info">
                                    <span class="ac-card-level">{{
                                        ac.level === 1 ? 'Level 1 — 쉽게 이해하기' : ac.level === 2 ? 'Level 2 — 핵심 정리' : 'Level 3 — 심화 완성'
                                    }}</span>
                                    <span class="ac-card-status" :class="ac.status === 'APPROVED' ? 'st-approved' : 'st-draft'">
                                        {{ ac.status === 'APPROVED' ? '✅ 승인됨' : '📝 초안' }}
                                    </span>
                                </div>
                                <button v-if="ac.status === 'DRAFT'" class="ac-card-approve-btn" @click.stop="approveAdaptive(ac.id, m.id)" title="승인">✅ 승인</button>
                                <span class="ac-card-arrow">›</span>
                            </div>
                        </div>

                        <!-- 적응형 콘텐츠 미리보기 모달 -->
                        <div v-if="adaptivePreview && adaptivePreview.materialId === m.id" class="adaptive-preview-overlay" @click.self="closeAdaptivePreview">
                            <div class="adaptive-preview-modal">
                                <div class="apm-header">
                                    <span class="apm-level-badge" :class="'apm-level-' + adaptivePreview.level">Level {{ adaptivePreview.level }}</span>
                                    <span class="apm-title">{{ adaptivePreview.title }}</span>
                                    <span :class="['apm-status', adaptivePreview.status === 'APPROVED' ? 'apm-approved' : 'apm-draft']">
                                        {{ adaptivePreview.status === 'APPROVED' ? '✅ 승인됨' : '📝 초안' }}
                                    </span>
                                    <button class="apm-close" @click="closeAdaptivePreview">✕</button>
                                </div>
                                <div class="apm-content" v-html="renderMarkdown(adaptivePreview.content)"></div>
                                <div class="apm-actions">
                                    <button v-if="adaptivePreview.status === 'DRAFT'" class="btn-apm-approve" @click="approveAdaptive(adaptivePreview.acId, adaptivePreview.materialId)">✅ 승인하기</button>
                                    <button class="btn-apm-close" @click="closeAdaptivePreview">닫기</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <p v-else class="empty-text">아직 업로드된 교안이 없습니다.</p>
            </div>

            <!-- 세션 종료 후: 인사이트 리포트 -->
            <div v-if="liveSession && liveSession.status === 'ENDED'" class="insight-section">
                <h2 class="section-title">📊 인사이트 리포트</h2>
                <div v-if="!insightData" class="insight-loading">
                    <div class="insight-spinner"></div>
                    <p>AI가 수업 데이터를 분석 중입니다...</p>
                    <p class="insight-hint">통합 노트 + 인사이트 리포트가 자동 생성됩니다 (약 30초~1분)</p>
                </div>
                <div v-else>
                    <!-- 통계 카드 -->
                    <div v-if="insightData.stats" class="insight-stats-row">
                        <div class="insight-stat">
                            <span class="is-num">{{ insightData.stats.total_participants || 0 }}</span>
                            <span class="is-lbl">참가자</span>
                        </div>
                        <div class="insight-stat">
                            <span class="is-num">{{ insightData.stats.duration_minutes || 0 }}분</span>
                            <span class="is-lbl">수업 시간</span>
                        </div>
                        <div class="insight-stat">
                            <span class="is-num">{{ insightData.stats.understand_rate || 0 }}%</span>
                            <span class="is-lbl">이해도</span>
                        </div>
                        <div class="insight-stat">
                            <span class="is-num">{{ insightData.stats.quiz_count || 0 }}건</span>
                            <span class="is-lbl">퀴즈</span>
                        </div>
                    </div>

                    <!-- 교수자 인사이트 마크다운 -->
                    <div v-if="insightData.instructor_insight" class="insight-body" v-html="renderInsightMarkdown(insightData.instructor_insight)"></div>
                    <p v-else class="insight-pending">인사이트 리포트 생성 중...</p>

                    <!-- 교안 매핑 -->
                    <div class="material-link-section" v-if="insightData">
                        <h3>📎 교안 연결</h3>
                        <div v-if="materials.length > 0" class="material-checklist">
                            <label v-for="m in materials" :key="m.id" class="material-check-item">
                                <input type="checkbox" :value="m.id" v-model="selectedMaterialIds" />
                                <span class="material-type-badge">{{ m.file_type }}</span>
                                {{ m.title }}
                            </label>
                        </div>
                        <p v-else class="empty-text">업로드된 교안이 없습니다.</p>
                        <button v-if="materials.length > 0" class="btn-link-materials" @click="linkMaterials">📎 교안 연결 저장</button>
                    </div>

                    <!-- 승인 컨트롤 (인사이트 내용이 생성된 후에만 표시) -->
                    <div class="approve-section" v-if="insightData && insightData.instructor_insight && !insightData.is_approved">
                        <p class="approve-notice">⚠️ 아직 학생에게 노트가 공개되지 않았습니다. 검토 후 승인해주세요.</p>
                        <div class="approve-options">
                            <label class="approve-check">
                                <input type="checkbox" v-model="makePublicForAbsent" />
                                결석생에게도 공개 (결석 보충용)
                            </label>
                            <select v-model="noteDistributionScope" class="scope-select">
                                <option value="ALL">🌐 전체 공개</option>
                                <option value="ATTENDEES">✅ 출석자만</option>
                                <option value="ABSENT">📩 결석생만</option>
                                <option value="LEVEL_1">🌱 Level 1만</option>
                                <option value="LEVEL_2">🌿 Level 2만</option>
                                <option value="LEVEL_3">🌸 Level 3만</option>
                            </select>
                        </div>
                        <button class="btn-approve" @click="approveNote">✅ 노트 승인 → 학생 공개</button>
                    </div>
                    <div v-else-if="insightData && insightData.is_approved" class="approved-badge">
                        ✅ 승인 완료 — 학생에게 공개 중
                        <span v-if="insightData.is_public"> (결석생 포함)</span>
                    </div>

                    <!-- Phase 2-4: 형성평가 생성 -->
                    <div v-if="insightData && insightData.is_approved && liveSession" class="formative-section">
                        <button v-if="!formativeStatus" class="btn-formative-gen" @click="generateFormative" :disabled="formativeGenerating">
                            {{ formativeGenerating ? '⏳ 문항 생성 중...' : '📝 사후 형성평가 생성' }}
                        </button>
                        <div v-if="formativeStatus === 'READY'" class="formative-ready">
                            ✅ 형성평가 생성 완료 ({{ formativeCount }}문항) — 학생들이 풀 수 있습니다.
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- 📋 수준 진단 탭                         -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'diagnostic'" class="diagnostic-tab-content">
            <div v-if="diagnosticLoading" class="diagnostic-loading">
                <p>진단 분석 데이터를 불러오는 중...</p>
            </div>

            <div v-else-if="diagnosticData">
                <!-- 레벨 분포 -->
                <div class="diagnostic-section">
                    <h2 class="section-title">📊 학습자 수준 분포</h2>
                    <div class="level-dist-row">
                        <div class="donut-wrapper" v-if="levelDonutData">
                            <Doughnut :data="levelDonutData" :options="donutOptions" />
                            <div class="donut-center">
                                <span class="center-num">{{ diagnosticData.diagnosed_count }}</span>
                                <span class="center-lbl">명 진단</span>
                            </div>
                        </div>
                        <div class="level-cards">
                            <div class="level-card lv1">
                                <span class="lv-icon">🌱</span>
                                <span class="lv-count">{{ diagnosticData.level_distribution.level_1 }}명</span>
                                <span class="lv-pct">{{ diagnosticData.level_percentages.level_1 }}%</span>
                                <span class="lv-label">Level 1 · 초보</span>
                            </div>
                            <div class="level-card lv2">
                                <span class="lv-icon">🌿</span>
                                <span class="lv-count">{{ diagnosticData.level_distribution.level_2 }}명</span>
                                <span class="lv-pct">{{ diagnosticData.level_percentages.level_2 }}%</span>
                                <span class="lv-label">Level 2 · 기초</span>
                            </div>
                            <div class="level-card lv3">
                                <span class="lv-icon">🌳</span>
                                <span class="lv-count">{{ diagnosticData.level_distribution.level_3 }}명</span>
                                <span class="lv-pct">{{ diagnosticData.level_percentages.level_3 }}%</span>
                                <span class="lv-label">Level 3 · 심화</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 취약 역량 TOP 5 -->
                <div class="diagnostic-section">
                    <h2 class="section-title">🔥 공통 취약 역량 TOP 5</h2>
                    <p class="section-subtitle">가장 많은 학습자에게 부족한 역량 (강의 우선순위 참고)</p>
                    <div v-if="diagnosticData.weak_skills_top5.length > 0" class="weak-skills-list">
                        <div v-for="(skill, i) in diagnosticData.weak_skills_top5" :key="i" class="weak-skill-row">
                            <span class="ws-rank">{{ i + 1 }}</span>
                            <div class="ws-info">
                                <span class="ws-name">{{ skill.skill_name }}</span>
                                <span class="ws-category">{{ skill.category }}</span>
                            </div>
                            <div class="ws-bar-track">
                                <div class="ws-bar-fill" :style="{ width: skill.gap_rate + '%', background: weakSkillColor(skill.gap_rate) }"></div>
                            </div>
                            <span class="ws-rate" :style="{ color: weakSkillColor(skill.gap_rate) }">{{ skill.gap_rate }}%</span>
                        </div>
                    </div>
                    <p v-else class="empty-text">아직 취약 역량 분석 데이터가 없습니다.</p>
                </div>

                <div class="diagnostic-footer">
                    <p>총 수강생: {{ diagnosticData.enrolled_count }}명 | 진단 완료: {{ diagnosticData.diagnosed_count }}명</p>
                </div>
            </div>

            <div v-else class="diagnostic-empty">
                <p>진단 데이터가 없습니다. 학습자가 진단 테스트를 완료하면 여기에 표시됩니다.</p>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- 📈 학습 분석 탭                         -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'analytics'" class="analytics-tab-content">
            <!-- 서브탭 -->
            <div class="analytics-sub-tabs">
                <button v-for="st in ['overview','weak','ai','report']" :key="st"
                    :class="['sub-tab-btn', { active: analyticsSubTab === st }]"
                    @click="analyticsSubTab = st">
                    {{ {overview:'📊 현황판', weak:'🔍 취약구간', ai:'🤖 AI 제안', report:'📋 리포트'}[st] }}
                </button>
            </div>

            <!-- 로딩 -->
            <div v-if="analyticsLoading" class="analytics-loading">데이터를 불러오는 중...</div>

            <!-- 서브탭 1: 현황판 -->
            <div v-else-if="analyticsSubTab === 'overview'" class="an-panel">
                <div v-if="analyticsOverview">
                    <div class="an-summary-row">
                        <div class="an-stat-card"><span class="an-stat-value">{{ analyticsOverview.total_students }}</span><span class="an-stat-label">수강생</span></div>
                        <div class="an-stat-card"><span class="an-stat-value">{{ analyticsOverview.session_count }}</span><span class="an-stat-label">종료 세션</span></div>
                        <div class="an-stat-card"><span class="an-stat-value">{{ analyticsOverview.avg_attendance_rate }}%</span><span class="an-stat-label">평균 출석률</span></div>
                        <div class="an-stat-card"><span class="an-stat-value">{{ analyticsOverview.avg_quiz_accuracy }}%</span><span class="an-stat-label">평균 정답률</span></div>
                        <div class="an-stat-card"><span class="an-stat-value">{{ analyticsOverview.avg_progress_rate }}%</span><span class="an-stat-label">평균 진도율</span></div>
                    </div>

                    <!-- 레벨 분포 -->
                    <div class="an-chart-row" v-if="levelChartData">
                        <div class="an-chart-box">
                            <h3>레벨 분포</h3>
                            <Doughnut :data="levelChartData" :options="{ responsive: true, maintainAspectRatio: false }" style="max-height: 200px;" />
                        </div>
                    </div>

                    <!-- 위험군 -->
                    <div v-if="analyticsOverview.at_risk_students && analyticsOverview.at_risk_students.length > 0" class="an-risk-section">
                        <h3>⚠️ 위험군 학습자 ({{ analyticsOverview.at_risk_students.length }}명)</h3>
                        <table class="an-risk-table">
                            <thead><tr><th>학생</th><th>레벨</th><th>위험 사유</th><th>결석 노트</th><th>형성평가</th><th>조치</th></tr></thead>
                            <tbody>
                                <tr v-for="s in analyticsOverview.at_risk_students" :key="s.id" class="an-risk-row">
                                    <td>{{ s.username }}</td>
                                    <td><span class="an-level-tag">{{ s.level }}</span></td>
                                    <td><span v-for="r in s.risk_reasons" :key="r" class="an-risk-tag">{{ r }}</span></td>
                                    <td>{{ s.absent_note_viewed ? '✅' : '❌' }}</td>
                                    <td>{{ s.formative_completed ? '✅' : '❌' }}</td>
                                    <td><button class="an-msg-btn" @click="openMessage(s)">📩</button></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div v-else class="an-empty">위험군 학습자가 없습니다 👍</div>
                </div>
                <div v-else class="an-empty">{{ analyticsOverview?.message || '데이터를 불러올 수 없습니다.' }}</div>
            </div>

            <!-- 서브탭 2: 취약구간 -->
            <div v-else-if="analyticsSubTab === 'weak'" class="an-panel">
                <div v-if="weakInsights && weakInsights.insights && weakInsights.insights.length > 0">
                    <h3>🔍 취약 구간 랭킹</h3>
                    <table class="an-weak-table">
                        <thead><tr><th>#</th><th>개념</th><th>세션</th><th>오답률</th><th>영향 학생</th><th>출처</th></tr></thead>
                        <tbody>
                            <tr v-for="ins in weakInsights.insights" :key="ins.rank">
                                <td class="an-rank">{{ ins.rank }}</td>
                                <td>{{ ins.concept }}</td>
                                <td>{{ ins.session_title }}</td>
                                <td>
                                    <div class="an-bar-bg"><div class="an-bar-fill" :style="{ width: ins.wrong_rate + '%' }"></div></div>
                                    <span>{{ ins.wrong_rate }}%</span>
                                </td>
                                <td>{{ ins.affected_count }}/{{ ins.total_students }}명</td>
                                <td><span class="an-source-tag">{{ ins.source }}</span></td>
                            </tr>
                        </tbody>
                    </table>

                    <!-- 차시별 비교 -->
                    <div v-if="sessionComparisonChart" class="an-chart-box" style="margin-top: 20px;">
                        <h3>차시별 비교 추이</h3>
                        <Bar :data="sessionComparisonChart" :options="{ responsive: true, maintainAspectRatio: false }" style="max-height: 250px;" />
                    </div>
                </div>
                <div v-else class="an-empty">아직 취약 구간 데이터가 없습니다.</div>
            </div>

            <!-- 서브탭 3: AI 제안 -->
            <div v-else-if="analyticsSubTab === 'ai'" class="an-panel">
                <div v-if="aiSuggestions && aiSuggestions.pending_suggestions && aiSuggestions.pending_suggestions.length > 0">
                    <h3>🤖 AI 제안 ({{ aiSuggestions.pending_count }}건 대기)</h3>
                    <div v-for="sg in aiSuggestions.pending_suggestions" :key="sg.type + sg.id" class="an-suggestion-card">
                        <div class="an-sg-header">
                            <span class="an-sg-type">{{ {REVIEW_ROUTE:'📚',WEAK_ZONE:'⚠️',ADAPTIVE_CONTENT:'📖'}[sg.type] }} {{ sg.type }}</span>
                            <span class="an-sg-student" v-if="sg.student_name">{{ sg.student_name }}</span>
                        </div>
                        <p class="an-sg-detail">{{ sg.detail }}</p>
                        <div class="an-sg-actions">
                            <button class="an-btn-approve" @click="handleSuggestion(sg.type, sg.id, 'APPROVE')">✅ 승인</button>
                            <button class="an-btn-reject" @click="handleSuggestion(sg.type, sg.id, 'REJECT')">❌ 거부</button>
                        </div>
                    </div>
                </div>
                <div v-else class="an-empty">대기 중인 AI 제안이 없습니다.</div>

                <div v-if="aiSuggestions && aiSuggestions.recent_decisions && aiSuggestions.recent_decisions.length > 0" style="margin-top: 20px;">
                    <h4>최근 판단 이력</h4>
                    <div v-for="(d, i) in aiSuggestions.recent_decisions" :key="i" class="an-decision-item">
                        <span>{{ d.type }} — {{ d.action }}</span>
                        <span class="an-decision-detail">{{ d.detail }}</span>
                    </div>
                </div>
            </div>

            <!-- 서브탭 4: 리포트 -->
            <div v-else-if="analyticsSubTab === 'report'" class="an-panel">
                <div v-if="qualityReport && qualityReport.sessions && qualityReport.sessions.length > 0">
                    <h3>📋 강의 품질 리포트</h3>
                    <table class="an-report-table">
                        <thead><tr><th>차시</th><th>날짜</th><th>참여</th><th>이해율</th><th>퀴즈</th><th>체크포인트</th><th>형성평가</th><th>WZ</th></tr></thead>
                        <tbody>
                            <tr v-for="s in qualityReport.sessions" :key="s.id">
                                <td>{{ s.title }}</td>
                                <td>{{ s.date }}</td>
                                <td>{{ s.participants }}명</td>
                                <td>{{ s.metrics.understand_rate }}%</td>
                                <td>{{ s.metrics.quiz_accuracy }}%</td>
                                <td>{{ s.metrics.checkpoint_pass_rate }}%</td>
                                <td>{{ s.metrics.formative_completion_rate }}%</td>
                                <td>{{ s.metrics.weak_zone_count }}</td>
                            </tr>
                        </tbody>
                    </table>

                    <!-- 재분류 제안 -->
                    <div v-if="qualityReport.level_redistribution && qualityReport.level_redistribution.changes && qualityReport.level_redistribution.changes.length > 0" class="an-redistribution">
                        <h3>🔄 레벨 재분류 제안</h3>
                        <div v-for="c in qualityReport.level_redistribution.changes" :key="c.student_id" class="an-reclass-item">
                            <span>{{ c.student_name }}</span>
                            <span class="an-level-tag">{{ c.from }}</span> → <span class="an-level-tag">{{ c.to }}</span>
                            <span class="an-reclass-reason">{{ c.reason }}</span>
                        </div>
                        <button class="an-btn-apply" @click="applyRedistribution">일괄 승인</button>
                    </div>

                    <!-- 그룹 메시지 -->
                    <div class="an-group-msg" style="margin-top: 20px;">
                        <h3>📩 그룹 메시지 발송</h3>
                        <select v-model="groupMsgLevel" class="an-select">
                            <option :value="0">전체</option>
                            <option :value="1">Level 1</option>
                            <option :value="2">Level 2</option>
                            <option :value="3">Level 3</option>
                        </select>
                        <input v-model="groupMsgTitle" placeholder="제목" class="an-input" />
                        <textarea v-model="groupMsgContent" placeholder="내용" class="an-textarea" rows="3"></textarea>
                        <button class="an-btn-send" @click="sendGroupMessage" :disabled="!groupMsgTitle || !groupMsgContent">발송</button>
                    </div>
                </div>
                <div v-else class="an-empty">{{ qualityReport?.message || '아직 종료된 강의가 없습니다.' }}</div>
            </div>
        </div>

        <!-- 메시지 발송 모달 -->
        <div v-if="showMsgModal" class="an-modal-overlay" @click.self="showMsgModal = false">
            <div class="an-modal">
                <h3>📩 {{ msgTarget?.username }}에게 메시지</h3>
                <input v-model="msgTitle" placeholder="제목" class="an-input" />
                <textarea v-model="msgContent" placeholder="내용" class="an-textarea" rows="4"></textarea>
                <div class="an-modal-actions">
                    <button class="an-btn-send" @click="sendDirectMessage" :disabled="!msgTitle || !msgContent">발송</button>
                    <button class="an-btn-cancel" @click="showMsgModal = false">취소</button>
                </div>
            </div>
        </div>

        <!-- ══════════════════════════════════════ -->
        <!-- Tab: 복습 루트 관리 -->
        <!-- ══════════════════════════════════════ -->
        <div v-if="activeTab === 'review'" class="review-tab-content">
            <h2>🔄 복습 루트 승인 관리</h2>
            <p style="color:#636b72;font-size:14px;margin-bottom:16px;">AI가 생성한 복습 루트를 검토하고 학생에게 배포할 수 있습니다.</p>

            <div v-if="reviewRoutesLoading" class="loading-state"><div class="spinner"></div>로딩 중...</div>

            <div v-else-if="pendingReviewRoutes.length === 0" class="empty-state">
                <p>🎉 승인 대기 중인 복습 루트가 없습니다.</p>
            </div>

            <div v-else class="review-list">
                <div v-for="route in pendingReviewRoutes" :key="route.id" class="review-card">
                    <div class="review-header">
                        <div>
                            <h3>{{ route.title || '복습 루트 #' + route.id }}</h3>
                            <span class="review-meta">
                                👤 {{ route.student_name || '학생' }} · ⏱️ {{ route.estimated_minutes || '?' }}분
                            </span>
                        </div>
                        <span class="review-status pending">대기</span>
                    </div>

                    <div class="review-items" v-if="route.items?.length">
                        <div v-for="(item, idx) in route.items" :key="idx" class="review-item">
                            <span class="ri-num">{{ idx + 1 }}</span>
                            <span>{{ item.title || item.content }}</span>
                        </div>
                    </div>

                    <div class="review-actions">
                        <button class="btn-approve" @click="approveReviewRoute(route.id)">✅ 승인</button>
                        <button class="btn-edit-route" @click="editReviewRouteTitle(route.id)">✏️ 수정</button>
                    </div>
                </div>
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
    background: transparent; color: #636b72; font-size: 14px; font-weight: 600;
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
.card-label { font-size: 13px; color: #636b72; }

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

/* 🚨 위험 학생 신호등 */
.traffic-light-cards { display: flex; gap: 16px; margin-bottom: 24px; }
.tl-card {
    flex: 1; display: flex; align-items: center; gap: 12px;
    padding: 16px 20px; border-radius: 12px; border: 1px solid #eee;
    background: white; box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.tl-icon { font-size: 28px; }
.tl-count { font-size: 32px; font-weight: 800; }
.tl-label { font-size: 13px; color: #636b72; }
.tl-critical { border-left: 4px solid #ef4444; }
.tl-critical .tl-count { color: #dc2626; }
.tl-warning { border-left: 4px solid #f59e0b; }
.tl-warning .tl-count { color: #d97706; }
.tl-good { border-left: 4px solid #22c55e; }
.tl-good .tl-count { color: #16a34a; }
.table-container { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #eee; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 15px; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { background: #f8f9fa; font-weight: 600; font-size: 13px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }

/* ── Student Info ── */
.student-name { font-weight: 600; font-size: 14px; margin-bottom: 2px; color: #333; }
.student-email { font-size: 12px; color: #6e6e6e; }

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
.loading-state { text-align: center; padding: 60px; color: #636b72; }
.spinner {
    width: 40px; height: 40px; margin: 0 auto 16px;
    border: 4px solid #eee; border-top-color: #4facfe;
    border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { text-align: center; padding: 60px; color: #6e6e6e; }

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
.upload-hint { font-size: 13px; color: #6e6e6e; }
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
    background: none; border: none; font-size: 28px; color: #6e6e6e;
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
.create-card .sub { color: #636b72; font-size: 14px; margin-bottom: 24px; }
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
.code-label { font-size: 12px; color: #636b72; text-transform: uppercase; letter-spacing: 2px; }
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

/* STT 마이크 */
.btn-stt-start {
    padding: 14px; background: #6366f1; color: white; border: none;
    border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-stt-start:hover { background: #4f46e5; }
.btn-kws-only {
    padding: 14px; background: #059669; color: white; border: none;
    border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-kws-only:hover { background: #047857; }
.kws-only-mode { background: #ecfdf5 !important; border: 1px solid #6ee7b7; }
.btn-stt-stop {
    padding: 14px; background: #dc2626; color: white; border: none;
    border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
    animation: pulse-warn 1.5s infinite;
}

.stt-preview {
    padding: 8px 12px; background: #f5f3ff; border-radius: 8px; margin-bottom: 16px;
    font-size: 12px; color: #6366f1;
}
.stt-label { font-weight: 600; margin-right: 6px; }
.stt-text { color: #333; }

/* KWS 감지 바 */
.kws-detection-bar {
    padding: 10px 14px; background: linear-gradient(135deg, #fef3c7, #fde68a);
    border-radius: 8px; margin-bottom: 12px;
    font-size: 13px; font-weight: 600; color: #92400e;
    animation: pulse-warn 2s infinite;
}

/* 라즈베리파이 패널 */
.rpi-panel {
    padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; margin-bottom: 16px;
}
.rpi-header {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 8px;
}
.rpi-dot.connected { color: #16a34a; font-size: 12px; }
.rpi-dot.disconnected { color: #dc2626; font-size: 12px; }
.rpi-controls { display: flex; gap: 8px; align-items: center; }
.rpi-input {
    flex: 1; padding: 8px 10px; border: 1px solid #cbd5e1;
    border-radius: 6px; font-size: 13px; outline: none;
}
.rpi-input:focus { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,.15); }
.rpi-input.rpi-port { max-width: 70px; }
.rpi-btn {
    padding: 8px 16px; background: #6366f1; color: white; border: none;
    border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;
    white-space: nowrap;
}
.rpi-btn:hover { background: #4f46e5; }
.rpi-btn:disabled { background: #94a3b8; cursor: wait; }

/* 수업 전 RPI 설정 */
.rpi-setup { background: #f0fdf4; border-color: #bbf7d0; }
.rpi-desc { font-size: 12px; color: #6b7280; margin: 0 0 10px 0; line-height: 1.5; }
.rpi-btn-test { background: #059669; }
.rpi-btn-test:hover { background: #047857; }

/* 수업 중 미니 상태 */
.rpi-status-mini {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; background: #f8fafc; border-radius: 8px;
    margin-bottom: 12px; font-size: 12px; color: #64748b;
}
.rpi-on { color: #16a34a; font-weight: 600; }
.rpi-off { color: #94a3b8; }
.rpi-btn-mini {
    padding: 4px 10px; background: #6366f1; color: white; border: none;
    border-radius: 4px; font-size: 11px; cursor: pointer;
}

/* STT+DSCNN 복합 모드 버튼 */
.btn-stt-dscnn-start {
    padding: 8px 14px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white; border: none; border-radius: 8px;
    font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.btn-stt-dscnn-start:hover { filter: brightness(1.1); }
.btn-stt-dscnn-stop {
    padding: 8px 14px; background: #ef4444; color: white; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
    animation: pulse-warn 2s infinite; white-space: nowrap;
}

/* DSCNN Only 모드 버튼 */
.btn-dscnn-start {
    padding: 8px 14px; background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white; border: none; border-radius: 8px;
    font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.btn-dscnn-start:hover { filter: brightness(1.1); }
.btn-dscnn-stop {
    padding: 8px 14px; background: #eab308; color: white; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
    animation: pulse-warn 2s infinite; white-space: nowrap;
}

/* 퀴즈 제안 스마트 팝업 */
.quiz-suggestion-popup {
    padding: 16px; background: linear-gradient(135deg, #fffbeb, #fef3c7);
    border: 2px solid #f59e0b; border-radius: 12px; margin-bottom: 20px;
    animation: slideDown 0.3s ease;
}
@keyframes slideDown { from { transform: translateY(-10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.suggestion-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.suggestion-header span:first-child { font-size: 15px; font-weight: 700; color: #92400e; }
.suggestion-hint { font-size: 11px; color: #b45309; }

.suggestion-question { font-size: 14px; font-weight: 600; color: #333; margin: 8px 0 12px; }

.suggestion-options { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.suggestion-opt {
    padding: 4px 10px; border-radius: 6px; font-size: 12px;
    background: white; border: 1px solid #e5e7eb; color: #555;
}
.suggestion-opt.correct { background: #dcfce7; border-color: #22c55e; color: #166534; font-weight: 600; }

.suggestion-actions { display: flex; gap: 8px; }
.btn-approve {
    flex: 1; padding: 10px; background: #22c55e; color: white; border: none;
    border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-approve:hover { background: #16a34a; }
.btn-dismiss {
    padding: 10px 16px; background: #f3f4f6; color: #636b72; border: none;
    border-radius: 8px; font-size: 14px; cursor: pointer;
}
.btn-dismiss:hover { background: #e5e7eb; }

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

/* A1: 학생 레벨 배지 */
.level-badge {
    font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 8px;
    margin-left: 4px; color: white;
}
.level-badge.level-1 { background: #f59e0b; }
.level-badge.level-2 { background: #3b82f6; }
.level-badge.level-3 { background: #8b5cf6; }

/* A2: 차시 배지 */
.week-badge {
    font-size: 12px; font-weight: 600; color: #6366f1;
    background: #eef2ff; padding: 3px 10px; border-radius: 12px;
}

/* A4: 프로젝터 공유 버튼 */
.btn-projector {
    margin-top: 8px; padding: 6px 14px; background: #1e1b4b; color: white;
    border: none; border-radius: 6px; font-size: 12px; cursor: pointer;
    transition: background 0.2s;
}
.btn-projector:hover { background: #312e81; }
.quiz-result-card:fullscreen {
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    background: #0f172a; color: white; padding: 40px; font-size: 24px;
}
.quiz-result-card:fullscreen .quiz-q { font-size: 28px; }
.quiz-result-card:fullscreen .quiz-accuracy { font-size: 40px; font-weight: 800; }
.quiz-result-card:fullscreen .quiz-meta { font-size: 20px; }
.quiz-result-card:fullscreen .btn-projector { display: none; }

/* B4: 배포 범위 선택 */
.scope-select {
    margin-left: 12px; padding: 6px 10px; border: 1px solid #d1d5db;
    border-radius: 8px; font-size: 13px; background: white; cursor: pointer;
}

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
.material-list { display: flex; flex-direction: column; gap: 12px; }
.material-card {
    background: #fff; border-radius: 12px; border: 1px solid #e5e7eb;
    overflow: hidden; transition: box-shadow 0.2s;
}
.material-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.material-card-header {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px; background: #fafafa; border-bottom: 1px solid #f0f0f0;
}
.material-type {
    background: #dbeafe; color: #1e40af; padding: 3px 10px;
    border-radius: 6px; font-size: 11px; font-weight: 700; white-space: nowrap;
}
.material-title { flex: 1; font-size: 14px; font-weight: 500; color: #333; }
.btn-adaptive-gen {
    padding: 6px 14px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #fff; border: none; border-radius: 8px; font-size: 12px;
    font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s;
}
.btn-adaptive-gen:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.3); }
.btn-adaptive-gen:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.btn-material-delete {
    background: none; border: none; color: #bbb; font-size: 16px;
    cursor: pointer; padding: 4px 6px; border-radius: 4px; transition: all 0.15s;
}
.btn-material-delete:hover { color: #ef4444; background: #fef2f2; }

/* 레벨별 변형 카드 */
.adaptive-card-list {
    display: flex; flex-direction: column;
}
.adaptive-card-item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px; cursor: pointer;
    border-bottom: 1px solid #f3f4f6; transition: background 0.15s;
    min-height: 48px;
}
.adaptive-card-item:last-child { border-bottom: none; }
.adaptive-card-item:hover { background: #f5f3ff; }
.ac-card-icon { font-size: 20px; width: 32px; text-align: center; flex-shrink: 0; }
.ac-card-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.ac-card-level { font-size: 13px; font-weight: 600; color: #333; }
.ac-card-status { font-size: 11px; }
.st-approved { color: #059669; }
.st-draft { color: #b45309; }
.ac-card-approve-btn {
    padding: 6px 14px; background: #10b981; color: #fff; border: none;
    border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
    transition: all 0.15s; white-space: nowrap;
}
.ac-card-approve-btn:hover { background: #059669; transform: translateY(-1px); }
.ac-card-arrow { font-size: 20px; color: #ccc; font-weight: 300; flex-shrink: 0; }
.ac-card-draft { }
.ac-card-approved { background: #f0fdf4; }
.ac-card-rejected { opacity: 0.5; }

.empty-text { color: #aaa; font-size: 13px; }

/* ── Pulse Gauge ── */
.pulse-gauge-section { margin-bottom: 24px; padding: 16px; background: #fafafa; border-radius: 12px; transition: all 0.3s; }
.pulse-gauge-section.warning { background: #fef2f2; border: 2px solid #ef4444; box-shadow: 0 0 12px rgba(239,68,68,0.2); }
.pulse-gauge-section h3 { font-size: 14px; margin: 0 0 12px; color: #333; }
.pulse-gauge-section.empty { text-align: center; }
.pulse-waiting { color: #aaa; font-size: 13px; margin: 0; }
.pulse-alert {
    padding: 8px 12px; background: #ef4444; color: white; border-radius: 8px;
    font-size: 13px; font-weight: 600; margin-bottom: 12px; text-align: center;
    animation: pulse-warn 1.5s infinite;
}
@keyframes pulse-warn { 0%,100% { opacity:1; } 50% { opacity:0.7; } }

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
.quiz-meta { font-size: 11px; color: #636b72; margin: 4px 0 0; }

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
.qa-votes { font-size: 12px; color: #636b72; }
.qa-question { font-size: 13px; color: #333; margin: 0 0 8px; font-weight: 500; }

.qa-ai-ref {
    padding: 8px; background: #eff6ff; border-radius: 6px; margin-bottom: 8px;
}
.ai-tag { font-size: 10px; color: #3b82f6; font-weight: 600; }
.qa-ai-ref p { font-size: 11px; color: #636b72; margin: 4px 0 0; }

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

/* ── Diagnostic Tab ── */
.diagnostic-tab-content { padding: 20px 0; }
.diagnostic-loading { text-align: center; padding: 40px 0; color: #aaa; }
.diagnostic-empty { text-align: center; padding: 40px 0; color: #aaa; }
.diagnostic-section { margin-bottom: 32px; }
.section-subtitle { font-size: 13px; color: #636b72; margin: -12px 0 16px; }

.level-dist-row { display: flex; gap: 32px; align-items: center; }
.donut-wrapper { position: relative; width: 220px; height: 220px; flex-shrink: 0; }
.donut-center {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    text-align: center; pointer-events: none;
}
.center-num { display: block; font-size: 28px; font-weight: 800; color: #333; }
.center-lbl { font-size: 11px; color: #aaa; }

.level-cards { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.level-card {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px; border-radius: 10px; background: #fafafa; border: 1px solid #eee;
}
.level-card.lv1 { border-left: 4px solid #f59e0b; }
.level-card.lv2 { border-left: 4px solid #3b82f6; }
.level-card.lv3 { border-left: 4px solid #8b5cf6; }
.lv-icon { font-size: 24px; }
.lv-count { font-size: 20px; font-weight: 700; color: #333; }
.lv-pct { font-size: 14px; color: #636b72; margin-left: auto; }
.lv-label { display: none; }

.weak-skills-list { display: flex; flex-direction: column; gap: 10px; }
.weak-skill-row {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px; background: #fafafa; border-radius: 10px;
}
.ws-rank {
    width: 28px; height: 28px; border-radius: 50%; background: #e5e7eb;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px; color: #555; flex-shrink: 0;
}
.ws-info { min-width: 140px; }
.ws-name { display: block; font-size: 13px; font-weight: 600; color: #333; }
.ws-category { font-size: 10px; color: #aaa; }
.ws-bar-track { flex: 1; height: 10px; background: #e5e7eb; border-radius: 5px; overflow: hidden; }
.ws-bar-fill { height: 100%; border-radius: 5px; transition: width 0.5s; }
.ws-rate { font-size: 14px; font-weight: 700; width: 50px; text-align: right; flex-shrink: 0; }

.diagnostic-footer { text-align: center; padding: 12px; color: #aaa; font-size: 12px; border-top: 1px solid #eee; }

/* ── Insight Report ── */
.insight-section { margin-top: 28px; padding: 20px; background: #fafafa; border-radius: 12px; border: 1px solid #eee; }
.insight-loading { text-align: center; padding: 40px 0; color: #636b72; }
.insight-spinner {
    width: 36px; height: 36px; border: 3px solid #eee; border-top-color: #3b82f6;
    border-radius: 50%; animation: spin-insight 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin-insight { to { transform: rotate(360deg); } }
.insight-hint { font-size: 12px; color: #aaa; }
.insight-pending { color: #aaa; font-style: italic; text-align: center; padding: 20px; }

.insight-stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.insight-stat { text-align: center; padding: 14px; background: white; border: 1px solid #e5e7eb; border-radius: 10px; }
.is-num { display: block; font-size: 22px; font-weight: 800; color: #333; }
.is-lbl { font-size: 11px; color: #aaa; }

.insight-body {
    padding: 16px; background: white; border-radius: 10px; border: 1px solid #e5e7eb;
    font-size: 13px; line-height: 1.8; color: #333;
}
.insight-body h2 { font-size: 18px; margin: 16px 0 8px; color: #1e3a5f; }
.insight-body h3 { font-size: 15px; margin: 12px 0 6px; color: #334155; }
.insight-body h4 { font-size: 14px; margin: 10px 0 4px; color: #475569; }
.insight-body li { margin-left: 16px; list-style: disc; margin-bottom: 4px; }
.insight-body strong { color: #1e40af; }

/* ── Step E: Approve & Materials ── */
.material-link-section { margin-top: 20px; padding: 16px; background: #f9fafb; border-radius: 10px; border: 1px solid #e5e7eb; }
.material-link-section h3 { font-size: 14px; margin: 0 0 10px; color: #333; }
.material-checklist { display: flex; flex-direction: column; gap: 6px; }
.material-check-item { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; padding: 6px 0; }
.material-check-item input[type=checkbox] { width: 16px; height: 16px; }
.material-type-badge { font-size: 10px; padding: 2px 6px; background: #dbeafe; color: #2563eb; border-radius: 4px; font-weight: 600; }
.btn-link-materials {
    margin-top: 10px; padding: 8px 16px; background: #6366f1; color: white; border: none;
    border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
}
.btn-link-materials:hover { background: #4f46e5; }

.approve-section {
    margin-top: 20px; padding: 16px; background: #fffbeb; border: 1px solid #fde68a;
    border-radius: 10px;
}
.approve-notice { color: #92400e; font-size: 13px; margin: 0 0 10px; font-weight: 500; }
.approve-options { margin-bottom: 12px; }
.approve-check { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.approve-check input[type=checkbox] { width: 16px; height: 16px; }
.btn-approve {
    padding: 10px 24px; background: #22c55e; color: white; border: none;
    border-radius: 8px; font-size: 14px; font-weight: 700; cursor: pointer;
}
.btn-approve:hover { background: #16a34a; }

.approved-badge {
    margin-top: 16px; padding: 12px; background: #f0fdf4; border: 1px solid #bbf7d0;
    border-radius: 8px; color: #16a34a; font-weight: 600; font-size: 14px; text-align: center;
}

/* ── Phase 2-1: Weak Zone Panel ── */
.weak-zone-panel { margin-top: 20px; padding: 16px; background: rgba(245,158,11,0.05); border: 1px solid rgba(245,158,11,0.2); border-radius: 12px; }
.weak-zone-panel h3 { font-size: 16px; color: #f59e0b; margin: 0 0 10px; display: flex; align-items: center; gap: 8px; }
.wz-badge { background: #ef4444; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 700; }
.wz-empty { color: #9ca3af; font-size: 13px; text-align: center; padding: 12px; }
.wz-list { display: flex; flex-direction: column; gap: 10px; }
.wz-item { padding: 12px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }
.wz-item-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.wz-student { font-weight: 600; font-size: 13px; color: #374151; }
.wz-trigger-badge { font-size: 11px; padding: 2px 8px; background: #fef3c7; color: #92400e; border-radius: 4px; }
.wz-status-tag { font-size: 10px; color: #9ca3af; margin-left: auto; }
.wz-ai-preview { font-size: 12px; color: #6b7280; margin: 4px 0; line-height: 1.5; }
.wz-item-actions { display: flex; gap: 8px; margin-top: 8px; }
.wz-btn-push { padding: 6px 12px; background: #f59e0b; color: #fff; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; }
.wz-btn-push:hover { background: #d97706; }
.wz-btn-dismiss { padding: 6px 12px; background: #f3f4f6; color: #6b7280; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 12px; cursor: pointer; }
.wz-btn-dismiss:hover { background: #e5e7eb; }
.wz-status-material_pushed { opacity: 0.7; }
.wz-status-dismissed { opacity: 0.5; }
.wz-status-resolved { opacity: 0.5; }

/* ── Phase 2-4: Formative Assessment ── */
.formative-section { margin-top: 16px; padding: 12px; background: rgba(99,102,241,0.05); border: 1px solid rgba(99,102,241,0.2); border-radius: 10px; }
.btn-formative-gen { width: 100%; padding: 12px; background: #6366f1; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-formative-gen:hover:not(:disabled) { background: #4f46e5; }
.btn-formative-gen:disabled { opacity: 0.6; cursor: not-allowed; }
.formative-ready { padding: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; color: #16a34a; font-size: 13px; font-weight: 600; text-align: center; }

/* ── Phase 2-2: Adaptive Content (카드형 스타일은 위에서 정의됨) ── */

/* 적응형 콘텐츠 미리보기 모달 */
.adaptive-preview-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
    backdrop-filter: blur(3px);
}
.adaptive-preview-modal {
    background: #fff; border-radius: 16px; width: 90%; max-width: 700px;
    max-height: 80vh; display: flex; flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.apm-header {
    display: flex; align-items: center; gap: 10px; padding: 16px 20px;
    border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.apm-level-badge {
    padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; color: #fff;
}
.apm-level-1 { background: #10b981; }
.apm-level-2 { background: #3b82f6; }
.apm-level-3 { background: #8b5cf6; }
.apm-title { flex: 1; font-size: 14px; font-weight: 600; color: #333; }
.apm-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.apm-approved { background: #d1fae5; color: #065f46; }
.apm-draft { background: #fef3c7; color: #92400e; }
.apm-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #6e6e6e; padding: 4px; }
.apm-close:hover { color: #333; }
.apm-content {
    padding: 20px; overflow-y: auto; flex: 1;
    font-size: 14px; line-height: 1.7; color: #333;
}
.apm-content h1 { font-size: 20px; margin: 0 0 12px; color: #1a1a2e; border-bottom: 2px solid #4facfe; padding-bottom: 6px; }
.apm-content h2 { font-size: 17px; margin: 20px 0 8px; color: #333; }
.apm-content h3 { font-size: 15px; margin: 16px 0 6px; color: #555; }
.apm-content ul, .apm-content ol { padding-left: 20px; }
.apm-content li { margin: 4px 0; }
.apm-content pre { background: #f3f4f6; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
.apm-content code { background: #e5e7eb; padding: 1px 4px; border-radius: 3px; font-size: 13px; }
.apm-content strong { color: #1e40af; }
.apm-content table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.apm-content th, .apm-content td { border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; font-size: 13px; }
.apm-content th { background: #f9fafb; font-weight: 600; }
.apm-actions {
    display: flex; justify-content: flex-end; gap: 8px; padding: 12px 20px;
    border-top: 1px solid #e5e7eb; flex-shrink: 0;
}
.btn-apm-approve {
    padding: 8px 20px; background: #10b981; color: #fff; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-apm-approve:hover { background: #059669; }
.btn-apm-close {
    padding: 8px 20px; background: #f3f4f6; color: #636b72; border: none;
    border-radius: 8px; font-size: 13px; cursor: pointer;
}
.btn-apm-close:hover { background: #e5e7eb; }
.ac-draft { background: #fef3c7; color: #92400e; }
.ac-approved { background: #d1fae5; color: #065f46; }
.ac-rejected { background: #fee2e2; color: #991b1b; opacity: 0.6; }
.ac-generating { background: #e5e7eb; color: #6b7280; }
.ac-approve-btn { background: #22c55e; color: #fff; border: none; border-radius: 3px; font-size: 9px; padding: 1px 4px; cursor: pointer; }
.ac-approve-btn:hover { background: #16a34a; }

/* ── Phase 3: Analytics Tab ── */
.analytics-tab-content { padding: 20px 0; }
.analytics-sub-tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.sub-tab-btn { padding: 8px 16px; border: 1px solid #e0e0e0; border-radius: 20px; background: #fff; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.sub-tab-btn.active { background: #1565c0; color: white; border-color: #1565c0; }
.sub-tab-btn:hover:not(.active) { background: #f5f5f5; }
.analytics-loading { text-align: center; padding: 40px; color: #6e6e6e; }

.an-panel { animation: fadeIn 0.2s; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.an-summary-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.an-stat-card { flex: 1; min-width: 120px; background: linear-gradient(135deg, #f8f9fa, #e8eaf6); border-radius: 12px; padding: 16px; text-align: center; }
.an-stat-value { display: block; font-size: 24px; font-weight: 700; color: #1565c0; }
.an-stat-label { display: block; font-size: 12px; color: #636b72; margin-top: 4px; }

.an-chart-row { margin-bottom: 20px; }
.an-chart-box { background: #fafafa; border-radius: 12px; padding: 16px; }
.an-chart-box h3 { margin: 0 0 12px 0; font-size: 15px; }

.an-risk-section { margin-top: 20px; }
.an-risk-section h3 { color: #c62828; }
.an-risk-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.an-risk-table th { background: #ffebee; padding: 8px; text-align: left; font-weight: 600; }
.an-risk-table td { padding: 8px; border-bottom: 1px solid #f5f5f5; }
.an-risk-row:hover { background: #fff3e0; }
.an-level-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; background: #e3f2fd; color: #1565c0; }
.an-risk-tag { display: inline-block; padding: 2px 6px; margin: 1px; border-radius: 4px; font-size: 10px; background: #ffcdd2; color: #b71c1c; }
.an-msg-btn { background: #42a5f5; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.an-msg-btn:hover { background: #1e88e5; }
.an-empty { text-align: center; padding: 40px; color: #6e6e6e; font-size: 14px; }

/* 취약구간 */
.an-weak-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.an-weak-table th { background: #fff3e0; padding: 8px; text-align: left; }
.an-weak-table td { padding: 8px; border-bottom: 1px solid #f5f5f5; }
.an-rank { font-weight: 700; color: #e65100; font-size: 16px; }
.an-bar-bg { height: 8px; background: #e0e0e0; border-radius: 4px; width: 80px; display: inline-block; margin-right: 8px; vertical-align: middle; }
.an-bar-fill { height: 100%; background: linear-gradient(90deg, #ff9800, #f44336); border-radius: 4px; }
.an-source-tag { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; background: #e8eaf6; color: #3f51b5; }

/* AI 제안 */
.an-suggestion-card { background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.an-sg-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.an-sg-type { font-weight: 600; font-size: 13px; }
.an-sg-student { font-size: 12px; color: #636b72; }
.an-sg-detail { margin: 0; font-size: 13px; color: #444; }
.an-sg-actions { display: flex; gap: 8px; margin-top: 12px; }
.an-btn-approve { background: #4caf50; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; }
.an-btn-approve:hover { background: #388e3c; }
.an-btn-reject { background: #ef5350; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; }
.an-btn-reject:hover { background: #c62828; }
.an-decision-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px; }
.an-decision-detail { color: #6e6e6e; }

/* 리포트 */
.an-report-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.an-report-table th { background: #e8f5e9; padding: 6px; text-align: center; font-weight: 600; }
.an-report-table td { padding: 6px; text-align: center; border-bottom: 1px solid #f5f5f5; }

/* 재분류 */
.an-redistribution { margin-top: 20px; padding: 16px; background: #fff8e1; border-radius: 12px; }
.an-reclass-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.an-reclass-reason { font-size: 11px; color: #636b72; }
.an-btn-apply { background: #7c4dff; color: white; border: none; padding: 8px 20px; border-radius: 8px; cursor: pointer; margin-top: 12px; font-weight: 600; }
.an-btn-apply:hover { background: #651fff; }

/* 그룹 메시지 */
.an-group-msg { background: #f5f5f5; padding: 16px; border-radius: 12px; }
.an-select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 8px; }
.an-input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 8px; box-sizing: border-box; }
.an-textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 8px; resize: vertical; box-sizing: border-box; }
.an-btn-send { background: #1565c0; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.an-btn-send:hover { background: #0d47a1; }
.an-btn-send:disabled { opacity: 0.5; cursor: not-allowed; }

/* 모달 */
.an-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 999; }
.an-modal { background: white; border-radius: 16px; padding: 24px; width: 400px; max-width: 90vw; }
.an-modal h3 { margin-top: 0; }
.an-modal-actions { display: flex; gap: 8px; margin-top: 12px; }
.an-btn-cancel { background: #e0e0e0; color: #333; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; }

/* ── Review Routes Tab ── */
.review-tab-content { padding: 20px 0; }
.review-tab-content h2 { margin: 0 0 4px; font-size: 22px; }
.review-list { display: flex; flex-direction: column; gap: 12px; }
.review-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; }
.review-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.review-header h3 { margin: 0 0 4px; font-size: 17px; color: #333; }
.review-meta { font-size: 13px; color: #636b72; }
.review-status { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }
.review-status.pending { background: #fff3e0; color: #e65100; }
.review-items { margin-bottom: 12px; }
.review-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 14px; color: #555; border-bottom: 1px solid #f5f5f5; }
.ri-num { width: 22px; height: 22px; border-radius: 50%; background: #e3f2fd; color: #1976d2; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.review-actions { display: flex; gap: 8px; }
.btn-approve { background: #4caf50; color: white; border: none; padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-approve:hover { background: #388e3c; }
.btn-edit-route { background: white; color: #333; border: 1px solid #ddd; padding: 8px 20px; border-radius: 8px; font-size: 13px; cursor: pointer; }
.btn-edit-route:hover { background: #f5f5f5; }
</style>
