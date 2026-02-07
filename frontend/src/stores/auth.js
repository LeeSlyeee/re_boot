import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useAuthStore = defineStore('auth', () => {
    const token = ref(localStorage.getItem('token') || null);
    const user = ref(JSON.parse(localStorage.getItem('user') || 'null'));

    const isLoggedIn = computed(() => !!token.value);

    const login = (accessToken, userData) => {
        token.value = accessToken;
        user.value = userData;
        localStorage.setItem('token', accessToken);
        // localStorage.setItem('user', JSON.stringify(userData)); // Store user info if available
    };

    const logout = () => {
        token.value = null;
        user.value = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/'; // Redirect to home
    };

    return { token, user, isLoggedIn, login, logout };
});
