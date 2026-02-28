<script setup lang="ts">
import type { MetricChartSeries } from './MetricLineChart.vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  series: MetricChartSeries[]
  hiddenKeys: string[]
}>()

const emit = defineEmits<{
  toggle: [key: string]
  reset: []
}>()

const { t } = useI18n()

const isHidden = (key: string) => props.hiddenKeys.includes(key)

const tagStyle = (key: string) => {
  if (isHidden(key)) {
    return {
      '--el-tag-bg-color': '#ffffff',
      '--el-tag-border-color': '#e2e8f0',
      '--el-tag-text-color': '#94a3b8'
    }
  }

  return {
    '--el-tag-bg-color': '#f1f5f9',
    '--el-tag-border-color': '#cbd5e1',
    '--el-tag-text-color': '#334155'
  }
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex flex-wrap gap-2">
      <el-tag
        v-for="item in series"
        :key="item.key"
        effect="plain"
        round
        class="cursor-pointer select-none transition-colors"
        :style="tagStyle(item.key)"
        @click="emit('toggle', item.key)"
      >
        <span class="inline-flex items-center gap-1">
          <span class="inline-block h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: item.color, opacity: isHidden(item.key) ? 0.45 : 1 }" />
          {{ item.label }}
        </span>
      </el-tag>
      <el-button text size="small" @click="emit('reset')">
        {{ t('dashboard.metrics.showAll') }}
      </el-button>
    </div>
    <div class="text-xs text-slate-500">
      {{ t('dashboard.metrics.clickToToggle') }}
    </div>
  </div>
</template>
