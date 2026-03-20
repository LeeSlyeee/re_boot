import { createRouter, createWebHistory } from "vue-router";
import HomeView from "../views/HomeView.vue";

/**
 * 동적 import 실패 시 자동 새로고침 (배포 후 캐시 불일치 대응)
 * 이전 빌드의 chunk 해시를 참조하는 브라우저가 404를 맞으면,
 * 한 번만 새로고침하여 최신 index.html을 받아오도록 처리.
 */
function lazyLoad(importFn) {
  return () =>
    importFn().catch((err) => {
      // "Failed to fetch dynamically imported module" 에러인 경우
      const isChunkError =
        err.message?.includes("dynamically imported module") ||
        err.message?.includes("Failed to fetch") ||
        err.message?.includes("Loading chunk");

      if (isChunkError) {
        const lastReload = sessionStorage.getItem("chunk_reload");
        const now = Date.now();
        // 무한 리로드 방지: 10초 이내 중복 리로드 차단
        if (!lastReload || now - Number(lastReload) > 10000) {
          sessionStorage.setItem("chunk_reload", String(now));
          window.location.reload();
          return;
        }
      }
      throw err; // 다른 에러는 그대로 전파
    });
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
    },
    {
      path: '/auth',
      name: 'auth',
      component: lazyLoad(() => import('../views/AuthView.vue'))
    },
    {
      path: '/learning',
      name: 'learning',
      component: lazyLoad(() => import('../views/LearningView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: lazyLoad(() => import('../views/DashboardView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: lazyLoad(() => import('../views/PortfolioView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/interview/setup',
      name: 'interview-setup',
      component: lazyLoad(() => import('../views/InterviewSetupView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/interview/:id',
      name: 'interview-chat',
      component: lazyLoad(() => import('../views/InterviewChatView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/placement',
      name: 'placement',
      component: lazyLoad(() => import('../views/PlacementView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/gapmap',
      name: 'gapmap',
      component: lazyLoad(() => import('../views/GapMapView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/ai-chat',
      name: 'ai-chat',
      component: lazyLoad(() => import('../views/AIChatView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/curriculum',
      name: 'curriculum',
      component: lazyLoad(() => import('../views/CurriculumView.vue')),
      meta: { requiresAuth: true }
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: lazyLoad(() => import('../views/OnboardingView.vue')),
      meta: { requiresAuth: true }
    },
    // 404 Catch-all
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: lazyLoad(() => import('../views/NotFoundView.vue'))
    },
  ],
});

// Navigation Guard: 로그인 필수 라우트 보호
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token');
  if (to.meta.requiresAuth && !token) {
    next({ name: 'auth', query: { redirect: to.fullPath } });
  } else {
    next();
  }
});

export default router;
