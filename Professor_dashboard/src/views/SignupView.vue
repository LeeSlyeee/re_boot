<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';

const router = useRouter();
const username = ref('');
const password = ref('');
const passwordConfirm = ref('');
const email = ref('');
const errorMsg = ref('');

const handleSignup = async () => {
    if (password.value !== passwordConfirm.value) {
        errorMsg.value = '비밀번호가 일치하지 않습니다.';
        return;
    }

    try {
        const response = await api.post('/auth/register/', {
            username: username.value,
            password: password.value,
            email: email.value,
            role: 'INSTRUCTOR' // 강사로 고정
        });
        
        alert('회원가입이 완료되었습니다. 로그인해주세요.');
        router.push('/login');
    } catch (e) {
        console.error(e);
        if (e.response && e.response.data) {
            // 에러 메시지가 딕셔너리 형태일 경우 처리
            const errors = Object.values(e.response.data).flat();
            errorMsg.value = errors.join(', ') || '회원가입 실패. 입력 정보를 확인하세요.';
        } else {
            errorMsg.value = '회원가입 중 오류가 발생했습니다.';
        }
    }
};
</script>

<template>
    <div class="login-container">
        <div class="card">
            <h2>강사 회원가입</h2>
            <form @submit.prevent="handleSignup">
                <div class="form-group">
                    <label>ID</label>
                    <input type="text" v-model="username" required placeholder="User ID" />
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" v-model="email" required placeholder="Email Address" />
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" v-model="password" required placeholder="Password" />
                </div>
                <div class="form-group">
                    <label>Confirm Password</label>
                    <input type="password" v-model="passwordConfirm" required placeholder="Confirm Password" />
                </div>
                
                <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
                
                <button type="submit">Complete Signup</button>
            </form>
            <div class="footer-link">
                <router-link to="/login">이미 계정이 있으신가요? 로그인</router-link>
            </div>
        </div>
    </div>
</template>

<style scoped>
.login-container {
    display: flex; justify-content: center; align-items: center;
    height: 100vh; background: #f0f2f5;
}
.card {
    background: white; padding: 40px; border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 350px;
}
.form-group { margin-bottom: 20px; }
label { display: block; margin-bottom: 5px; font-weight: bold; }
input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button {
    width: 100%; padding: 12px; background: #28a745; color: white;
    border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 10px;
}
button:hover { background: #218838; }
.error { color: red; margin-bottom: 15px; font-size: 14px; }
.footer-link { text-align: center; margin-top: 20px; font-size: 14px; }
.footer-link a { color: #007bff; text-decoration: none; }
.footer-link a:hover { text-decoration: underline; }
</style>
