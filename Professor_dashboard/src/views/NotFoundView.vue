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
          🏠 대시보드로 돌아가기
        </router-link>
        <router-link to="/login" class="btn-login">
          🔐 로그인 페이지
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
  background: #f5f7fa;
  padding: 2rem;
}

.not-found-content {
  text-align: center;
  max-width: 500px;
  background: #fff;
  border-radius: 16px;
  padding: 3rem 2rem;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.error-code {
  font-size: 6rem;
  font-weight: 900;
  color: #7c3aed;
  line-height: 1;
  margin-bottom: 1rem;
}

.error-title {
  font-size: 1.4rem;
  color: #1e293b;
  margin-bottom: 0.75rem;
  font-weight: 600;
}

.error-description {
  color: #64748b;
  font-size: 0.95rem;
  margin-bottom: 2rem;
}

.error-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.btn-home, .btn-login {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.4rem;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s ease;
}

.btn-home {
  background: #7c3aed;
  color: #fff;
}

.btn-home:hover {
  background: #6d28d9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

.btn-login {
  background: #f1f5f9;
  color: #475569;
}

.btn-login:hover {
  background: #e2e8f0;
}
</style>
