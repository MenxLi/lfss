import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '@/store/user'

const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        {
            path: '/login',
            name: 'Login',
            component: () => import('@/views/Login.vue')
        },
        {
            path: '/',
            component: () => import('@/components/Layout.vue'),
            children: [
                {
                    path: '',
                    name: 'Dashboard',
                    component: () => import('@/views/Dashboard.vue')
                },
                {
                    path: 'files/:path(.*)*',
                    name: 'Files',
                    component: () => import('@/views/Files.vue')
                },
                {
                    path: 'editor',
                    name: 'Editor',
                    component: () => import('@/views/Editor.vue')
                },
                {
                    path: 'users',
                    name: 'Users',
                    component: () => import('@/views/UserManagement.vue')
                },
                {
                    path: 'logs',
                    name: 'Logs',
                    component: () => import('@/views/Logs.vue')
                }
            ]
        }
    ]
})

router.beforeEach((to, _from, next) => {
    const userStore = useUserStore()
    if (to.name !== 'Login' && !userStore.token) {
        next({ name: 'Login' })
    } else {
        next()
    }
})

export default router
