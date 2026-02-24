<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'
import Connector from '@/api'
import { useLogStore } from '@/store/logs'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const logStore = useLogStore()

const form = ref({
  endpoint: window.location.origin || 'http://localhost:8000',
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
  if (!form.value.endpoint || !form.value.token) return
  
  loading.value = true
  try {
    const conn = new Connector()
    conn.config = { endpoint: form.value.endpoint, token: form.value.token }
    
    const user = await conn.whoami()
    if (user && user.id !== 0) {
      userStore.setToken(form.value.token)
      localStorage.setItem('endpoint', form.value.endpoint)
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
  <div class="min-h-screen flex items-center justify-center bg-gray-100">
    <el-card class="w-96 shadow-lg">
      <template #header>
        <div class="text-center text-xl font-bold">{{ t('login.title') }}</div>
      </template>
      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="Endpoint">
          <el-input v-model="form.endpoint" :prefix-icon="'Link'" />
        </el-form-item>
        <el-form-item label="Token">
          <el-input v-model="form.token" type="password" show-password :prefix-icon="'Key'" />
        </el-form-item>
        <el-button type="primary" class="w-full mt-4" native-type="submit" :loading="loading">
          {{ t('login.submit') }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>
