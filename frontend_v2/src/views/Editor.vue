<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Connector, { ApiUtils } from '@/api'
import { useUserStore } from '@/store/user'
import { useLogStore } from '@/store/logs'
import { Back, DocumentChecked } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const logStore = useLogStore()

const filePath = computed(() => {
  const path = route.query.path as string
  return path || ''
})

const content = ref('')
const originalContent = ref('')
const loading = ref(false)
const saving = ref(false)
const isNew = ref(false)

const conn = new Connector()
conn.config = { 
  endpoint: localStorage.getItem('endpoint') || window.location.origin, 
  token: userStore.token 
}

const loadFile = async () => {
  if (!filePath.value) {
    logStore.logMessage('error', 'No file specified')
    return
  }
  
  loading.value = true
  try {
    const meta = await conn.getMetadata(filePath.value)
    if (meta) {
      if ('file_size' in meta && meta.file_size > 5 * 1024 * 1024) {
        throw new Error('File too large (Max 5MB)')
      }
      const text = await conn.getText(filePath.value)
      content.value = text
      originalContent.value = text
      isNew.value = false
    } else {
      isNew.value = true
      content.value = ''
      originalContent.value = ''
    }
  } catch (e: any) {
    logStore.logMessage('error', e.message || 'Failed to load file')
  } finally {
    loading.value = false
  }
}

onMounted(loadFile)

const handleSave = async () => {
  if (!filePath.value) return
  
  saving.value = true
  try {
    await conn.putText(filePath.value, content.value, { conflict: 'overwrite' })
    originalContent.value = content.value
    isNew.value = false
    logStore.logMessage('success', 'Saved successfully')
  } catch (e: any) {
    logStore.logMessage('error', e.message || 'Failed to save file')
  } finally {
    saving.value = false
  }
}

const handleBack = () => {
  router.back()
}

const handleTab = (e: KeyboardEvent) => {
  if (e.key === 'Tab') {
    e.preventDefault()
    const target = e.target as HTMLTextAreaElement
    const start = target.selectionStart
    const end = target.selectionEnd
    content.value = content.value.substring(0, start) + '    ' + content.value.substring(end)
    
    // Need to wait for next tick to update selection
    setTimeout(() => {
      target.selectionStart = target.selectionEnd = start + 4
    }, 0)
  }
}

const isDirty = computed(() => content.value !== originalContent.value)
</script>

<template>
  <div class="h-[calc(100vh-120px)] flex flex-col space-y-4">
    <div class="flex justify-between items-center">
      <div class="flex items-center gap-4">
        <el-button @click="handleBack">
          <el-icon><Back /></el-icon>
        </el-button>
        <div class="text-lg font-medium flex items-center gap-2">
          {{ ApiUtils.decodePath(filePath) }}
          <el-tag v-if="isNew" size="small" type="success">New</el-tag>
          <el-tag v-if="isDirty" size="small" type="warning">Modified</el-tag>
        </div>
      </div>
      <el-button type="primary" @click="handleSave" :loading="saving" :disabled="!isDirty && !isNew">
        <el-icon class="mr-1"><DocumentChecked /></el-icon>
        Save
      </el-button>
    </div>

    <el-card shadow="never" class="flex-1 flex flex-col" body-class="flex-1 flex flex-col p-0" v-loading="loading">
      <textarea
        v-model="content"
        class="flex-1 w-full p-4 resize-none outline-none font-mono text-sm bg-transparent"
        @keydown="handleTab"
        :disabled="loading"
        placeholder="Enter file content here..."
      ></textarea>
    </el-card>
  </div>
</template>
