<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Trash2 } from 'lucide-vue-next';
import api from '../api/axios';

const lectures = ref([]);
const router = useRouter();

const fetchLectures = async () => {
    try {
        const res = await api.get('/learning/lectures/');
        lectures.value = res.data;
    } catch (e) {
        console.error(e);
        if (e.response && e.response.status === 401) {
            router.push('/login');
        }
    }
};

const showModal = ref(false);
const newLectureTitle = ref('');
const isSubmitting = ref(false);
const modalError = ref('');

const openModal = () => {
    showModal.value = true;
    newLectureTitle.value = '';
    modalError.value = '';
};

const closeModal = () => {
    showModal.value = false;
    modalError.value = '';
};

const createLecture = async () => {
    if (!newLectureTitle.value.trim()) return;
    if (isSubmitting.value) return;

    isSubmitting.value = true;
    modalError.value = '';

    try {
        await api.post('/learning/lectures/', { title: newLectureTitle.value });
        showModal.value = false;
        fetchLectures();
    } catch (e) {
        console.error(e);
        if (e.response && e.response.data) {
            if (e.response.data.detail) {
                modalError.value = e.response.data.detail;
            } else {
                modalError.value = Object.entries(e.response.data)
                    .map(([key, val]) => `${key}: ${val}`)
                    .join(', ');
            }
        } else {
            modalError.value = "강의 생성 중 오류가 발생했습니다.";
        }
    } finally {
        isSubmitting.value = false;
    }
};

const deleteLecture = async (id) => {
    if (!confirm("정말로 이 강의를 삭제하시겠습니까? 삭제 후에는 복구할 수 없습니다.")) return;
    
    try {
        await api.delete(`/learning/lectures/${id}/`);
        fetchLectures();
    } catch (e) {
        console.error(e);
        alert("강의 삭제 실패: " + (e.response?.data?.detail || "알 수 없는 오류"));
    }
};

const goToDetail = (id) => {
    router.push(`/lecture/${id}`);
};

onMounted(fetchLectures);
</script>

<template>
    <div class="dashboard">
        <header>
            <h1>My Classrooms</h1>
            <button @click="openModal">+ New Class</button>
        </header>
        
        <div class="grid">
            <div v-for="lecture in lectures" :key="lecture.id" class="card" @click="goToDetail(lecture.id)">
                <div class="card-header">
                    <h3>{{ lecture.title }}</h3>
                    <button class="btn-delete" @click.stop="deleteLecture(lecture.id)">
                        <Trash2 :size="18" />
                    </button>
                </div>
                <p class="code">Code: <span>{{ lecture.access_code }}</span></p>
                <p>Students: {{ lecture.student_count || 0 }}</p>
                <span class="date">{{ new Date(lecture.created_at).toLocaleDateString() }}</span>
            </div>
        </div>
        
        <div v-if="lectures.length === 0" class="empty-state">
            <p>개설된 강의가 없습니다. 새로운 강의를 생성해보세요.</p>
        </div>

        <!-- Custom Modal -->
        <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
            <div class="modal-content">
                <h2>새 강의 개설</h2>
                <input type="text" v-model="newLectureTitle" placeholder="강의명을 입력하세요 (예: React 기초)" @keyup.enter="createLecture" :disabled="isSubmitting" />
                
                <p v-if="modalError" class="error-text">{{ modalError }}</p>

                <div class="modal-actions">
                    <button class="btn-cancel" @click="closeModal" :disabled="isSubmitting">취소</button>
                    <button class="btn-confirm" @click="createLecture" :disabled="isSubmitting">
                        {{ isSubmitting ? '생성 중...' : '생성하기' }}
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.dashboard { padding: 40px; max-width: 1200px; margin: 0 auto; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; }

.card {
    background: white; padding: 24px; border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05); cursor: pointer;
    transition: transform 0.2s; border: 1px solid #eee;
    position: relative;
}
.card:hover { transform: translateY(-5px); box-shadow: 0 8px 12px rgba(0,0,0,0.1); }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.card-header h3 { margin: 0; font-size: 20px; color: #333; flex: 1; text-align: left; }

.btn-delete {
    padding: 6px; background: transparent; color: #999; border: none; 
    border-radius: 4px; cursor: pointer; transition: all 0.2s;
    display: flex; align-items: center; justify-content: center;
}
.btn-delete:hover { background: #ffebeb; color: #dc3545; }

p { color: #666; margin: 4px 0; }
.code { font-weight: bold; color: #4facfe; font-size: 14px; background: rgba(79, 172, 254, 0.1); display: inline-block; padding: 2px 8px; border-radius: 4px; }
button { padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; }
button:hover { background: #218838; }

.empty-state { text-align: center; margin-top: 50px; color: #888; }
.error-text { color: #dc3545; font-size: 14px; margin-bottom: 15px; }

/* Modal Styles */
.modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.5); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
}
.modal-content {
    background: white; padding: 30px; border-radius: 12px; width: 400px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}
.modal-content h2 { margin-top: 0; margin-bottom: 20px; color: #333; }
.modal-content input {
    width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px;
    font-size: 16px; margin-bottom: 20px; box-sizing: border-box;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn-cancel { background: #ddd; color: #333; }
.btn-cancel:hover { background: #ccc; }
.btn-confirm { background: #007bff; color: white; }
.btn-confirm:hover { background: #0056b3; }
</style>
