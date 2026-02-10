<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { RouterLink } from "vue-router";
import { useAuthStore } from '../../stores/auth';

const isScrolled = ref(false);

const handleScroll = () => {
  isScrolled.value = window.scrollY > 0;
};

const authStore = useAuthStore();
// Pinia state is reactive by default when accessed directly
</script>

<template>
  <nav class="navbar glass-panel">
    <div class="nav-content">
      <div class="logo">
        <RouterLink to="/" class="brand-link">Re:Boot</RouterLink>
      </div>
      
      <div class="nav-links">
        <RouterLink to="/learning" class="nav-item">학습하기</RouterLink>
        <RouterLink to="/dashboard" class="nav-item">대시보드</RouterLink>
        <RouterLink to="/portfolio" class="nav-item">포트폴리오</RouterLink>
      </div>

      <div class="nav-actions">
        <!-- Direct access to store state for reactivity -->
        <div v-if="authStore.token" class="user-menu">
            <span class="welcome-msg">{{ authStore.user?.username }}님 환영합니다!</span>
            <button class="btn btn-primary" @click="authStore.logout">로그아웃</button>
        </div>
        <RouterLink v-else to="/auth" class="btn btn-primary">로그인</RouterLink>
      </div>
    </div>
  </nav>
</template>

<style scoped lang="scss">
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: var(--header-height);
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  z-index: 1000;
  transition: background 0.3s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0);

  &.scrolled {
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
}

.nav-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.logo {
  font-weight: 600;
  font-size: 18px;
  color: white;
  letter-spacing: -0.02em;
}

.nav-links {
  display: flex;
  gap: 32px;
}

.nav-item {
  font-size: 12px;
  color: #e8e8ed;
  opacity: 0.8;
  transition: opacity 0.2s ease;

  &:hover {
    opacity: 1;
  }

  &.router-link-active {
    opacity: 1;
    color: var(--color-accent);
  }
}

.user-menu {
  display: flex; 
  align-items: center; 
  gap: 16px; /* 여유로운 간격 */
  
  .welcome-msg {
    font-size: 14px;
    font-weight: 500;
    color: #e8e8ed;
  }
}
</style>
