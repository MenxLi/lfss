<script setup lang="ts">
import { useLogStore } from '@/store/logs'
import { useI18n } from 'vue-i18n'

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
        <el-table-column prop="message" label="Message" />
        <template #empty>
          <el-empty description="No logs for this session" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>
