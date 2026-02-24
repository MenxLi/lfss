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

    return {
        filePageSize,
        fileSortBy,
        fileSortDesc,
        fileLastPath,
        fileColumns,
    }
}, {
    persist: {
        key: 'lfss-preferences',
    },
})
