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

        const res = await api.get(`/learning/lectures/${lectureId}/dashboard/`);
        students.value = res.data;
        
        chartData.value = {
            labels: students.value.map(s => s.name),
            datasets: [
                {
                    label: '평균 점수',
                    backgroundColor: '#4facfe',
                    data: students.value.map(s => s.average_score)
                }
            ]
        };
    } catch (e) {
        console.error(e);
        if (e.response && e.response.status === 401) router.push('/login');
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
                        <th>이름</th>
                        <th>이메일</th>
                        <th>퀴즈 응시 횟수</th>
                        <th>평균 점수</th>
                        <th>최근 점수</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="student in students" :key="student.id">
                        <td>{{ student.name }}</td>
                        <td>{{ student.email }}</td>
                        <td>{{ student.quiz_count }}</td>
                        <td>{{ student.average_score }}</td>
                        <td>{{ student.latest_score }}</td>
                    </tr>
                    <tr v-if="students.length === 0">
                        <td colspan="5" style="text-align: center; color: #888;">수강생 데이터가 없습니다.</td>
                    </tr>
                </tbody>
            </table>
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
</style>
