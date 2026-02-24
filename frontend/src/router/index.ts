import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'
import Connector from '@/api'

const resolveRouterBase = () => {
    const path = window.location.pathname
    if (path === '/.panel' || path.startsWith('/.panel/')) {
        return '/.panel/'
    }
    return '/'
}

const router = createRouter({
    history: createWebHistory(resolveRouterBase()),
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

router.beforeEach(async (to) => {
    const userStore = useUserStore()

    if (to.name === 'Login') {
        return true
    }

    if (!userStore.token) {
        userStore.logout()
        return {
            name: 'Login',
            query: { redirect: to.fullPath }
        }
    }

    if (userStore.userInfo) {
        return true
    }

    const endpoint = (localStorage.getItem('endpoint') || '').trim()
    if (!endpoint) {
        userStore.logout()
        return {
            name: 'Login',
            query: { redirect: to.fullPath }
        }
    }

    try {
        const conn = new Connector()
        conn.config = { endpoint, token: userStore.token }
        const user = await conn.whoami()
        userStore.setUserInfo(user)
        return true
    } catch {
        userStore.logout()
        return {
            name: 'Login',
            query: { redirect: to.fullPath }
        }
    }
})

export default router
