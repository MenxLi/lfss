<script setup lang="ts">
import type { HttpTraffic } from '@/api'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLogStore } from '@/store/logs'
import { useUserStore } from '@/store/user'
import { usePreferenceStore } from '@/store/preferences'
import { createConnector, formatBytes } from '@/utils'
import MetricLineChart, { type MetricChartSeries } from './MetricLineChart.vue'
import DashboardMetricLegend from './DashboardMetricLegend.vue'
import DashboardMetricSummaryGrid, { type MetricSummaryItem } from './DashboardMetricSummaryGrid.vue'

type MetricWindow = 'hour' | 'day' | 'week'
type MetricMode = 'requests' | 'throughput'

const { t, locale } = useI18n()
const userStore = useUserStore()
const logStore = useLogStore()
const preferenceStore = usePreferenceStore()

const selectedWindow = computed<MetricWindow>({
  get: () => preferenceStore.dashboardMetricWindow,
  set: (value) => {
    preferenceStore.dashboardMetricWindow = value
  }
})

const selectedMode = computed<MetricMode>({
  get: () => preferenceStore.dashboardMetricMode,
  set: (value) => {
    preferenceStore.dashboardMetricMode = value
  }
})

const loading = ref(false)
const traffic = ref<HttpTraffic[]>([])

const windowOptions = computed(() => [
  { value: 'hour' as const, label: t('dashboard.metrics.windowHour') },
  { value: 'day' as const, label: t('dashboard.metrics.windowDay') },
  { value: 'week' as const, label: t('dashboard.metrics.windowWeek') }
])

const modeOptions = computed(() => [
  { value: 'requests' as const, label: t('dashboard.metrics.modeRequests') },
  { value: 'throughput' as const, label: t('dashboard.metrics.modeThroughput') }
])

const rangeConfig = computed(() => {
  if (selectedWindow.value === 'hour') {
    return {
      resolution: 'minute' as const,
      count: 60,
      stepSeconds: 60
    }
  }

  if (selectedWindow.value === 'week') {
    return {
      resolution: 'day' as const,
      count: 7,
      stepSeconds: 86400
    }
  }

  return {
    resolution: 'hour' as const,
    count: 24,
    stepSeconds: 3600
  }
})

const isAdmin = computed(() => !!userStore.userInfo?.is_admin)

const buildStartTime = () => {
  const step = rangeConfig.value.stepSeconds
  const now = Math.floor(Date.now() / 1000)
  const currentWindowStart = Math.floor(now / step) * step
  return currentWindowStart - (rangeConfig.value.count - 1) * step
}

const formatLabel = (timestampSec: number) => {
  const d = new Date(timestampSec * 1000)
  if (selectedWindow.value === 'hour') {
    return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  if (selectedWindow.value === 'day') {
    return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return d.toLocaleDateString(locale.value, { month: '2-digit', day: '2-digit' })
}

const labels = computed(() => {
  const startTime = buildStartTime()
  const step = rangeConfig.value.stepSeconds
  return Array.from({ length: rangeConfig.value.count }, (_, idx) => formatLabel(startTime + idx * step))
})

const requestTotals = computed(() => traffic.value.map((item) => item.total_count ?? 0))

const requestSeries = computed<MetricChartSeries[]>(() => {
  if (!isAdmin.value) {
    return [
      {
        key: 'requests-total',
        label: t('dashboard.metrics.totalRequests'),
        color: 'var(--el-color-primary)',
        data: requestTotals.value
      }
    ]
  }

  return [
    {
      key: 'status-1xx',
      label: '1xx',
      color: 'var(--el-color-info)',
      data: traffic.value.map((item) => item.code_100_count ?? 0)
    },
    {
      key: 'status-2xx',
      label: '2xx',
      color: 'var(--el-color-success)',
      data: traffic.value.map((item) => item.code_200_count ?? 0)
    },
    {
      key: 'status-3xx',
      label: '3xx',
      color: 'var(--el-color-primary)',
      data: traffic.value.map((item) => item.code_300_count ?? 0)
    },
    {
      key: 'status-4xx',
      label: '4xx',
      color: 'var(--el-color-warning)',
      data: traffic.value.map((item) => item.code_400_count ?? 0)
    },
    {
      key: 'status-5xx',
      label: '5xx',
      color: 'var(--el-color-danger)',
      data: traffic.value.map((item) => item.code_500_count ?? 0)
    }
  ]
})

const throughputSeries = computed<MetricChartSeries[]>(() => [
  {
    key: 'bytes-in',
    label: t('dashboard.metrics.inputBytes'),
    color: 'var(--el-color-success)',
    data: traffic.value.map((item) => item.bytes_in ?? 0)
  },
  {
    key: 'bytes-out',
    label: t('dashboard.metrics.outputBytes'),
    color: 'var(--el-color-primary)',
    data: traffic.value.map((item) => item.bytes_out ?? 0)
  }
])

const activeSeries = computed(() => (selectedMode.value === 'requests' ? requestSeries.value : throughputSeries.value))

const hiddenSeriesKeys = computed<string[]>({
  get: () =>
    selectedMode.value === 'requests'
      ? preferenceStore.dashboardHiddenRequestSeries
      : preferenceStore.dashboardHiddenThroughputSeries,
  set: (value) => {
    if (selectedMode.value === 'requests') {
      preferenceStore.dashboardHiddenRequestSeries = value
      return
    }
    preferenceStore.dashboardHiddenThroughputSeries = value
  }
})

const visibleSeries = computed(() => activeSeries.value.filter((item) => !hiddenSeriesKeys.value.includes(item.key)))

const summaryItems = computed<MetricSummaryItem[]>(() => {
  const windows = Math.max(traffic.value.length, 1)

  if (selectedMode.value === 'requests') {
    const total = requestTotals.value.reduce((acc, cur) => acc + cur, 0)
    const peak = Math.max(0, ...requestTotals.value)
    const avg = total / windows

    if (isAdmin.value) {
      const successCount = traffic.value.reduce((acc, item) => acc + (item.code_200_count ?? 0), 0)
      const successRate = total > 0 ? (successCount / total) * 100 : 0
      return [
        {
          key: 'total',
          label: t('dashboard.metrics.summaryTotalRequests'),
          value: total.toLocaleString()
        },
        {
          key: 'avg',
          label: t('dashboard.metrics.summaryAvgPerWindow'),
          value: avg.toFixed(1)
        },
        {
          key: 'peak',
          label: t('dashboard.metrics.summaryPeakWindow'),
          value: peak.toLocaleString()
        },
        {
          key: 'success-rate',
          label: t('dashboard.metrics.summarySuccessRate'),
          value: `${successRate.toFixed(1)}%`
        }
      ]
    }

    return [
      {
        key: 'total',
        label: t('dashboard.metrics.summaryTotalRequests'),
        value: total.toLocaleString()
      },
      {
        key: 'avg',
        label: t('dashboard.metrics.summaryAvgPerWindow'),
        value: avg.toFixed(1)
      },
      {
        key: 'peak',
        label: t('dashboard.metrics.summaryPeakWindow'),
        value: peak.toLocaleString()
      }
    ]
  }

  const inData = throughputSeries.value[0]?.data ?? []
  const outData = throughputSeries.value[1]?.data ?? []
  const totalIn = inData.reduce((acc, cur) => acc + cur, 0)
  const totalOut = outData.reduce((acc, cur) => acc + cur, 0)
  const avgPerWindow = (totalIn + totalOut) / windows
  const peakIn = Math.max(0, ...inData)
  const peakOut = Math.max(0, ...outData)

  return [
    {
      key: 'total-in',
      label: t('dashboard.metrics.summaryTotalInput'),
      value: formatBytes(totalIn)
    },
    {
      key: 'total-out',
      label: t('dashboard.metrics.summaryTotalOutput'),
      value: formatBytes(totalOut)
    },
    {
      key: 'avg',
      label: t('dashboard.metrics.summaryAvgThroughput'),
      value: formatBytes(avgPerWindow)
    },
    {
      key: 'peak',
      label: t('dashboard.metrics.summaryPeakInOut'),
      value: `${formatBytes(peakIn)} / ${formatBytes(peakOut)}`
    }
  ]
})

const toggleSeriesVisibility = (key: string) => {
  const isCurrentlyHidden = hiddenSeriesKeys.value.includes(key)
  if (isCurrentlyHidden) {
    hiddenSeriesKeys.value = hiddenSeriesKeys.value.filter((item) => item !== key)
    return
  }

  const visibleCount = activeSeries.value.length - hiddenSeriesKeys.value.length
  if (visibleCount <= 1) {
    logStore.logMessage('warning', t('dashboard.metrics.keepOneVisible'))
    return
  }

  hiddenSeriesKeys.value = [...hiddenSeriesKeys.value, key]
}

const resetSeriesVisibility = () => {
  hiddenSeriesKeys.value = []
}

watch(activeSeries, (series) => {
  const keySet = new Set(series.map((item) => item.key))
  hiddenSeriesKeys.value = hiddenSeriesKeys.value.filter((key) => keySet.has(key))
})

watch(
  () => [activeSeries.value.length, visibleSeries.value.length],
  () => {
    if (activeSeries.value.length > 0 && visibleSeries.value.length === 0) {
      hiddenSeriesKeys.value = []
    }
  }
)

const loadMetrics = async () => {
  if (!userStore.token) {
    return
  }

  loading.value = true
  try {
    const conn = createConnector(userStore.token)
    const startTime = buildStartTime()
    traffic.value = await conn.queryHttpTraffic(rangeConfig.value.resolution, startTime, rangeConfig.value.count)
  } catch (e: unknown) {
    const err = e as Error
    logStore.logMessage('error', err.message || t('dashboard.metrics.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch([selectedWindow, () => userStore.token], () => {
  loadMetrics()
})

onMounted(() => {
  loadMetrics()
})
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="font-bold flex items-center gap-2">
          <el-icon><Histogram /></el-icon>
          {{ t('dashboard.metrics.title') }}
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <el-radio-group v-model="selectedMode" size="small">
            <el-radio-button
              v-for="option in modeOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="selectedWindow" size="small">
            <el-radio-button
              v-for="option in windowOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
          <el-button :loading="loading" @click="loadMetrics">
            <el-icon class="mr-1"><Refresh /></el-icon>
            {{ t('users.refresh') }}
          </el-button>
        </div>
      </div>
      <div class="mt-2 text-xs text-slate-500">
        <el-icon class="mr-1"><InfoFilled /></el-icon>
        {{ t('dashboard.metrics.scopeHint') }}
      </div>
    </template>

    <div class="space-y-4">
      <DashboardMetricLegend
        :series="activeSeries"
        :hidden-keys="hiddenSeriesKeys"
        @toggle="toggleSeriesVisibility"
        @reset="resetSeriesVisibility"
      />

      <MetricLineChart
        :labels="labels"
        :series="visibleSeries"
        :stacked="false"
        :loading="loading"
        :empty-text="loading ? t('dashboard.metrics.loading') : t('dashboard.metrics.noData')"
        :format-value="selectedMode === 'throughput' ? formatBytes : (n) => Math.round(n).toLocaleString()"
      />

      <DashboardMetricSummaryGrid :items="summaryItems" />
    </div>
  </el-card>
</template>
