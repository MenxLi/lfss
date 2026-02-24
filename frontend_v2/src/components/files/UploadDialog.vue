<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Connector, { ApiUtils } from '@/api'
import { ensureDirPath, forEachFile, getLastPathComponentRange, selectInputRange } from '@/utils'
import { UploadFilled, Refresh } from '@element-plus/icons-vue'
import { useLogStore } from '@/store/logs'

const props = defineProps<{
  conn: Connector
  currentPath: string
}>()

const emit = defineEmits<{
  (e: 'uploaded'): void
  (e: 'close'): void
}>()

const { t } = useI18n()
const logStore = useLogStore()

const uploadDialogVisible = ref(false)
const uploadPath = ref('')
const uploadFileObj = ref<File | null>(null)
const uploadFileName = ref('')
const isUploading = ref(false)
const fileExists = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadPathInputRef = ref<any>(null)
const multipleDestDirInputRef = ref<any>(null)

const isMultiple = ref(false)
const multipleFiles = ref<{ relPath: string, file: File }[]>([])
const multipleBaseDir = ref('')
const multipleDestDirName = ref('')

const joinPath = (base: string, name: string) => {
  if (!base) return name
  return base.endsWith('/') ? `${base}${name}` : `${base}/${name}`
}

const normalizeSubdirName = (name: string) => name.trim().replace(/^\/+|\/+$/g, '')

const getRootDirFromRelPath = (relPath: string) => {
  const firstPart = relPath.split('/').filter(Boolean)[0] || ''
  return normalizeSubdirName(firstPart)
}

const focusAndSelectLastPathComponent = async () => {
  await nextTick()
  const input = uploadPathInputRef.value?.input as HTMLInputElement | undefined
  if (!input) return
  const [start, end] = getLastPathComponentRange(uploadPath.value)
  selectInputRange(input, start, end)
}

const focusAndSelectDestDirName = async () => {
  await nextTick()
  const input = multipleDestDirInputRef.value?.input as HTMLInputElement | undefined
  if (!input) return
  selectInputRange(input, 0, input.value.length)
}

const resetState = () => {
  uploadFileObj.value = null
  uploadFileName.value = ''
  fileExists.value = false
  isMultiple.value = false
  multipleFiles.value = []
  multipleBaseDir.value = ''
  multipleDestDirName.value = ''
}

const open = async () => {
  uploadPath.value = ensureDirPath(props.currentPath)
  resetState()
  uploadDialogVisible.value = true
  await focusAndSelectLastPathComponent()
}

const openWithDrop = async (e: DragEvent) => {
  await open()
  await handleDrop(e)
}

defineExpose({ open, openWithDrop })

const checkFileExists = async () => {
  if (!uploadFileName.value || uploadFileName.value.endsWith('/')) {
    fileExists.value = false
    return
  }
  const fullPath = joinPath(uploadPath.value, uploadFileName.value)
  try {
    const meta = await props.conn.getMetadata(fullPath)
    fileExists.value = !!meta
  } catch (e) {
    fileExists.value = false
  }
}

const randomizeFileName = () => {
  const ext = uploadFileName.value.split('.').pop() || ''
  const randomStr = Math.random().toString(36).substring(2, 15)
  uploadFileName.value = ext && uploadFileName.value.includes('.') ? `${randomStr}.${ext}` : randomStr
  checkFileExists()
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    uploadFileObj.value = target.files[0]
    uploadFileName.value = target.files[0].name
    isMultiple.value = false
    checkFileExists()
  }
}

const handleDrop = async (e: DragEvent) => {
  const items = e.dataTransfer?.items
  if (items && items.length === 1 && items[0].kind === 'file' && items[0].webkitGetAsEntry()?.isFile) {
    const file = items[0].getAsFile()
    if (file) {
      uploadFileObj.value = file
      uploadFileName.value = file.name
      isMultiple.value = false
      checkFileExists()
    }
    return
  }

  isUploading.value = true
  try {
    const files: { relPath: string, file: File }[] = []
    await forEachFile(e, async (relPath, filePromiseFn) => {
      const file = await filePromiseFn()
      files.push({ relPath, file })
    })
    
    multipleFiles.value = files
    isMultiple.value = true
    uploadFileObj.value = null
    uploadFileName.value = ''

    uploadPath.value = ensureDirPath(props.currentPath)
    if (items && items.length === 1 && items[0].kind === 'file' && items[0].webkitGetAsEntry()?.isDirectory) {
      const dirNameFromEntry = normalizeSubdirName(items[0].webkitGetAsEntry()?.name || '')
      const dirNameFromRelPath = files.length > 0 ? getRootDirFromRelPath(files[0].relPath) : ''
      const dirName = dirNameFromEntry || dirNameFromRelPath
      if (dirName) {
        multipleBaseDir.value = `${dirName}/`
        multipleDestDirName.value = dirName
      }
    } else {
      multipleBaseDir.value = ''
      multipleDestDirName.value = ''
    }

    if (multipleDestDirName.value) {
      await focusAndSelectDestDirName()
    } else {
      await nextTick()
      const input = multipleDestDirInputRef.value?.input as HTMLInputElement | undefined
      if (input) { input.focus() }
    }
  } catch (err: any) {
    logStore.logMessage('error', 'Failed to read files: ' + err.message)
  } finally {
    isUploading.value = false
  }
}

const confirmUpload = async () => {
  if (isMultiple.value) {
    isUploading.value = true
    try {
      const dstBasePath = ensureDirPath(uploadPath.value)
      const destDirName = normalizeSubdirName(multipleDestDirName.value)

      let activeCount = 0
      const queue: (() => void)[] = []
      const runWithLimit = async (task: () => Promise<void>) => {
        if (activeCount >= 8) {
          await new Promise<void>(resolve => queue.push(resolve))
        }
        activeCount++
        try {
          await task()
        } finally {
          activeCount--
          if (queue.length) {
            const next = queue.shift()
            if (next) next()
          }
        }
      }

      const uploadTasks = multipleFiles.value.map(({ relPath, file }) => async () => {
        let finalRelPath = relPath
        if (multipleBaseDir.value) {
          if (relPath.startsWith(multipleBaseDir.value)) {
            finalRelPath = relPath.substring(multipleBaseDir.value.length)
          } else {
            const rootDir = getRootDirFromRelPath(relPath)
            if (rootDir) {
              const pathParts = relPath.split('/').filter(Boolean)
              finalRelPath = pathParts.slice(1).join('/')
            }
          }
        }
        const prefixedRelPath = destDirName ? `${destDirName}/${finalRelPath}` : finalRelPath
        const fullPath = joinPath(dstBasePath, prefixedRelPath)
        await ApiUtils.uploadFile(props.conn, fullPath, file, { conflict: 'overwrite' })
      })

      await Promise.all(uploadTasks.map(task => runWithLimit(task)))
      logStore.logMessage('success', 'Upload success')
      uploadDialogVisible.value = false
      emit('uploaded')
    } catch (err: any) {
      logStore.logMessage('error', 'Failed to upload some files: ' + err.message)
    } finally {
      isUploading.value = false
    }
    return
  }

  if (!uploadFileObj.value || !uploadFileName.value) return
  isUploading.value = true
  try {
    const fullPath = joinPath(uploadPath.value, uploadFileName.value)
    await ApiUtils.uploadFile(props.conn, fullPath, uploadFileObj.value, { conflict: 'overwrite' })
    logStore.logMessage('success', t('files.success'))
    uploadDialogVisible.value = false
    emit('uploaded')
  } catch (e: unknown) {
    const err = e as Error
    logStore.logMessage('error', err.message || t('files.failed'))
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="uploadDialogVisible"
    :title="t('files.upload')"
    width="500px"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div 
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition-colors"
        @click="triggerFileInput"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <input 
          type="file" 
          ref="fileInputRef" 
          class="hidden" 
          @change="handleFileInputChange"
        />
        <el-icon class="text-4xl text-gray-400 mb-2"><UploadFilled /></el-icon>
        <div class="text-gray-600">
          <span v-if="uploadFileObj">{{ uploadFileObj.name }}</span>
          <span v-else-if="isMultiple">Ready to upload {{ multipleFiles.length }} files</span>
          <span v-else>Click or drag file here to upload</span>
        </div>
      </div>

      <div v-if="uploadFileObj || isMultiple" class="space-y-2">
        <el-input ref="uploadPathInputRef" v-model="uploadPath" placeholder="Upload directory" @input="checkFileExists">
          <template #prepend>Directory</template>
        </el-input>
        <el-input
          v-if="isMultiple"
          ref="multipleDestDirInputRef"
          v-model="multipleDestDirName"
          placeholder="Destination subdirectory"
        >
          <template #prepend>Subdirectory</template>
        </el-input>
        <div v-if="!isMultiple" class="flex items-center gap-2">
          <el-input v-model="uploadFileName" placeholder="File name" @input="checkFileExists">
            <template #prepend>File Name</template>
          </el-input>
          <el-button @click="randomizeFileName" title="Randomize name">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
        <div v-if="!isMultiple && fileExists" class="text-red-500 text-sm">
          Warning: File already exists and will be overwritten.
        </div>
        <div v-if="isMultiple" class="text-gray-600 text-sm">
          Note: Same name files will be overwritten. 
          Filename will be preserved with the relative path. 
          Set subdirectory to place files under a custom folder.
        </div>
      </div>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="uploadDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="isUploading" :disabled="(!isMultiple && (!uploadFileObj || !uploadFileName)) || (isMultiple && multipleFiles.length === 0)">
          Upload
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>
