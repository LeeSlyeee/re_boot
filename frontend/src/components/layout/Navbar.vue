<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { useAuthStore } from '../../stores/auth';

const route = useRoute();
const isScrolled = ref(false);
const openDropdown = ref(null); // 'learn' | 'career' | null
let closeTimer = null;

const handleScroll = () => {
  isScrolled.value = window.scrollY > 0;
};

onMounted(() => {
  window.addEventListener('scroll', handleScroll);
});

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll);
});

const authStore = useAuthStore();

// ─── 드롭다운 그룹 정의 ───
const learnItems = [
  { to: '/onboarding', label: '온보딩 센터', icon: '🎓' },
  { to: '/placement', label: '레벨테스트', icon: '🎯' },
  { to: '/gapmap', label: '갭 맵', icon: '📊' },
  { to: '/curriculum', label: '로드맵', icon: '🗺️' },
];

const careerItems = [
  { to: '/portfolio', label: '포트폴리오', icon: '📁' },
  { to: '/interview/setup', label: '면접 연습', icon: '🎭' },
];

// ─── 드롭다운 로직 ───
function showDropdown(name) {
  clearTimeout(closeTimer);
  openDropdown.value = name;
}

function scheduleClose() {
  closeTimer = setTimeout(() => {
    openDropdown.value = null;
  }, 200);
}

function cancelClose() {
  clearTimeout(closeTimer);
}

// 해당 그룹의 하위 경로 중 하나라도 현재 활성이면 true
function isGroupActive(items) {
  return items.some(item => route.path === item.to || route.path.startsWith(item.to + '/'));
}
</script>

<template>
  <nav class="navbar" :class="{ scrolled: isScrolled }">
    <div class="nav-content">
      <!-- 로고 -->
      <div class="logo">
        <RouterLink to="/" class="brand-link">Re:Boot</RouterLink>
      </div>

      <!-- 네비게이션 -->
      <div class="nav-links">
        <!-- 학습하기 (직접 노출) -->
        <RouterLink to="/learning" class="nav-trigger direct-link">학습하기</RouterLink>

        <!-- 학습관리 드롭다운 -->
        <div
          class="nav-dropdown"
          @mouseenter="showDropdown('learn')"
          @mouseleave="scheduleClose"
        >
          <button
            class="nav-trigger"
            :class="{ active: isGroupActive(learnItems) }"
          >
            학습관리
            <svg class="chevron" :class="{ open: openDropdown === 'learn' }" width="10" height="6" viewBox="0 0 10 6" fill="none">
              <path d="M1 1L5 5L9 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <Transition name="dropdown">
            <div
              v-if="openDropdown === 'learn'"
              class="dropdown-panel"
              @mouseenter="cancelClose"
              @mouseleave="scheduleClose"
            >
              <RouterLink
                v-for="item in learnItems"
                :key="item.to"
                :to="item.to"
                class="dropdown-item"
                @click="openDropdown = null"
              >
                <span class="dropdown-icon">{{ item.icon }}</span>
                <span class="dropdown-label">{{ item.label }}</span>
              </RouterLink>
            </div>
          </Transition>
        </div>

        <!-- 커리어 드롭다운 -->
        <div
          class="nav-dropdown"
          @mouseenter="showDropdown('career')"
          @mouseleave="scheduleClose"
        >
          <button
            class="nav-trigger"
            :class="{ active: isGroupActive(careerItems) }"
          >
            커리어
            <svg class="chevron" :class="{ open: openDropdown === 'career' }" width="10" height="6" viewBox="0 0 10 6" fill="none">
              <path d="M1 1L5 5L9 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <Transition name="dropdown">
            <div
              v-if="openDropdown === 'career'"
              class="dropdown-panel"
              @mouseenter="cancelClose"
              @mouseleave="scheduleClose"
            >
              <RouterLink
                v-for="item in careerItems"
                :key="item.to"
                :to="item.to"
                class="dropdown-item"
                @click="openDropdown = null"
              >
                <span class="dropdown-icon">{{ item.icon }}</span>
                <span class="dropdown-label">{{ item.label }}</span>
              </RouterLink>
            </div>
          </Transition>
        </div>

        <!-- 대시보드 (직접 노출) -->
        <RouterLink to="/dashboard" class="nav-trigger direct-link">대시보드</RouterLink>
      </div>

      <!-- 사용자 영역 -->
      <div class="nav-actions">
        <div v-if="authStore.token" class="user-menu">
          <span class="welcome-msg">{{ authStore.user?.username }}님</span>
          <button class="btn-logout" @click="authStore.logout">로그아웃</button>
        </div>
        <RouterLink v-else to="/auth" class="btn-login">로그인</RouterLink>
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
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  z-index: 1000;
  transition: all 0.3s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);

  &.scrolled {
    background: rgba(10, 10, 15, 0.95);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
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

// ─── 로고 ───
.logo {
  flex-shrink: 0;

  .brand-link {
    font-weight: 700;
    font-size: 20px;
    color: #fff;
    letter-spacing: -0.03em;
    text-decoration: none;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

// ─── 네비 링크 영역 ───
.nav-links {
  display: flex;
  align-items: center;
  gap: 8px;
}

// ─── 드롭다운 컨테이너 ───
.nav-dropdown {
  position: relative;
}

// ─── 트리거 버튼 (학습 ▾, 커리어 ▾, 대시보드) ───
.nav-trigger {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.65);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
  white-space: nowrap;

  &:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.06);
  }

  &.active,
  &.router-link-active {
    color: #a78bfa;
    background: rgba(139, 92, 246, 0.1);
  }
}

.direct-link {
  text-decoration: none;
}

// ─── 쉐브론 아이콘 ───
.chevron {
  transition: transform 0.25s ease;
  opacity: 0.5;

  &.open {
    transform: rotate(180deg);
    opacity: 1;
  }
}

// ─── 드롭다운 패널 ───
.dropdown-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 200px;
  padding: 8px;
  background: rgba(22, 22, 30, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.03) inset;
}

// ─── 드롭다운 아이템 ───
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.75);
  text-decoration: none;
  font-size: 14px;
  font-weight: 450;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 92, 246, 0.12);
    color: #fff;

    .dropdown-icon {
      transform: scale(1.15);
    }
  }

  &.router-link-active {
    background: rgba(139, 92, 246, 0.15);
    color: #a78bfa;
  }
}

.dropdown-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
  transition: transform 0.2s ease;
}

.dropdown-label {
  flex: 1;
}

// ─── 드롭다운 트랜지션 ───
.dropdown-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown-leave-active {
  transition: all 0.15s ease-in;
}

.dropdown-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-6px) scale(0.97);
}

.dropdown-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-4px) scale(0.98);
}

// ─── 사용자 영역 ───
.nav-actions {
  flex-shrink: 0;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 12px;

  .welcome-msg {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.7);
  }
}

.btn-logout {
  padding: 6px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.75);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.2);
    color: #fff;
  }
}

.btn-login {
  padding: 8px 20px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
    transform: translateY(-1px);
  }
}
</style>
