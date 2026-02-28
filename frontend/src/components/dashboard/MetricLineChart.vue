<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

export interface MetricChartSeries {
  key: string
  label: string
  color: string
  data: number[]
}

const props = withDefaults(
  defineProps<{
    labels: string[]
    series: MetricChartSeries[]
    stacked?: boolean
    loading?: boolean
    emptyText?: string
    formatValue?: (value: number) => string
  }>(),
  {
    stacked: false,
    loading: false,
    emptyText: '',
    formatValue: (value: number) => value.toLocaleString()
  }
)

const chartWrapRef = ref<HTMLDivElement | null>(null)
const hoverIndex = ref<number | null>(null)
const lastHoverIndex = ref(0)
let chart: uPlot | null = null
let resizeObserver: ResizeObserver | null = null

const pointCount = computed(() => props.labels.length)

const resolveColor = (color: string) => {
  const input = color.trim()
  const cssVar = input.match(/^var\((--[^)]+)\)$/)
  if (!cssVar || !cssVar[1]) {
    return input
  }

  const varName = cssVar[1]
  const rootStyle = getComputedStyle(document.documentElement)
  const resolved = rootStyle.getPropertyValue(varName).trim()
  if (resolved) {
    return resolved
  }

  const fallback: Record<string, string> = {
    '--el-color-primary': '#409eff',
    '--el-color-success': '#67c23a',
    '--el-color-warning': '#e6a23c',
    '--el-color-danger': '#f56c6c',
    '--el-color-info': '#909399'
  }
  return fallback[varName] ?? '#409eff'
}

const toRgba = (color: string, alpha: number) => {
  const input = color.trim()
  if (input.startsWith('#')) {
    const hex = input.slice(1)
    if (hex.length === 3) {
      const r = Number.parseInt(`${hex[0]}${hex[0]}`, 16)
      const g = Number.parseInt(`${hex[1]}${hex[1]}`, 16)
      const b = Number.parseInt(`${hex[2]}${hex[2]}`, 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    }
    if (hex.length === 6) {
      const r = Number.parseInt(hex.slice(0, 2), 16)
      const g = Number.parseInt(hex.slice(2, 4), 16)
      const b = Number.parseInt(hex.slice(4, 6), 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    }
  }

  const rgb = input.match(/rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i)
  if (rgb) {
    return `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${alpha})`
  }

  return input
}

const normalizedSeries = computed(() => {
  const count = pointCount.value
  return props.series.map((item) => {
    const padded = item.data.slice(0, count)
    while (padded.length < count) {
      padded.push(0)
    }
    return {
      ...item,
      data: padded.map((value) => Math.max(0, Number(value) || 0))
    }
  })
})

const processedData = computed(() => {
  const count = pointCount.value
  const x = Array.from({ length: count }, (_, idx) => idx)

  return {
    rawSeries: normalizedSeries.value,
    plottedSeries: normalizedSeries.value,
    data: [x, ...normalizedSeries.value.map((item) => item.data)]
  }
})

const hasData = computed(() => {
  if (props.labels.length === 0 || props.series.length === 0) {
    return false
  }
  return normalizedSeries.value.some((item) => item.data.some((value) => value > 0))
})

const hoveredRows = computed(() => {
  if (processedData.value.rawSeries.length === 0 || pointCount.value === 0) {
    return [] as Array<{ key: string; label: string; color: string; value: number }>
  }

  const index = hoverIndex.value ?? lastHoverIndex.value

  return processedData.value.rawSeries.map((series) => ({
    key: series.key,
    label: series.label,
    color: series.color,
    value: series.data[index] ?? 0
  }))
})

const hoveredLabel = computed(() => {
  if (pointCount.value === 0) {
    return ''
  }
  const index = hoverIndex.value ?? lastHoverIndex.value
  return props.labels[index] ?? ''
})

const destroyChart = () => {
  if (chart) {
    chart.destroy()
    chart = null
  }
  hoverIndex.value = null
}

const buildOptions = (width: number): uPlot.Options => {
  const xAxisColor = '#94a3b8'
  const yAxisColor = '#334155'
  const gridColor = '#e2e8f0'
  const splinePathBuilder = (uPlot as unknown as { paths?: { spline?: () => any } }).paths?.spline?.()

  const series: uPlot.Series[] = [
    { label: 'x' },
    ...processedData.value.plottedSeries.map((item) => {
      const solidColor = resolveColor(item.color)
      return {
        label: item.label,
        stroke: toRgba(solidColor, 0.68),
        width: 2.4,
        points: { show: false },
        paths: pointCount.value >= 3 ? splinePathBuilder : undefined
      }
    })
  ]

  const hooks: uPlot.Options['hooks'] = {
    setCursor: [
      (u) => {
        if (typeof u.cursor.idx === 'number') {
          hoverIndex.value = u.cursor.idx
          lastHoverIndex.value = u.cursor.idx
        } else {
          hoverIndex.value = null
        }
      }
    ]
  }

  return {
    width,
    height: 300,
    series,
    axes: [
      {
        stroke: xAxisColor,
        grid: {
          stroke: gridColor,
          width: 1
        },
        values: (_u, splits) =>
          splits.map((value) => {
            const index = Math.round(Number(value))
            return props.labels[index] ?? ''
          }),
        space: 72,
        size: 42,
        font: '11px sans-serif'
      },
      {
        stroke: yAxisColor,
        grid: {
          stroke: gridColor,
          width: 1.2
        },
        values: (_u, splits) => splits.map((value) => props.formatValue(Number(value))),
        size: 56,
        font: '11px sans-serif'
      }
    ],
    scales: {
      x: {
        time: false
      }
    },
    legend: {
      show: false
    },
    cursor: {
      drag: { x: false, y: false },
      points: {
        size: 7,
        stroke: '#1f2937',
        fill: '#ffffff',
        width: 2
      }
    },
    hooks
  }
}

const renderChart = async () => {
  destroyChart()

  if (props.loading || !hasData.value) {
    return
  }

  await nextTick()

  if (!chartWrapRef.value) {
    return
  }

  const width = Math.max(320, chartWrapRef.value.clientWidth)
  lastHoverIndex.value = Math.max(pointCount.value - 1, 0)
  chart = new uPlot(buildOptions(width), processedData.value.data as uPlot.AlignedData, chartWrapRef.value)
}

onMounted(() => {
  renderChart()
  requestAnimationFrame(() => {
    renderChart()
  })

  if (chartWrapRef.value) {
    resizeObserver = new ResizeObserver(() => {
      renderChart()
    })
    resizeObserver.observe(chartWrapRef.value)
  }
})

watch(
  () => [props.labels, props.series, props.stacked, props.loading],
  () => {
    renderChart()
  },
  { deep: true, flush: 'post' }
)

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  destroyChart()
})
</script>

<template>
  <div class="w-full">
    <div
      v-if="loading"
      class="h-[300px] rounded-xl border border-slate-200 bg-white/60 flex items-center justify-center text-slate-500"
    >
      <el-icon class="is-loading mr-2"><Loading /></el-icon>
      <span>{{ emptyText }}</span>
    </div>
    <div
      v-else-if="!hasData"
      class="h-[300px] rounded-xl border border-slate-200 bg-white/60 flex items-center justify-center text-slate-500"
    >
      {{ emptyText }}
    </div>
    <div v-else class="space-y-3">
      <div ref="chartWrapRef" class="w-full h-[300px]" />
      <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span class="font-medium text-slate-700">{{ hoveredLabel }}</span>
        <span
          v-for="row in hoveredRows"
          :key="row.key"
          class="inline-flex items-center gap-1"
        >
          <span class="inline-block h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: row.color }" />
          <span>{{ row.label }}: {{ formatValue(row.value) }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.u-over) {
  border-radius: 0.75rem;
}

:deep(.u-axis text) {
  fill: #64748b;
}

:deep(.u-y text) {
  fill: #334155;
  font-weight: 600;
}
</style>
