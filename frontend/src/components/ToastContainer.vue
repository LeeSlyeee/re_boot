<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast-item', `toast-${toast.type}`, { 'toast-hide': !toast.visible }]"
        >
          <span class="toast-icon">
            {{ toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : toast.type === 'warning' ? '⚠️' : 'ℹ️' }}
          </span>
          <span class="toast-message">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/useToast';
const { toasts } = useToast();
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  backdrop-filter: blur(10px);
  pointer-events: auto;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  max-width: 400px;
}

.toast-success {
  background: rgba(16, 185, 129, 0.95);
  color: #fff;
}
.toast-error {
  background: rgba(239, 68, 68, 0.95);
  color: #fff;
}
.toast-warning {
  background: rgba(245, 158, 11, 0.95);
  color: #fff;
}
.toast-info {
  background: rgba(59, 130, 246, 0.95);
  color: #fff;
}

.toast-hide {
  opacity: 0;
  transform: translateX(100%);
}

.toast-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.toast-message {
  line-height: 1.4;
}

.toast-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.toast-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
