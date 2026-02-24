<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import Connector from '@/api'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t, locale } = useI18n()

const isMobile = ref(false)
const isCollapse = ref(false)

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  isCollapse.value = isMobile.value
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  if (userStore.token && !userStore.userInfo) {
    const conn = new Connector()
    conn.config = { 
      endpoint: localStorage.getItem('endpoint') || window.location.origin, 
      token: userStore.token 
    }
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
  <el-container class="h-screen">
    <el-aside :width="isCollapse ? '64px' : '200px'" class="bg-gray-800 text-white flex flex-col transition-all duration-300">
      <div class="p-4 text-xl font-bold text-center border-b border-gray-700 flex items-center justify-center h-[60px]">
        <span v-if="!isCollapse">LFSS</span>
        <el-icon v-else><Monitor /></el-icon>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="flex-1 border-none"
        background-color="#1f2937"
        text-color="#fff"
        active-text-color="#409eff"
        :collapse="isCollapse"
        router
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <template #title>{{ t('menu.dashboard') }}</template>
        </el-menu-item>
        <el-menu-item index="/files">
          <el-icon><Folder /></el-icon>
          <template #title>{{ t('menu.files') }}</template>
        </el-menu-item>
        <el-menu-item index="/users" v-if="userStore.userInfo?.is_admin">
          <el-icon><User /></el-icon>
          <template #title>{{ t('menu.users') }}</template>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <template #title>{{ t('menu.logs') }}</template>
        </el-menu-item>
      </el-menu>
      <div class="p-4 border-t border-gray-700 flex flex-col gap-2 items-center">
        <el-button link @click="toggleLocale" class="text-gray-300 hover:text-white w-full">
          {{ locale === 'en' ? '中文' : 'EN' }}
        </el-button>
        <el-button link @click="handleLogout" class="text-gray-300 hover:text-white w-full">
          <el-icon><SwitchButton /></el-icon>
          <span v-if="!isCollapse" class="ml-2">{{ t('menu.logout') }}</span>
        </el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="bg-white border-b flex items-center px-4 h-[60px]">
        <el-button link @click="isCollapse = !isCollapse">
          <el-icon size="20"><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
        </el-button>
      </el-header>
      <el-main class="bg-gray-100 p-4 md:p-6 overflow-auto">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
