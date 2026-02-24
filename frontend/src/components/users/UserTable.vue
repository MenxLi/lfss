<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { UserRecord } from '@/api'
import { formatBytes, formatDateTime } from '@/utils'

const { t } = useI18n()

defineProps<{
  users: UserRecord[]
  loading: boolean
  currentUsername?: string
  expireMap: Record<string, number | null | undefined>
  userStorageUsedMap: Record<string, number | undefined>
}>()

const emit = defineEmits<{
  (e: 'sort', payload: { prop: string, order: string }): void
  (e: 'edit', user: UserRecord): void
  (e: 'delete', user: UserRecord): void
  (e: 'peers', user: UserRecord): void
  (e: 'expire', user: UserRecord): void
}>()

const formatExpire = (seconds?: number | null) => {
  if (seconds === null || seconds === undefined) return t('users.never')
  if (seconds <= 0) return t('users.expired')
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return t('users.expireFmtDay', { days, hours })
  if (hours > 0) return t('users.expireFmtHour', { hours, minutes })
  return t('users.expireFmtMin', { minutes: Math.max(minutes, 1) })
}
</script>

<template>
  <div v-loading="loading">
    <el-table :data="users" style="width: 100%" @sort-change="emit('sort', $event)">
      <el-table-column prop="username" :label="t('users.username')" sortable="custom" min-width="180" />
      <el-table-column prop="is_admin" :label="t('users.role')" sortable="custom" width="120">
        <template #default="{ row }">
          <el-tag :type="row.is_admin ? 'danger' : 'success'">
            {{ row.is_admin ? t('dashboard.admin') : t('dashboard.user') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('users.storage')" min-width="140">
        <template #default="{ row }">
          <span>
            {{ row.max_storage ? formatBytes(row.max_storage) : t('dashboard.unlimited') }}
            <span class="text-gray-500"> ({{ t('users.usedStorage') }}: {{ formatBytes(userStorageUsedMap[row.username] ?? 0) }})</span>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" :label="t('users.createdAt')" sortable="custom" min-width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.create_time) }}
        </template>
      </el-table-column>
      <el-table-column prop="last_active" :label="t('users.lastActive')" sortable="custom" min-width="180">
        <template #default="{ row }">
          {{ row.last_active ? formatDateTime(row.last_active) : t('users.never') }}
        </template>
      </el-table-column>
      <el-table-column :label="t('users.expireIn')" min-width="150">
        <template #default="{ row }">
          <span :class="expireMap[row.username] !== null && expireMap[row.username] as any <= 0 ? 'text-red-500' : ''">
            {{ formatExpire(expireMap[row.username]) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column :label="t('users.actions')" width="260" fixed="right">
        <template #default="{ row }">
          <div class="flex items-center gap-0">
            <el-button size="medium" @click="emit('edit', row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button size="medium" type="primary" plain @click="emit('peers', row)">
              <el-icon><Connection /></el-icon>
            </el-button>
            <el-button size="medium" type="warning" plain @click="emit('expire', row)">
              <el-icon><Clock /></el-icon>
            </el-button>
            <el-button
              size="medium"
              type="danger"
              @click="emit('delete', row)"
              :disabled="row.username === currentUsername"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
