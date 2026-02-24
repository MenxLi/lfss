<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import { createConnector } from '@/utils'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t, locale } = useI18n()

const isMobile = ref(false)
const isCollapse = ref(false)
const menuItems = computed(() => {
  const items = [
    { index: '/', icon: 'Odometer', label: t('menu.dashboard') },
    { index: '/files', icon: 'Folder', label: t('menu.files') },
    { index: '/logs', icon: 'Document', label: t('menu.logs') }
  ]
  if (userStore.userInfo?.is_admin) {
    items.splice(2, 0, { index: '/users', icon: 'User', label: t('menu.users') })
  }
  return items
})

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  isCollapse.value = isMobile.value
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  if (userStore.token && !userStore.userInfo) {
    const conn = createConnector(userStore.token)
    try {
      const user = await conn.whoami()
      userStore.setUserInfo(user)
    } catch (e) {
      console.error(e)
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

const activeMenu = computed(() => {
  if (route.path.startsWith('/files')) return '/files'
  return route.path
})

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}

const toggleLocale = () => {
  locale.value = locale.value === 'en' ? 'zh' : 'en'
  localStorage.setItem('locale', locale.value)
}
</script>

<template>
  <el-container class="h-screen bg-slate-100">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="bg-slate-900 text-white flex flex-col transition-all duration-300">
      <div class="p-4 text-xl font-bold text-center border-b border-slate-700/80 flex items-center justify-center h-[60px]">
        <span v-if="!isCollapse">LFSS</span>
        <el-icon v-else><Monitor /></el-icon>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="flex-1 border-none"
        background-color="#0f172a"
        style="border-right: none"
        text-color="#fff"
        active-text-color="#409eff"
        :collapse="isCollapse"
        router
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.label }}</template>
        </el-menu-item>
      </el-menu>
      <div class="p-4 border-t border-slate-700/80 flex flex-col gap-2 items-center">
        <el-button link @click="toggleLocale" class="text-slate-300 hover:text-white w-full">
          {{ locale === 'en' ? '中文' : 'EN' }}
        </el-button>
        <el-button link @click="handleLogout" class="text-slate-300 hover:text-white w-full">
          <el-icon><SwitchButton /></el-icon>
          <span v-if="!isCollapse" class="ml-2">{{ t('menu.logout') }}</span>
        </el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="bg-white flex items-center px-4 h-[60px] border-b border-slate-200/80">
        <el-button link @click="isCollapse = !isCollapse">
          <el-icon size="20"><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
        </el-button>
      </el-header>
      <el-main class="p-4 md:p-6 overflow-auto">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
