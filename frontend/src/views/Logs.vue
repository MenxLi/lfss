<script setup lang="ts">
import { useLogStore } from '@/store/logs'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils'

const logStore = useLogStore()
const { t } = useI18n()

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
  ElMessageBox.alert(message, t('logs.messageTitle'), {
    confirmButtonText: t('users.confirm')
  })
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-between items-center">
      <h1 class="text-2xl font-bold text-gray-800">{{ t('menu.logs') }}</h1>
      <el-button type="danger" @click="logStore.clearLogs">
        <el-icon class="mr-1"><Delete /></el-icon>
        {{ t('logs.clear') }}
      </el-button>
    </div>

    <el-card shadow="never" class="border border-slate-200/70">
      <el-table :data="logStore.logs" style="width: 100%" :default-sort="{ prop: 'timestamp', order: 'descending' }">
        <el-table-column prop="timestamp" :label="t('logs.time')" width="180" sortable>
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp, false) }}
          </template>
        </el-table-column>
        <el-table-column prop="type" :label="t('logs.type')" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.type)" size="small">
              {{ row.type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" :label="t('logs.message')" min-width="300">
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
          <el-empty :description="t('logs.empty')" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>
