<script setup>
import { RouterView } from "vue-router";
import Navbar from "./components/layout/Navbar.vue";
import ToastContainer from "./components/ToastContainer.vue";
</script>

<template>
  <div class="app-wrapper">
    <Navbar />
    <ToastContainer />
    <main>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.app-wrapper {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
  padding-top: var(
    --header-height
  ); /* Ensure content doesn't hide behind fixed header */
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
