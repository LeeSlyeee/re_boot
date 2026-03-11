<template>
  <div class="not-found-container">
    <div class="not-found-content">
      <div class="error-code">404</div>
      <h1 class="error-title">페이지를 찾을 수 없습니다</h1>
      <p class="error-description">
        요청하신 페이지가 존재하지 않거나, 이동되었을 수 있습니다.
      </p>
      <div class="error-actions">
        <router-link to="/" class="btn-home">
          🏠 홈으로 돌아가기
        </router-link>
        <router-link to="/dashboard" class="btn-dashboard">
          📊 대시보드로 이동
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
// No logic needed
</script>

<style scoped>
.not-found-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0a0a1a 100%);
  padding: 2rem;
}

.not-found-content {
  text-align: center;
  max-width: 500px;
}

.error-code {
  font-size: 8rem;
  font-weight: 900;
  background: linear-gradient(135deg, #7c3aed, #a855f7, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  margin-bottom: 1rem;
  animation: pulse-glow 2s ease-in-out infinite alternate;
}

@keyframes pulse-glow {
  from { opacity: 0.7; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.error-title {
  font-size: 1.5rem;
  color: #e2e8f0;
  margin-bottom: 0.75rem;
  font-weight: 600;
}

.error-description {
  color: #94a3b8;
  font-size: 1rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.error-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.btn-home, .btn-dashboard {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.3s ease;
}

.btn-home {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.btn-home:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(124, 58, 237, 0.4);
}

.btn-dashboard {
  background: rgba(255, 255, 255, 0.08);
  color: #c084fc;
  border: 1px solid rgba(124, 58, 237, 0.3);
}

.btn-dashboard:hover {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-2px);
}
</style>
