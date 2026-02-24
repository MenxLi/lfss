<script setup lang="ts">
import { useLogStore } from '@/store/logs'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'

const logStore = useLogStore()
const { t } = useI18n()

const formatDate = (timestamp: number) => {
  return new Date(timestamp).toLocaleString()
}

const getTypeColor = (type: string) => {
  switch (type) {
    case 'success': return 'success'
    case 'warning': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
}

const MESSAGE_PREVIEW_LENGTH = 120

const getMessagePreview = (message: string) => {
  if (message.length <= MESSAGE_PREVIEW_LENGTH) {
    return message
  }
  return `${message.slice(0, MESSAGE_PREVIEW_LENGTH)}...`
}

const showFullMessage = (message: string) => {
  ElMessageBox.alert(message, 'Log Message', {
    confirmButtonText: 'OK'
  })
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-between items-center">
      <h1 class="text-2xl font-bold text-gray-800">{{ t('menu.logs') }}</h1>
      <el-button type="danger" @click="logStore.clearLogs">
        <el-icon class="mr-1"><Delete /></el-icon>
        Clear Logs
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="logStore.logs" style="width: 100%" :default-sort="{ prop: 'timestamp', order: 'descending' }">
        <el-table-column prop="timestamp" label="Time" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="type" label="Type" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.type)" size="small">
              {{ row.type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="Message" min-width="300">
          <template #default="{ row }">
            <span
              class="block truncate cursor-pointer hover:text-blue-500"
              :title="row.message"
              @click="showFullMessage(row.message)"
            >
              {{ getMessagePreview(row.message) }}
            </span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="No logs for this session" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>
