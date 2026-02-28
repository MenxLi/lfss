import { defineStore } from 'pinia'
import { ref } from 'vue'

export type FileSortField = '' | 'url' | 'file_size' | 'create_time' | 'access_time' | 'mime_type' | 'owner_id'

export interface FileColumnPrefs {
    size: boolean
    created: boolean
    accessed: boolean
    permission: boolean
    ownerId: boolean
}

export type DashboardMetricWindow = 'hour' | 'day' | 'week'
export type DashboardMetricMode = 'requests' | 'throughput'

export const usePreferenceStore = defineStore('preferences', () => {
    const filePageSize = ref(50)
    const fileSortBy = ref<FileSortField>('')
    const fileSortDesc = ref(false)
    const fileLastPath = ref('')
    const fileColumns = ref<FileColumnPrefs>({
        size: true,
        created: true,
        accessed: true,
        permission: true,
        ownerId: false,
    })
    const dashboardMetricWindow = ref<DashboardMetricWindow>('day')
    const dashboardMetricMode = ref<DashboardMetricMode>('requests')
    const dashboardHiddenRequestSeries = ref<string[]>([])
    const dashboardHiddenThroughputSeries = ref<string[]>([])

    return {
        filePageSize,
        fileSortBy,
        fileSortDesc,
        fileLastPath,
        fileColumns,
        dashboardMetricWindow,
        dashboardMetricMode,
        dashboardHiddenRequestSeries,
        dashboardHiddenThroughputSeries,
    }
}, {
    persist: {
        key: 'lfss-preferences',
    },
})
