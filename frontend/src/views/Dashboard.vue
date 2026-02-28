<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { useLogStore } from '@/store/logs'
import { useI18n } from 'vue-i18n'
import { sha256 } from 'js-sha256'
import type { UserRecord } from '@/api'
import { createConnector } from '@/utils'
import DashboardMetricsPanel from '@/components/dashboard/DashboardMetricsPanel.vue'
import DashboardStorageCard from '@/components/dashboard/DashboardStorageCard.vue'
import DashboardCollaboratorsCard from '@/components/dashboard/DashboardCollaboratorsCard.vue'

const userStore = useUserStore()
const logStore = useLogStore()
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
    logStore.logMessage('success', t('users.tokenCopied'))
  } catch {
    logStore.logMessage('error', t('users.copyTokenFailed'))
  }
}

const updateMyPassword = async () => {
  if (!passwordForm.value.password) {
    logStore.logMessage('warning', t('dashboard.passwordRequired'))
    return
  }
  accountLoading.value = true
  try {
    const conn = getConnector()
    const result = await conn.setPassword(passwordForm.value.password)
    userStore.setToken(result.token)
    passwordForm.value.password = ''
    logStore.logMessage('success', t('dashboard.passwordUpdated'))
  } catch (e: unknown) {
    const err = e as Error
    logStore.logMessage('error', err.message || t('dashboard.passwordUpdateFailed'))
  } finally {
    accountLoading.value = false
  }
}

const loadStorage = async () => {
  const conn = getConnector()
  const data = await conn.getUserStorage()
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
    logStore.logMessage('error', err.message || t('dashboard.failedToLoadCollaborators'))
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
    logStore.logMessage('error', err.message || t('dashboard.failedToLoadStorage'))
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
      <DashboardStorageCard :used="storageInfo.used" :total="storageInfo.total" />

      <DashboardCollaboratorsCard
        :peers="filteredPeers"
        :loading="peerLoading"
        :include-admin="includeAdmin"
        :incoming="incoming"
        @update:include-admin="includeAdmin = $event"
        @update:incoming="incoming = $event"
        @reload="loadPeers"
      />
    </div>

    <DashboardMetricsPanel />

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
