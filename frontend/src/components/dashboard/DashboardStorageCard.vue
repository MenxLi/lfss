<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytes } from '@/utils'

const props = defineProps<{
  used: number
  total: number
}>()

const { t } = useI18n()

const progress = computed(() => {
  if (props.total <= 0) {
    return 0
  }
  return Math.min(100, Math.round((props.used / props.total) * 100))
})
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <div class="font-bold flex items-center gap-2">
        <el-icon><DataLine /></el-icon>
        {{ t('dashboard.storage') }}
      </div>
    </template>
    <div class="flex flex-col gap-4">
      <div class="flex justify-between items-center">
        <span class="text-gray-500">{{ t('dashboard.used') }}</span>
        <span class="font-medium text-lg">{{ formatBytes(used) }}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-gray-500">{{ t('dashboard.total') }}</span>
        <span class="font-medium text-lg">
          {{ total > 0 ? formatBytes(total) : t('dashboard.unlimited') }}
        </span>
      </div>
      <el-progress
        v-if="total > 0"
        :percentage="progress"
        :status="used > total * 0.9 ? 'exception' : ''"
      />
    </div>
  </el-card>
</template>
