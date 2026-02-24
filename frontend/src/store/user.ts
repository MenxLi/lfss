import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserRecord } from '@/api'

export const useUserStore = defineStore('user', () => {
    const token = ref('')
    const userInfo = ref<UserRecord | null>(null)

    function setToken(newToken: string) {
        token.value = newToken
    }

    function setUserInfo(info: UserRecord | null) {
        userInfo.value = info
    }

    function logout() {
        token.value = ''
        userInfo.value = null
    }

    return { token, userInfo, setToken, setUserInfo, logout }
}, {
    persist: {
        key: 'lfss-user',
        pick: ['token'],
    }
})
