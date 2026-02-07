<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';

import { useAuthStore } from '../stores/auth';

const router = useRouter();
const authStore = useAuthStore();
const isLoginMode = ref(true);

const form = ref({
    username: '',
    password: '',
    email: '',
    confirmPassword: ''
});

const handleLogin = async () => {
    try {
        const { data } = await api.post('/auth/login/', {
            username: form.value.username,
            password: form.value.password
        });
        
        // Use Store Action
        authStore.login(data.access, { username: form.value.username });
        
        alert(`환영합니다, ${form.value.username}님!`);
        router.push('/learning');
        
    } catch (e) {
        console.error(e);
        alert('로그인 실패: 아이디와 비밀번호를 확인해주세요.');
    }
};

const handleRegister = async () => {
    if (form.value.password !== form.value.confirmPassword) {
        alert('비밀번호가 일치하지 않습니다.');
        return;
    }
    
    try {
        await api.post('/auth/register/', {
            username: form.value.username,
            password: form.value.password,
            email: form.value.email
        });
        
        alert('회원가입 성공! 로그인해주세요.');
        isLoginMode.value = true;
        
    } catch (e) {
        console.error(e);
        alert('회원가입 실패: 이미 존재하는 아이디이거나 오류가 발생했습니다.');
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
            
            <button type="submit" class="btn btn-primary btn-full">
                {{ isLoginMode ? '시작하기' : '계정 생성' }}
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
