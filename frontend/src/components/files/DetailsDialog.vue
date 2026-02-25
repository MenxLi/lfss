<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Connector, { ApiUtils } from '@/api'
import type { DirectoryRecord, FileRecord } from '@/api'
import { copyToClipboard } from '@/utils'
import { useLogStore } from '@/store/logs'

const props = defineProps<{
  conn: Connector
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useI18n()
const logStore = useLogStore()

const detailsDialogVisible = ref(false)
const detailsData = ref<(DirectoryRecord | FileRecord) & { isDir: boolean } | null>(null)
const ownerUsername = ref<string>('')

const open = async (row: DirectoryRecord | FileRecord, isDir: boolean) => {
  detailsData.value = { ...row, isDir }
  detailsDialogVisible.value = true
  ownerUsername.value = ''
  if (isDir) {
    props.conn.getMetadata(ApiUtils.decodePath(row.url)).then((res) => {
      detailsData.value = { ...res as DirectoryRecord, isDir: true }
    }).catch((e) => {
      console.error('Failed to fetch directory details', e)
      logStore.logMessage('error', t('files.details.loadDirFailed'))
    })
  }

  if (!isDir && 'owner_id' in row) {
    ownerUsername.value = String(`[ID: ${row.owner_id}]`)
    props.conn.queryUser(row.owner_id).then((user) => {
      ownerUsername.value = user.username
    }).catch((e) => {
      console.error('Failed to fetch owner username', e)
      ownerUsername.value = String(row.owner_id)
    })
  }
}

defineExpose({ open })

const formatSize = (bytes: number) => {
  if (bytes === -1) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const copyUrl = () => {
  if (!detailsData.value) return
  const url = ApiUtils.getFullUrl(props.conn, detailsData.value.url, false)
  copyToClipboard(url)
  logStore.logMessage('success', t('files.details.urlCopied'))
}
const copyUrlRaw = () => {
  if (!detailsData.value) return
  copyToClipboard(detailsData.value.url)
  logStore.logMessage('success', t('files.details.pathCopied'))
}
</script>

<template>
  <el-dialog
    v-model="detailsDialogVisible"
    :title="t('files.details.title')"
    width="500px"
    @close="emit('close')"
  >
    <div v-if="detailsData" class="space-y-4">
      <div class="border border-gray-200">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item :label="t('files.details.name')">
            <span class="break-all">{{ ApiUtils.decodePath(detailsData.url).split('/').filter(Boolean).pop() || '/' }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('files.details.path')">
            <span class="break-all">{{ ApiUtils.decodePath(detailsData.url) }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('files.details.type')">
            {{ detailsData.isDir ? t('files.directory') : t('files.file') }}
          </el-descriptions-item>

          <template v-if="!detailsData.isDir">
            <el-descriptions-item :label="t('files.details.owner')">
              {{ ownerUsername || (detailsData as FileRecord).owner_id }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('files.details.size')">
              {{ formatSize((detailsData as FileRecord).file_size) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('files.details.mimeType')">
              {{ (detailsData as FileRecord).mime_type || '-' }}
            </el-descriptions-item>
          </template>

          <el-descriptions-item :label="t('files.details.created')">
            {{ formatDate(detailsData.create_time) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('files.details.accessed')">
            {{ formatDate(detailsData.access_time) }}
          </el-descriptions-item>

          <template v-if="detailsData.isDir">
            <el-descriptions-item :label="t('files.details.modified')">
              {{ formatDate((detailsData as DirectoryRecord).update_time) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('files.details.fileCount')">
              {{ (detailsData as DirectoryRecord).n_files }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('files.details.size')">
              {{ formatSize((detailsData as DirectoryRecord).size) }}
            </el-descriptions-item>
          </template>
        </el-descriptions>
      </div>

      <div class="space-y-2">
        <div class="text-xs text-gray-500">{{ t('files.details.path') }}</div>
        <div class="flex items-center gap-2">
          <el-input :value="detailsData.url" readonly />
          <el-button @click="copyUrlRaw" :title="t('files.details.copyPath')">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="space-y-2">
        <div class="text-xs text-gray-500">{{ t('files.details.fullUrl') }}</div>
        <div class="flex items-center gap-2">
          <el-input :value="ApiUtils.getFullUrl(props.conn, detailsData.url, false)" readonly />
          <el-button @click="copyUrl" :title="t('files.details.copyUrl')">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>
