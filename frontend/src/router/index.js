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
  ],
});

export default router;
