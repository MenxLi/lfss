<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { sha256 } from 'js-sha256'
import type { UserRecord } from '@/api'
import { createConnector, formatBytes } from '@/utils'

const userStore = useUserStore()
const { t } = useI18n()

const storageInfo = ref({
  used: 0,
  total: 0
})

type CollaboratorRecord = UserRecord & { accessLevel: 1 | 2 }

const peers = ref<CollaboratorRecord[]>([])
const peerLoading = ref(false)
const includeAdmin = ref(false)
const incoming = ref(true)
const accountDialogVisible = ref(false)
const accountLoading = ref(false)
const passwordForm = ref({ password: '' })
const newTokenPreview = computed(() => {
  const username = userStore.userInfo?.username || ''
  if (!username || !passwordForm.value.password) return ''
  return sha256(`${username}:${passwordForm.value.password}`)
})

const filteredPeers = computed(() => {
  if (includeAdmin.value) {
    return peers.value
  }
  return peers.value.filter((peer) => !peer.is_admin)
})

const getConnector = () => {
  return createConnector(userStore.token)
}

const generateRandomPassword = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_'
  let password = ''
  for (let i = 0; i < 32; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  passwordForm.value.password = password
}

const copyCurrentToken = async () => {
  if (!userStore.token) return
  try {
    await navigator.clipboard.writeText(userStore.token)
    ElMessage.success(t('users.tokenCopied'))
  } catch {
    ElMessage.error(t('users.copyTokenFailed'))
  }
}

const updateMyPassword = async () => {
  if (!passwordForm.value.password) {
    ElMessage.warning(t('dashboard.passwordRequired'))
    return
  }
  accountLoading.value = true
  try {
    const conn = getConnector()
    const result = await conn.updateMyPassword(passwordForm.value.password)
    userStore.setToken(result.token)
    passwordForm.value.password = ''
    ElMessage.success(t('dashboard.passwordUpdated'))
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('dashboard.passwordUpdateFailed'))
  } finally {
    accountLoading.value = false
  }
}

const loadStorage = async () => {
  const conn = getConnector()
  const res = await conn.fetcher.get('_api/user/storage')
  if (!res.ok) {
    throw new Error(`Failed to load storage, status code: ${res.status}`)
  }
  const data = await res.json()
  storageInfo.value.used = data.used ?? 0
  storageInfo.value.total = data.quota ?? 0
}

const loadPeers = async () => {
  peerLoading.value = true
  try {
    const conn = getConnector()
    const [readPeers, writePeers] = await Promise.all([
      conn.listPeers({ level: 1, incoming: incoming.value, admin: includeAdmin.value }),
      conn.listPeers({ level: 2, incoming: incoming.value, admin: includeAdmin.value })
    ])

    const peerMap = new Map<string, CollaboratorRecord>()

    for (const user of readPeers) {
      peerMap.set(user.username, { ...user, accessLevel: 1 })
    }

    for (const user of writePeers) {
      peerMap.set(user.username, { ...user, accessLevel: 2 })
    }

    peers.value = [...peerMap.values()].sort((a, b) => a.username.localeCompare(b.username))
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('dashboard.failedToLoadCollaborators'))
  } finally {
    peerLoading.value = false
  }
}

onMounted(async () => {
  if (!userStore.token) {
    return
  }

  try {
    await loadStorage()
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('dashboard.failedToLoadStorage'))
  }

  await loadPeers()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <h1 class="text-2xl font-bold text-gray-800">
        {{ t('dashboard.welcome', { name: userStore.userInfo?.username }) }}
      </h1>
      <el-button plain @click="accountDialogVisible = true">
        <el-icon class="mr-1"><Key /></el-icon>
        {{ t('dashboard.accountSecurity') }}
      </el-button>
    </div>

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
            <span class="font-medium text-lg">{{ formatBytes(storageInfo.used) }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-gray-500">{{ t('dashboard.total') }}</span>
            <span class="font-medium text-lg">
              {{ storageInfo.total > 0 ? formatBytes(storageInfo.total) : t('dashboard.unlimited') }}
            </span>
          </div>
          <el-progress 
            v-if="storageInfo.total > 0"
            :percentage="Math.min(100, Math.round((storageInfo.used / storageInfo.total) * 100))" 
            :status="storageInfo.used > storageInfo.total * 0.9 ? 'exception' : ''"
          />
        </div>
      </el-card>

      <el-card shadow="hover">
        <template #header>
          <div class="font-bold flex items-center justify-between gap-4 flex-wrap">
            <span class="flex items-center gap-2">
              <el-icon><User /></el-icon>
              {{ t('dashboard.collaborators') }}
            </span>
            <div class="flex items-center gap-2">
              <el-checkbox v-model="includeAdmin" @change="loadPeers">
                {{ t('dashboard.includeAdmin') }}
              </el-checkbox>
              <el-switch v-model="incoming" @change="loadPeers" 
                :active-text="t('dashboard.incomingAccess')" 
                :inactive-text="t('dashboard.outcomingAccess')" 
                inline-prompt/>
            </div>
          </div>
        </template>
        <div class="flex flex-col gap-2" v-loading="peerLoading">
          <div v-if="filteredPeers.length === 0" class="text-gray-500 text-center py-4">
            {{ t('dashboard.noCollaborators') }}
          </div>
          <div v-else class="space-y-2">
            <div v-for="peer in filteredPeers" :key="peer.username" class="flex items-center justify-between p-2 bg-gray-50 rounded">
              <div class="flex items-center gap-2">
                <el-avatar :size="32" class="bg-blue-500">{{ peer.username.charAt(0).toUpperCase() }}</el-avatar>
                <span class="font-medium">{{ peer.username }}</span>
              </div>
              <div class="flex items-center gap-2">
                <el-tag size="small" type="info">
                  {{ peer.accessLevel === 2 ? t('dashboard.accessWrite') : t('dashboard.accessRead') }}
                </el-tag>
                <el-tag size="small" :type="peer.is_admin ? 'danger' : 'success'">
                  {{ peer.is_admin ? t('dashboard.admin') : t('dashboard.user') }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="accountDialogVisible"
      :title="t('dashboard.accountSecurity')"
      width="480px"
    >
      <div class="space-y-4">
        <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between gap-2">
          <span class="text-sm text-slate-600">{{ t('dashboard.currentToken') }}</span>
          <el-button link type="primary" @click="copyCurrentToken">{{ t('users.copyToken') }}</el-button>
        </div>

        <el-form :model="passwordForm" label-position="top">
          <el-form-item :label="t('dashboard.newPassword')">
            <div class="flex gap-2 w-full">
              <el-input v-model="passwordForm.password" type="password" show-password />
              <el-button @click="generateRandomPassword" :title="t('users.randomPassword')">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </el-form-item>
          <el-form-item v-if="newTokenPreview" :label="t('dashboard.newTokenPreview')">
            <div class="w-full text-xs text-slate-500 break-all">{{ newTokenPreview }}</div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="accountDialogVisible = false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="accountLoading" @click="updateMyPassword">
          {{ t('dashboard.updatePassword') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
