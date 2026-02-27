<script setup>
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const router = useRouter();
const authStore = useAuthStore();

function startLearning() {
  if (authStore.token) {
    // 이미 로그인 → 바로 학습 페이지
    router.push('/learning');
  } else {
    // 미로그인 → 로그인 후 학습 페이지로 리다이렉트
    router.push('/auth?redirect=/learning');
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
          <button class="btn-cta" @click="startLearning">
            <span class="btn-cta-icon">🚀</span>
            {{ authStore.token ? '학습 시작하기' : '로그인 하여 학습 시작하기' }}
          </button>
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
  justify-content: center;
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
}

.btn-cta-icon {
  font-size: 20px;
}
</style>
