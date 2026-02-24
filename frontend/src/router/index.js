import { createRouter, createWebHistory } from "vue-router";
import HomeView from "../views/HomeView.vue";

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
      component: () => import('../views/AuthView.vue')
    },
    {
      path: '/learning',
      name: 'learning',
      component: () => import('../views/LearningView.vue')
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue')
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: () => import('../views/PortfolioView.vue')
    },
    {
      path: '/interview/setup',
      name: 'interview-setup',
      component: () => import('../views/InterviewSetupView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/interview/:id',
      name: 'interview-chat',
      component: () => import('../views/InterviewChatView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/placement',
      name: 'placement',
      component: () => import('../views/PlacementView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/gapmap',
      name: 'gapmap',
      component: () => import('../views/GapMapView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/ai-chat',
      name: 'ai-chat',
      component: () => import('../views/AIChatView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/curriculum',
      name: 'curriculum',
      component: () => import('../views/CurriculumView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: () => import('../views/OnboardingView.vue'),
      meta: { requiresAuth: true }
    },
  ],
});

export default router;
