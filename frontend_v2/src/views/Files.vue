<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import Connector, { ApiUtils, permMap } from '@/api'
import type { DirectoryRecord, FileRecord } from '@/api'
import { useUserStore } from '@/store/user'
import {
  Document,
  Folder,
  Download,
  Delete,
  Upload,
  CopyDocument,
  Rank,
  InfoFilled,
  FolderAdd,
  Back
} from '@element-plus/icons-vue'
import UploadDialog from '@/components/files/UploadDialog.vue'
import DetailsDialog from '@/components/files/DetailsDialog.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const currentPath = computed(() => {
  const path = route.params.path as string | string[]
  if (!path) return ''
  let p = Array.isArray(path) ? path.join('/') : path
  if (!p.endsWith('/')) p += '/'
  return p
})

const joinPath = (base: string, name: string) => {
  if (!base) return name
  return base.endsWith('/') ? `${base}${name}` : `${base}/${name}`
}

const dirs = ref<DirectoryRecord[]>([])
const files = ref<FileRecord[]>([])
const loading = ref(false)

// Pagination & Sorting
const currentPage = ref(1)
const pageSize = ref(50)
const totalItems = ref(0)
const sortBy = ref<string>('')
const sortDesc = ref<boolean>(false)

const conn = new Connector()
conn.config = { 
  endpoint: localStorage.getItem('endpoint') || window.location.origin, 
  token: userStore.token 
}

const loadData = async () => {
  loading.value = true
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    const [data, count] = await ApiUtils.listPath(conn, currentPath.value, {
      offset,
      limit: pageSize.value,
      orderBy: (sortBy.value || 'none') as any,
      orderDesc: sortDesc.value
    })
    dirs.value = data.dirs
    files.value = data.files
    totalItems.value = count.dirs + count.files
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || 'Failed to load files')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(currentPath, () => {
  currentPage.value = 1
  loadData()
})

const handleSortChange = ({ prop, order }: { prop: string, order: string }) => {
  if (!order) {
    sortBy.value = ''
    sortDesc.value = false
  } else {
    sortBy.value = prop === 'url' ? 'url' : prop === 'file_size' ? 'file_size' : prop === 'update_time' ? 'update_time' : ''
    sortDesc.value = order === 'descending'
  }
  currentPage.value = 1
  loadData()
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  currentPage.value = 1
  loadData()
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  loadData()
}

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

const handleDirClick = (dir: DirectoryRecord) => {
  router.push(`/files/${dir.url}`)
}

const handleBack = () => {
  if (!currentPath.value) return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  router.push(`/files/${parts.join('/')}`)
}

const handleDelete = async (item: DirectoryRecord | FileRecord, isDir: boolean) => {
  try {
    await ElMessageBox.confirm(t('files.confirmDelete'), 'Warning', {
      type: 'warning'
    })
    const path = item.url
    await conn.delete(isDir && !path.endsWith('/') ? path + '/' : path)
    ElMessage.success(t('files.success'))
    loadData()
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      ElMessage.error(err.message || t('files.failed'))
    }
  }
}

// Upload Modal State
const uploadDialogRef = ref<InstanceType<typeof UploadDialog> | null>(null)

const openUploadDialog = () => {
  uploadDialogRef.value?.open()
}

const handleDownload = (item: DirectoryRecord | FileRecord, isDir: boolean) => {
  let path = item.url
  if (isDir) {
    if (!path.endsWith('/')) path += '/'
    window.open(ApiUtils.getBundleUrl(conn, path), '_blank')
  } else {
    window.open(ApiUtils.getDownloadUrl(conn, path), '_blank')
  }
}

const handleMove = async (item: DirectoryRecord | FileRecord, isDir: boolean) => {
  try {
    let srcPath = item.url
    if (isDir && !srcPath.endsWith('/')) srcPath += '/'
    
    const { value } = (await ElMessageBox.prompt('Enter destination path:', 'Move', {
      inputValue: srcPath,
      confirmButtonText: 'Move',
      cancelButtonText: 'Cancel',
    })) as any
    if (value) {
      await conn.move(srcPath, value)
      ElMessage.success('Moved successfully')
      loadData()
    }
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      ElMessage.error(err.message || 'Failed to move')
    }
  }
}

const handleCopy = async (item: DirectoryRecord | FileRecord, isDir: boolean) => {
  try {
    let srcPath = item.url
    if (isDir && !srcPath.endsWith('/')) srcPath += '/'
    
    const { value } = (await ElMessageBox.prompt('Enter destination path:', 'Copy', {
      inputValue: srcPath,
      confirmButtonText: 'Copy',
      cancelButtonText: 'Cancel',
    })) as any
    if (value) {
      await conn.copy(srcPath, value)
      ElMessage.success('Copied successfully')
      loadData()
    }
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      ElMessage.error(err.message || 'Failed to copy')
    }
  }
}

const handleCreateFolder = async () => {
  try {
    const { value } = (await ElMessageBox.prompt('Enter folder name:', 'New Folder', {
      confirmButtonText: 'Create',
      cancelButtonText: 'Cancel',
      inputPattern: /^[^/]+$/,
      inputErrorMessage: 'Folder name cannot contain slashes'
    })) as any
    if (value) {
      const folderPath = joinPath(currentPath.value, value)
      await conn.putText(joinPath(folderPath, '.lfss-keep'), '')
      ElMessage.success('Folder created')
      loadData()
    }
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      ElMessage.error(err.message || 'Failed to create folder')
    }
  }
}

const handlePermissionChange = async (file: FileRecord, perm: number) => {
  try {
    await conn.setFilePermission(file.url, perm)
    ElMessage.success('Permission updated')
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || 'Failed to update permission')
    loadData() // revert
  }
}

const canManagePermission = (row: DirectoryRecord | FileRecord) => {
  if (row.url.endsWith('/')) return false
  const fileRow = row as FileRecord
  console.log('Checking permission for file:', fileRow.url, 'owner:', fileRow.owner_id, 'current user:', userStore.userInfo)
  return userStore.userInfo?.is_admin || fileRow.owner_id === userStore.userInfo?.id
}

const isImage = (url: string) => {
  const ext = url.split('.').pop()?.toLowerCase()
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext || '')
}

// Details Modal State
const detailsDialogRef = ref<InstanceType<typeof DetailsDialog> | null>(null)

const handleDetails = (row: DirectoryRecord | FileRecord, isDir: boolean) => {
  detailsDialogRef.value?.open(row, isDir)
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-between items-center">
      <div class="flex items-center gap-2">
        <el-button @click="handleBack" :disabled="!currentPath">
          <el-icon><Back /></el-icon>
        </el-button>
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/files' }">Root</el-breadcrumb-item>
          <el-breadcrumb-item 
            v-for="(part, index) in currentPath.split('/').filter(Boolean)" 
            :key="index"
            :to="{ path: '/files/' + currentPath.split('/').filter(Boolean).slice(0, index + 1).join('/') + '/' }"
          >
            {{ part }}
          </el-breadcrumb-item>
        </el-breadcrumb>
      </div>
      <div class="flex gap-2">
        <el-button type="success" @click="handleCreateFolder" :disabled="!currentPath">
          <el-icon class="mr-1"><FolderAdd /></el-icon>
          New Folder
        </el-button>
        <el-button type="primary" @click="openUploadDialog" :disabled="!currentPath">
          <el-icon class="mr-1"><Upload /></el-icon>
          {{ t('files.upload') }}
        </el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-table 
        :data="[...dirs.map(d => ({...d, isDir: true})), ...files.map(f => ({...f, isDir: false}))]" 
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="url" :label="t('files.name')" min-width="200" sortable="custom">
          <template #default="{ row }">
            <div class="flex items-center gap-2 cursor-pointer hover:text-blue-500" @click="row.isDir ? handleDirClick(row) : null">
              <template v-if="!row.isDir && isImage(row.url)">
                <el-image 
                  :src="ApiUtils.getThumbUrl(conn, row.url)" 
                  lazy 
                  class="w-8 h-8 rounded object-cover"
                  :preview-src-list="[ApiUtils.getDownloadUrl(conn, row.url)]"
                  preview-teleported
                  @click.stop
                >
                  <template #error>
                    <el-icon size="20" color="#909399"><Document /></el-icon>
                  </template>
                </el-image>
              </template>
              <el-icon v-else size="20" :color="row.isDir ? '#e6a23c' : '#909399'">
                <Folder v-if="row.isDir" />
                <Document v-else />
              </el-icon>
              <span>{{ row.url.split('/').filter(Boolean).pop() }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" :label="t('files.size')" width="120" sortable="custom">
          <template #default="{ row }">
            {{ row.isDir ? '-' : formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="update_time" :label="t('files.modified')" width="180" sortable="custom">
          <template #default="{ row }">
            {{ formatDate(row.update_time || row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('files.permission')" width="150">
          <template #default="{ row }">
            <el-select 
              v-if="canManagePermission(row)" 
              v-model="row.permission" 
              size="small"
              @change="(val: number) => handlePermissionChange(row, val)"
            >
              <el-option v-for="(label, value) in permMap" :key="value" :label="t(`files.permissions.${label}`)" :value="Number(value)" />
            </el-select>
            <span v-else-if="!row.isDir">{{ t(`files.permissions.${permMap[row.permission] || 'unset'}`) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('files.actions')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" @click="handleDetails(row, row.isDir)" title="Details">
                <el-icon><InfoFilled /></el-icon>
              </el-button>
              <el-button size="small" @click="handleDownload(row, row.isDir)" title="Download">
                <el-icon><Download /></el-icon>
              </el-button>
              <el-button size="small" @click="handleCopy(row, row.isDir)" title="Copy">
                <el-icon><CopyDocument /></el-icon>
              </el-button>
              <el-button size="small" @click="handleMove(row, row.isDir)" title="Move">
                <el-icon><Rank /></el-icon>
              </el-button>
              <el-button size="small" type="danger" @click="handleDelete(row, row.isDir)" title="Delete">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="t('files.empty')" />
        </template>
      </el-table>
      
      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          :total="totalItems"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- Upload Dialog -->
    <UploadDialog 
      ref="uploadDialogRef" 
      :conn="conn" 
      :current-path="currentPath" 
      @uploaded="loadData" 
    />

    <!-- Details Dialog -->
    <DetailsDialog 
      ref="detailsDialogRef" 
      :conn="conn" 
    />
  </div>
</template>
