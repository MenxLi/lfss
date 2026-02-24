<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { UserRecord } from '@/api'
import { formatBytes, formatDateTime } from '@/utils'

const { t } = useI18n()

defineProps<{
  users: UserRecord[]
  loading: boolean
  currentUsername?: string
}>()

const emit = defineEmits<{
  (e: 'sort', payload: { prop: string, order: string }): void
  (e: 'edit', user: UserRecord): void
  (e: 'delete', user: UserRecord): void
  (e: 'peers', user: UserRecord): void
}>()
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
          {{ row.max_storage ? formatBytes(row.max_storage) : t('dashboard.unlimited') }}
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
      <el-table-column :label="t('users.actions')" width="220" fixed="right">
        <template #default="{ row }">
          <div class="flex items-center gap-1">
            <el-button size="small" @click="emit('edit', row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button size="small" type="primary" plain @click="emit('peers', row)">
              <el-icon><Connection /></el-icon>
            </el-button>
            <el-button
              size="small"
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
