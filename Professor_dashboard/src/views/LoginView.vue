<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/axios';

const router = useRouter();
const username = ref('');
const password = ref('');
const errorMsg = ref('');

const handleLogin = async () => {
    try {
        const response = await api.post('/auth/login/', {
            username: username.value,
            password: password.value
        });
        
        localStorage.setItem('access_token', response.data.access);
        localStorage.setItem('refresh_token', response.data.refresh);
        
        router.push('/');
    } catch (e) {
        console.error(e);
        errorMsg.value = '로그인 실패. 아이디와 비밀번호를 확인하세요.';
    }
};
</script>

<template>
    <div class="login-container">
        <div class="card">
            <h2>Professor Dashboard</h2>
            <form @submit.prevent="handleLogin">
                <div class="form-group">
                    <label>ID</label>
                    <input type="text" v-model="username" required />
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" v-model="password" required />
                </div>
                <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
                <button type="submit">Login</button>
            </form>
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
input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
button {
    width: 100%; padding: 12px; background: #007bff; color: white;
    border: none; border-radius: 4px; cursor: pointer; font-size: 16px;
}
button:hover { background: #0056b3; }
.error { color: red; margin-bottom: 15px; font-size: 14px; }
</style>
