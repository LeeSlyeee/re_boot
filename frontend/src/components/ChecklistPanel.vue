<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { CheckCircle, Circle, ChevronDown, ChevronRight, ListChecks } from 'lucide-vue-next';
import api from '../api/axios';

const props = defineProps({
    lectureId: { type: [String, Number], required: true }
});

const syllabi = ref([]);
const isLoading = ref(true);
const openWeeks = ref({}); // { week_number: boolean }

// Computed: 전체 진도율
const progress = computed(() => {
    let total = 0;
    let checked = 0;
    syllabi.value.forEach(s => {
        s.objectives.forEach(o => {
            total++;
            if (o.is_checked) checked++;
        });
    });
    return total === 0 ? 0 : Math.round((checked / total) * 100);
});

const fetchChecklist = async () => {
    if (!props.lectureId) return;
    isLoading.value = true;
    try {
        const res = await api.get(`/learning/checklist/?lecture_id=${props.lectureId}`);
        syllabi.value = res.data;
        
        // Default: Open the first week or all? Let's open the first active week
        syllabi.value.forEach((s, idx) => {
             // Open first week by default
             if (idx === 0) openWeeks.value[s.week_number] = true;
        });
    } catch (e) {
        console.error("Failed to fetch checklist", e);
    } finally {
        isLoading.value = false;
    }
};

const toggleWeek = (weekNum) => {
    openWeeks.value[weekNum] = !openWeeks.value[weekNum];
};

const toggleObjective = async (objective) => {
    // Frontend Optimistic Update
    const originalState = objective.is_checked;
    objective.is_checked = !objective.is_checked;

    try {
        await api.post(`/learning/checklist/${objective.id}/toggle/`);
    } catch (e) {
        console.error("Toggle Failed", e);
        objective.is_checked = originalState; // Revert on fail
    }
};

onMounted(fetchChecklist);
watch(() => props.lectureId, fetchChecklist);

</script>

<template>
    <div class="checklist-panel glass-panel">
        <div class="checklist-header">
            <h3><ListChecks size="20" /> 학습 진도 체크리스트</h3>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="fill" :style="{width: progress + '%'}"></div>
                </div>
                <span class="percent">{{ progress }}% 달성</span>
            </div>
        </div>

        <div v-if="isLoading" class="loading-state">
            로딩 중...
        </div>

        <div v-else-if="syllabi.length === 0" class="empty-state">
            <p>등록된 강의 계획서가 없습니다.</p>
        </div>

        <div v-else class="syllabus-list">
            <div v-for="week in syllabi" :key="week.id" class="week-item">
                <div class="week-header" @click="toggleWeek(week.week_number)">
                    <component :is="openWeeks[week.week_number] ? ChevronDown : ChevronRight" size="16" class="arrow" />
                    <span class="week-title">{{ week.week_number }}주차: {{ week.title }}</span>
                </div>
                
                <div v-if="openWeeks[week.week_number]" class="objective-list">
                    <div v-for="obj in week.objectives" :key="obj.id" 
                         class="objective-item" :class="{checked: obj.is_checked}"
                         @click="toggleObjective(obj)">
                        <component :is="obj.is_checked ? CheckCircle : Circle" 
                                   size="18" 
                                   class="check-icon"
                                   :class="obj.is_checked ? 'checked-icon' : 'unchecked-icon'" />
                        <span class="content">{{ obj.content }}</span>
                    </div>
                    <div v-if="week.objectives.length === 0" class="no-objectives">
                        목표 없음
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped lang="scss">
.checklist-panel {
    display: flex; flex-direction: column;
    height: 100%; max-height: 800px;
    background: rgba(28, 28, 30, 0.6); 
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    overflow: hidden;
}

.checklist-header {
    margin-bottom: 20px;
    h3 { 
        display: flex; align-items: center; gap: 8px;
        font-size: 18px; color: white; margin: 0 0 12px 0;
    }
}

.progress-container {
    display: flex; align-items: center; gap: 10px;
    .progress-bar {
        flex: 1; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;
        .fill { height: 100%; background: var(--color-accent, #007aff); transition: width 0.3s ease; }
    }
    .percent { font-size: 13px; color: var(--color-accent, #007aff); font-weight: bold; width: 60px; text-align: right; }
}

.syllabus-list {
    flex: 1; overflow-y: auto;
    display: flex; flex-direction: column; gap: 10px;
    padding-right: 4px; /* Scrollbar space */
    
    &::-webkit-scrollbar { width: 6px; }
    &::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
}

.week-item {
    background: rgba(255,255,255,0.03); 
    border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);
    overflow: hidden;
}

.week-header {
    padding: 12px 16px; display: flex; align-items: center; gap: 8px;
    cursor: pointer; transition: background 0.2s;
    user-select: none;
    
    &:hover { background: rgba(255,255,255,0.08); }
    .week-title { font-weight: 600; font-size: 14px; color: #eee; }
    .arrow { color: #888; }
}

.objective-list {
    padding: 0 16px 12px 36px; /* Indent content */
    display: flex; flex-direction: column; gap: 8px;
}

.objective-item {
    display: flex; align-items: flex-start; gap: 10px;
    cursor: pointer; padding: 6px 0;
    transition: opacity 0.2s;
    
    .content { font-size: 14px; color: #ccc; line-height: 1.4; flex: 1; transition: color 0.2s; }
    .check-icon { margin-top: 1px; flex-shrink: 0; }
    
    .unchecked-icon { color: #555; }
    .checked-icon { color: var(--color-accent, #4caf50); }
    
    &:hover {
        .unchecked-icon { color: #888; }
        .content { color: white; }
    }
    
    &.checked .content {
        color: #888;
        text-decoration: line-through; /* Optional styling for completed items */
    }
}

.loading-state, .empty-state {
    text-align: center; color: #888; margin-top: 40px; font-size: 14px;
}
.no-objectives { font-size: 12px; color: #666; font-style: italic; }
</style>
