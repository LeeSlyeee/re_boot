<script setup>
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import api from '../api/axios';
import { useToast } from '../composables/useToast';
const { showToast } = useToast();

import { useAuthStore } from '../stores/auth';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const isLoginMode = ref(true);
const isLoading = ref(false);
const errorMessage = ref('');

const form = ref({
    username: '',
    password: '',
    email: '',
    confirmPassword: ''
});

const handleLogin = async () => {
    if (isLoading.value) return;
    errorMessage.value = '';
    isLoading.value = true;
    
    try {
        const { data } = await api.post('/auth/login/', {
            username: form.value.username,
            password: form.value.password
        });
        
        // Use Store Action
        authStore.login(data.access, { username: form.value.username });
        
        showToast(`환영합니다, ${form.value.username}님!`, 'success');
        
        // redirect 쿼리 파라미터가 있으면 해당 경로로, 없으면 /learning
        const redirectTo = route.query.redirect || '/learning';
        
        // router.push()도 비동기이므로 await 처리하여 네비게이션 실패를 방지
        await router.push(redirectTo);
        
    } catch (e) {
        console.error('Login Error:', e);
        const detail = e.response?.data?.detail;
        errorMessage.value = detail || '아이디 또는 비밀번호가 올바르지 않습니다.';
        showToast('로그인 실패: 아이디와 비밀번호를 확인해주세요.', 'error');
    } finally {
        isLoading.value = false;
    }
};

const handleRegister = async () => {
    if (isLoading.value) return;
    errorMessage.value = '';
    
    if (form.value.password !== form.value.confirmPassword) {
        errorMessage.value = '비밀번호가 일치하지 않습니다.';
        showToast('비밀번호가 일치하지 않습니다.', 'error');
        return;
    }
    
    isLoading.value = true;
    try {
        await api.post('/auth/register/', {
            username: form.value.username,
            password: form.value.password,
            email: form.value.email
        });
        
        showToast('회원가입 성공! 로그인해주세요.', 'success');
        isLoginMode.value = true;
        
    } catch (e) {
        console.error('Register Error:', e);
        if (e.response?.data?.detail) {
            errorMessage.value = e.response.data.detail;
        } else if (e.response?.data) {
            errorMessage.value = Object.entries(e.response.data)
                .map(([key, val]) => `${Array.isArray(val) ? val.join(', ') : val}`)
                .join(' · ');
        } else {
            errorMessage.value = '회원가입에 실패했습니다. 다시 시도해주세요.';
        }
        showToast('회원가입 실패', 'error');
    } finally {
        isLoading.value = false;
    }
};
</script>

<template>
  <div class="auth-view">
    <div class="glass-panel auth-card">
        <h2 class="text-headline">{{ isLoginMode ? '로그인' : '회원가입' }}</h2>
        <p class="text-subhead">{{ isLoginMode ? 'Re:Boot에 오신 것을 환영합니다.' : '커리어 빌드업을 시작해보세요.' }}</p>
        
        <form @submit.prevent="isLoginMode ? handleLogin() : handleRegister()">
            <div class="input-group">
                <input type="text" v-model="form.username" placeholder="사용자 아이디" required />
            </div>
            
            <div v-if="!isLoginMode" class="input-group">
                <input type="email" v-model="form.email" placeholder="이메일 주소" required />
            </div>

            <div class="input-group">
                <input type="password" v-model="form.password" placeholder="비밀번호" required />
            </div>

            <div v-if="!isLoginMode" class="input-group">
                <input type="password" v-model="form.confirmPassword" placeholder="비밀번호 확인" required />
            </div>
            
            <div v-if="errorMessage" class="error-inline">
                <span>⚠️ {{ errorMessage }}</span>
            </div>

            <button type="submit" class="btn btn-primary btn-full" :disabled="isLoading">
                <span v-if="isLoading">처리 중...</span>
                <span v-else>{{ isLoginMode ? '시작하기' : '계정 생성' }}</span>
            </button>
        </form>
        
        <div class="toggle-mode">
            <span v-if="isLoginMode">계정이 없으신가요? <a @click="isLoginMode = false">회원가입</a></span>
            <span v-else>이미 계정이 있으신가요? <a @click="isLoginMode = true">로그인</a></span>
        </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.auth-view {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding-top: var(--header-height);
}

.auth-card {
    width: 100%;
    max-width: 400px;
    padding: 40px;
    text-align: center;
}

.text-headline {
    font-size: 32px;
    margin-bottom: 8px;
}

.text-subhead {
    font-size: 14px;
    margin-bottom: 32px;
}

.input-group {
    margin-bottom: 16px;
    
    input {
        width: 100%;
        padding: 12px 16px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: white;
        font-size: 16px;
        transition: all 0.2s;
        
        &:focus {
            outline: none;
            border-color: var(--color-accent);
            background: rgba(255, 255, 255, 0.1);
        }
    }
}

.btn-full {
    width: 100%;
    margin-top: 16px;
    height: 48px;
    font-size: 16px;
}

.error-inline {
    margin-top: 8px;
    margin-bottom: 4px;
    padding: 10px 14px;
    background: rgba(255, 69, 58, 0.12);
    border: 1px solid rgba(255, 69, 58, 0.3);
    border-radius: 10px;
    text-align: left;

    span {
        color: #ff6b6b;
        font-size: 13px;
        font-weight: 500;
        line-height: 1.4;
    }
}

.toggle-mode {
    margin-top: 24px;
    font-size: 14px;
    color: var(--color-text-secondary);
    
    a {
        color: var(--color-accent);
        cursor: pointer;
        font-weight: 500;
        
        &:hover {
            text-decoration: underline;
        }
    }
}
</style>
