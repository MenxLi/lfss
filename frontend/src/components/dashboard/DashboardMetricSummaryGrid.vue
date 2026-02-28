<script setup lang="ts">
export interface MetricSummaryItem {
  key: string
  label: string
  value: string
}

defineProps<{
  items: MetricSummaryItem[]
}>()
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
    <el-card v-for="item in items" :key="item.key" shadow="never" class="!rounded-lg border border-slate-200/70">
      <div class="text-xs text-slate-500">{{ item.label }}</div>
      <div class="text-lg font-semibold text-slate-800 mt-1 break-all">{{ item.value }}</div>
    </el-card>
  </div>
</template>
