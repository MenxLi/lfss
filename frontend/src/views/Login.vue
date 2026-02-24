<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import Connector from '@/api'
import { useLogStore } from '@/store/logs'
import { resolveEndpoint } from '@/utils'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const logStore = useLogStore()

const form = ref({
  endpoint: resolveEndpoint(),
  token: ''
})

const loading = ref(false)

onMounted(() => {
  const savedEndpoint = localStorage.getItem('endpoint')
  if (savedEndpoint) {
    form.value.endpoint = savedEndpoint
  }
})

const handleLogin = async () => {
  const endpoint = form.value.endpoint.trim()
  const token = form.value.token.trim()
  if (!endpoint || !token) return
  
  loading.value = true
  try {
    const conn = new Connector()
    conn.config = { endpoint, token }
    
    const user = await conn.whoami()
    if (user && user.id !== 0) {
      userStore.setToken(token)
      localStorage.setItem('endpoint', endpoint)
      userStore.setUserInfo(user)
      logStore.logMessage('success', t('login.success'))
      router.push('/')
    } else {
      logStore.logMessage('error', t('login.failed'))
    }
  } catch (e) {
    logStore.logMessage('error', t('login.failed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-100 to-slate-200 p-4">
    <el-card class="w-full max-w-md border border-slate-200/70">
      <template #header>
        <div class="text-center text-xl font-bold tracking-tight">{{ t('login.title') }}</div>
      </template>
      <el-form @submit.prevent="handleLogin" label-position="top" class="space-y-1">
        <el-form-item label="Endpoint">
          <el-input v-model="form.endpoint" placeholder="https://example.com">
            <template #prefix><el-icon><Link /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="Token">
          <el-input v-model="form.token" type="password" show-password>
            <template #prefix><el-icon><Key /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" class="w-full mt-2" native-type="submit" :loading="loading" :disabled="!form.endpoint.trim() || !form.token.trim()">
          {{ t('login.submit') }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>
