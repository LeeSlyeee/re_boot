<script setup>
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api/axios';
import { Bar } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const route = useRoute();
const router = useRouter();
const students = ref([]);
const lectureId = route.params.id;
const lectureTitle = ref('');
const lectureCode = ref('');

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

        // [Change] Call 'monitor' instead of 'dashboard' for richer data
        const res = await api.get(`/learning/lectures/${lectureId}/monitor/`);
        students.value = res.data;
        
        chartData.value = {
            labels: students.value.map(s => s.name),
            datasets: [
                {
                    label: '진도율 (%)', // Changed to Progress
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

// Checklist Management
const syllabi = ref([]);
const isAddingWeek = ref(false);
const newWeekTitle = ref('');
const newWeekDesc = ref('');
const editingObjective = ref(null); // { weekId, text }

const fetchChecklist = async () => {
    try {
        // [FIX] Correct API endpoint matching ChecklistViewSet.list
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

onMounted(fetchDashboard);
</script>

<template>
    <div class="detail-view">
        <button class="back-btn" @click="router.push('/')">← 대시보드로 돌아가기</button>
        <div class="header-row">
            <h1>{{ lectureTitle }} - 학생 성적 현황</h1>
            <div class="code-badge" @click="copyCode" v-if="lectureCode">
                <span class="label">ENTRY CODE</span>
                <span class="value">{{ lectureCode }}</span>
                <span class="icon">❐</span>
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
</template>

<style scoped>
.detail-view { padding: 40px; max-width: 1200px; margin: 0 auto; color: #333; }
.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 30px; }
.header-row h1 { margin: 0; }
.code-badge {
    background: #e3f2fd; color: #1565c0; padding: 10px 20px; border-radius: 50px;
    display: flex; align-items: center; gap: 10px; cursor: pointer; transition: background 0.2s;
    font-size: 16px; border: 1px solid #bbdefb;
}
.code-badge:hover { background: #bbdefb; }
.code-badge .label { font-weight: normal; font-size: 13px; opacity: 0.8; }
.code-badge .value { font-weight: bold; font-size: 20px; letter-spacing: 2px; }
.back-btn { background: none; border: none; font-size: 16px; color: #007bff; cursor: pointer; margin-bottom: 20px; }
.chart-container { height: 400px; margin-bottom: 40px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.table-container { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 15px; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: bold; }
tr:last-child td { border-bottom: none; }

/* Syllabus Manager */
.syllabus-manager { margin-top: 50px; padding-top: 30px; border-top: 1px solid #ddd; }
.section-title { font-size: 20px; margin-bottom: 20px; }
.week-card {
    background: #f9f9f9; padding: 20px; margin-bottom: 20px;
    border-radius: 8px; border: 1px solid #eee;
}
.week-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.week-header h3 { margin: 0; font-size: 16px; color: #333; }
.btn-micro { padding: 4px 8px; font-size: 12px; cursor: pointer; border: 1px solid #ccc; background: white; border-radius: 4px; }
.objective-list { padding-left: 20px; }
.obj-item { margin-bottom: 5px; font-size: 14px; position: relative; }
.delete-x { color: #aaa; cursor: pointer; margin-left: 10px; font-weight: bold; display: none; }
.obj-item:hover .delete-x { display: inline; color: red; }
.add-week-form { margin-top: 30px; background: #f0f8ff; padding: 20px; border-radius: 8px; display: flex; gap: 10px; align-items: center; }
.add-week-form input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
.add-week-form button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }

/* Monitor Styles */
.student-name { font-weight: bold; font-size: 14px; margin-bottom: 2px; }
.student-email { font-size: 12px; color: #888; }

.status-badge {
    padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;
    display: inline-block;
}
.status-badge.critical { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.status-badge.warning { background: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80; }
.status-badge.good { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

.progress-wrapper { display: flex; align-items: center; gap: 10px; }
.progress-bar { flex: 1; height: 8px; background: #eee; border-radius: 10px; overflow: hidden; }
.progress-bar .fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.progress-bar .fill.critical { background: #c62828; }
.progress-bar .fill.warning { background: #ef6c00; }
.progress-bar .fill.good { background: #4caf50; }
.percent { font-size: 12px; font-weight: 600; min-width: 35px; text-align: right; }

.skill-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.skill-tag {
    background: #e3f2fd; color: #1565c0; padding: 4px 8px; border-radius: 4px; font-size: 11px;
    border: 1px solid #bbdefb;
}
.no-skill { color: #ccc; font-size: 12px; }
</style>
