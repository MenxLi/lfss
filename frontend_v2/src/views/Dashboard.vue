<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import Connector from '@/api'
import type { UserRecord } from '@/api'
import UserManagement from '@/components/UserManagement.vue'

const userStore = useUserStore()
const { t } = useI18n()

const storageInfo = ref({
  used: 0,
  total: 0
})

const peers = ref<UserRecord[]>([])

const formatSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

onMounted(async () => {
  if (userStore.token) {
    const conn = new Connector()
    conn.config = { 
      endpoint: localStorage.getItem('endpoint') || window.location.origin, 
      token: userStore.token 
    }
    try {
      // Fetch storage info
      const res = await conn.fetcher.get('_api/user/storage')
      if (res.ok) {
        const data = await res.json()
        storageInfo.value.used = data.used
        storageInfo.value.total = data.quota
      }
      
      // Fetch peers
      peers.value = await conn.listPeers({ level: 1, incoming: false })
    } catch (e) {
      console.error(e)
    }
  }
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-800">
      {{ t('dashboard.welcome', { name: userStore.userInfo?.username }) }}
    </h1>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <el-card shadow="hover">
        <template #header>
          <div class="font-bold flex items-center gap-2">
            <el-icon><DataLine /></el-icon>
            {{ t('dashboard.storage') }}
          </div>
        </template>
        <div class="flex flex-col gap-4">
          <div class="flex justify-between items-center">
            <span class="text-gray-500">{{ t('dashboard.used') }}</span>
            <span class="font-medium text-lg">{{ formatSize(storageInfo.used) }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-gray-500">{{ t('dashboard.total') }}</span>
            <span class="font-medium text-lg">
              {{ userStore.userInfo?.max_storage ? formatSize(userStore.userInfo.max_storage) : t('dashboard.unlimited') }}
            </span>
          </div>
          <el-progress 
            v-if="userStore.userInfo?.max_storage"
            :percentage="Math.min(100, Math.round((storageInfo.used / userStore.userInfo.max_storage) * 100))" 
            :status="storageInfo.used > userStore.userInfo.max_storage * 0.9 ? 'exception' : ''"
          />
        </div>
      </el-card>

      <el-card shadow="hover">
        <template #header>
          <div class="font-bold flex items-center gap-2">
            <el-icon><User /></el-icon>
            {{ t('dashboard.collaborators') }}
          </div>
        </template>
        <div class="flex flex-col gap-2">
          <div v-if="peers.length === 0" class="text-gray-500 text-center py-4">
            {{ t('dashboard.noCollaborators') }}
          </div>
          <div v-else class="space-y-2">
            <div v-for="peer in peers" :key="peer.username" class="flex items-center justify-between p-2 bg-gray-50 rounded">
              <div class="flex items-center gap-2">
                <el-avatar :size="32" class="bg-blue-500">{{ peer.username.charAt(0).toUpperCase() }}</el-avatar>
                <span class="font-medium">{{ peer.username }}</span>
              </div>
              <el-tag size="small" type="info">
                {{ peer.is_admin ? t('dashboard.admin') : t('dashboard.user') }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <div v-if="userStore.userInfo?.is_admin" class="mt-6">
      <UserManagement />
    </div>
  </div>
</template>
