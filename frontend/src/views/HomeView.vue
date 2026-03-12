<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import api from '../api/axios';

const router = useRouter();
const authStore = useAuthStore();
const isDemoLoading = ref(false);

function startLearning() {
  if (authStore.token) {
    // 이미 로그인 → 바로 학습 페이지
    router.push('/learning');
  } else {
    // 미로그인 → 로그인 후 학습 페이지로 리다이렉트
    router.push('/auth?redirect=/learning');
  }
}

async function startDemoLearning() {
  isDemoLoading.value = true;
  try {
    // 1. 데모 게스트 로그인 (고유 유저 자동 생성)
    const res = await api.post('/auth/demo-login/');
    const { access, user } = res.data;

    // 2. authStore에 토큰 저장 (기존 인증 체계 그대로 활용)
    authStore.login(access, user);

    // 3. 학습 페이지로 이동 (클래스 참여 자동 진입)
    router.push('/learning?mode=join');
  } catch (e) {
    console.error('데모 로그인 실패:', e);
    alert('데모 로그인에 실패했습니다. 서버 상태를 확인해주세요.');
  } finally {
    isDemoLoading.value = false;
  }
}
</script>

<template>
  <div class="home-view">
    <section class="hero-section">
      <div class="container">
        <h1 class="text-headline">
          Re:Boot Your Career.<br />
          <span class="gradient-text">AI Powered.</span>
        </h1>
        <p class="text-subhead">
          실시간 경로 재설계로 완주를 보장하는<br />
          가장 진보된 커리어 빌드업 플랫폼.
        </p>
        <div class="cta-group">
          <!-- 로그인 사용자: 기존 학습 시작 버튼 -->
          <button v-if="authStore.token" class="btn-cta" @click="startLearning">
            <span class="btn-cta-icon">🚀</span>
            학습 시작하기
          </button>
          <!-- 미로그인: 현장 강의 테스트 버튼 -->
          <template v-else>
            <button
              class="btn-cta btn-demo"
              :disabled="isDemoLoading"
              @click="startDemoLearning"
            >
              <span class="btn-cta-icon">📚</span>
              {{ isDemoLoading ? '준비 중...' : '현장 강의 테스트' }}
            </button>
            <button class="btn-cta-secondary" @click="startLearning">
              로그인하여 학습 시작
            </button>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.home-view {
  padding-top: 100px;
  text-align: center;
}

.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.text-headline {
  font-size: 64px;
  margin-bottom: 24px;

  .gradient-text {
    background: linear-gradient(135deg, #6366f1 0%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.text-subhead {
  max-width: 600px;
  margin: 0 auto 48px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.6);
  font-size: 17px;
}

.cta-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.btn-cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 16px 36px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 24px rgba(99, 102, 241, 0.3);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(99, 102, 241, 0.45);
  }

  &:active {
    transform: translateY(0);
  }

  &:disabled {
    opacity: 0.7;
    cursor: wait;
  }
}

.btn-demo {
  background: linear-gradient(135deg, #10b981, #059669);
  box-shadow: 0 4px 24px rgba(16, 185, 129, 0.3);
  font-size: 19px;
  padding: 18px 42px;

  &:hover {
    box-shadow: 0 8px 32px rgba(16, 185, 129, 0.45);
  }
}

.btn-cta-secondary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    border-color: rgba(255, 255, 255, 0.4);
    color: rgba(255, 255, 255, 0.8);
  }
}

.btn-cta-icon {
  font-size: 20px;
}
</style>
