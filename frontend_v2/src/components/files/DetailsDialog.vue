<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import Connector, { ApiUtils } from '@/api'
import type { DirectoryRecord, FileRecord } from '@/api'
import { copyToClipboard } from '@/utils'

const props = defineProps<{
  conn: Connector
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const detailsDialogVisible = ref(false)
const detailsData = ref<(DirectoryRecord | FileRecord) & { isDir: boolean } | null>(null)

const open = (row: DirectoryRecord | FileRecord, isDir: boolean) => {
  detailsData.value = { ...row, isDir }
  detailsDialogVisible.value = true
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
  const url = ApiUtils.getDownloadUrl(props.conn, detailsData.value.url)
  copyToClipboard(url)
  ElMessage.success('URL copied to clipboard')
}
</script>

<template>
  <el-dialog
    v-model="detailsDialogVisible"
    title="Details"
    width="500px"
    @close="emit('close')"
  >
    <div v-if="detailsData" class="space-y-4">
      <div class="grid grid-cols-3 gap-2">
        <div class="font-bold text-gray-600">Name:</div>
        <div class="col-span-2 break-all">{{ detailsData.url.split('/').filter(Boolean).pop() }}</div>
        
        <div class="font-bold text-gray-600">Path:</div>
        <div class="col-span-2 break-all">{{ detailsData.url }}</div>
        
        <div class="font-bold text-gray-600">Type:</div>
        <div class="col-span-2">{{ detailsData.isDir ? 'Directory' : 'File' }}</div>
        
        <template v-if="!detailsData.isDir">
          <div class="font-bold text-gray-600">Size:</div>
          <div class="col-span-2">{{ formatSize((detailsData as FileRecord).file_size) }}</div>
          
          <div class="font-bold text-gray-600">MIME Type:</div>
          <div class="col-span-2">{{ (detailsData as FileRecord).mime_type || '-' }}</div>
        </template>
        
        <div class="font-bold text-gray-600">Created:</div>
        <div class="col-span-2">{{ formatDate(detailsData.create_time) }}</div>
        
        <div class="font-bold text-gray-600">Modified:</div>
        <div class="col-span-2">{{ formatDate((detailsData as DirectoryRecord).update_time || detailsData.create_time) }}</div>
        
        <template v-if="!detailsData.isDir">
          <div class="font-bold text-gray-600">Download URL:</div>
          <div class="col-span-2 flex items-center gap-2">
            <el-input :value="ApiUtils.getDownloadUrl(props.conn, detailsData.url)" readonly size="small" />
            <el-button size="small" @click="copyUrl" title="Copy URL">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>
        </template>
      </div>
    </div>
  </el-dialog>
</template>
