<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface CollaboratorItem {
  username: string
  is_admin: boolean
  accessLevel: 1 | 2
}

const props = defineProps<{
  peers: CollaboratorItem[]
  loading: boolean
  includeAdmin: boolean
  incoming: boolean
}>()

const emit = defineEmits<{
  'update:includeAdmin': [value: boolean]
  'update:incoming': [value: boolean]
  reload: []
}>()

const { t } = useI18n()

const includeAdminModel = computed({
  get: () => props.includeAdmin,
  set: (value: boolean) => {
    emit('update:includeAdmin', value)
  }
})

const incomingModel = computed({
  get: () => props.incoming,
  set: (value: boolean) => {
    emit('update:incoming', value)
  }
})
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <div class="font-bold flex items-center justify-between gap-4 flex-wrap">
        <span class="flex items-center gap-2">
          <el-icon><User /></el-icon>
          {{ t('dashboard.collaborators') }}
        </span>
        <div class="flex items-center gap-2">
          <el-checkbox v-model="includeAdminModel" @change="emit('reload')">
            {{ t('dashboard.includeAdmin') }}
          </el-checkbox>
          <el-switch
            v-model="incomingModel"
            @change="emit('reload')"
            :active-text="t('dashboard.incomingAccess')"
            :inactive-text="t('dashboard.outcomingAccess')"
            inline-prompt
          />
        </div>
      </div>
    </template>
    <div class="flex flex-col gap-2" v-loading="loading">
      <div v-if="peers.length === 0" class="text-gray-500 text-center py-4">
        {{ t('dashboard.noCollaborators') }}
      </div>
      <div v-else class="space-y-2">
        <div v-for="peer in peers" :key="peer.username" class="flex items-center justify-between p-2 bg-gray-50 rounded">
          <div class="flex items-center gap-2">
            <el-avatar :size="32" class="bg-blue-500 shrink-0">{{ peer.username.charAt(0).toUpperCase() }}</el-avatar>
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
</template>
