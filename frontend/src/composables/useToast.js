/**
 * useToast — 블로킹 alert() 대체 토스트 알림 시스템
 * 사용법: const { showToast } = useToast();
 *         showToast('메시지', 'success'); // success | error | warning | info
 */
import { ref } from 'vue';

const toasts = ref([]);
let toastId = 0;

export function useToast() {
    const showToast = (message, type = 'info', duration = 3000) => {
        const id = ++toastId;
        toasts.value.push({ id, message, type, visible: true });

        setTimeout(() => {
            const idx = toasts.value.findIndex(t => t.id === id);
            if (idx !== -1) {
                toasts.value[idx].visible = false;
                setTimeout(() => {
                    toasts.value = toasts.value.filter(t => t.id !== id);
                }, 400);
            }
        }, duration);
    };

    return { toasts, showToast };
}
