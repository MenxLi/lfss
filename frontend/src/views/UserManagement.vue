<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'
import { sha256 } from 'js-sha256'
import type { UserRecord } from '@/api'
import { useUserStore } from '@/store/user'
import { useLogStore } from '@/store/logs'
import UserToolbar from '@/components/users/UserToolbar.vue'
import UserTable from '@/components/users/UserTable.vue'
import PeerAccessDialog from '@/components/users/PeerAccessDialog.vue'
import { createConnector } from '@/utils'

const { t } = useI18n()
const userStore = useUserStore()
const logStore = useLogStore()

const conn = createConnector(userStore.token)

const users = ref<UserRecord[]>([])
const userExpireMap = ref<Record<string, number | null>>({})
const userStorageUsedMap = ref<Record<string, number>>({})
const loading = ref(false)
const searchQuery = ref('')
const includeVirtual = ref(false)
const sortBy = ref<'username' | 'create_time' | 'is_admin' | 'last_active'>('create_time')
const sortDesc = ref(false)
const sortableProps = ['username', 'create_time', 'is_admin', 'last_active'] as const
const currentPage = ref(1)
const pageSize = ref(20)
const totalUsers = ref(0)

const dialogVisible = ref(false)
const isEdit = ref(false)
const form = ref({
  virtual: false,
  tag: '',
  expire: '',
  username: '',
  password: '',
  admin: false,
  max_storage: '100G',
  permission: 'UNSET'
})

const peerDialogVisible = ref(false)
const peerTargetUsername = ref('')

const userToken = computed(() => {
  if (!form.value.username || !form.value.password) return ''
  return sha256(form.value.username + ':' + form.value.password)
})

const loadUsers = async () => {
  loading.value = true
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    users.value = await conn.listUsers({
      username_filter: searchQuery.value || undefined,
      include_virtual: includeVirtual.value,
      order_by: sortBy.value,
      order_desc: sortDesc.value,
      offset,
      limit: pageSize.value
    })
    const allMatched = await conn.listUsers({
      username_filter: searchQuery.value || undefined,
      include_virtual: includeVirtual.value,
      order_by: sortBy.value,
      order_desc: sortDesc.value,
      offset: 0,
      limit: 100000
    })
    totalUsers.value = allMatched.length
    const entries = await Promise.all(users.value.map(async (user) => {
      try {
        const info = await conn.queryUserExpire({ username: user.username })
        return [user.username, info.expire_seconds] as const
      } catch {
        return [user.username, null] as const
      }
    }))
    userExpireMap.value = Object.fromEntries(entries)

    const storageEntries = await Promise.all(users.value.map(async (user) => {
      try {
        const info = await conn.getUserStorage(user.username)
        return [user.username, info.used] as const
      } catch {
        return [user.username, 0] as const
      }
    }))
    userStorageUsedMap.value = Object.fromEntries(storageEntries)
  } catch (e: unknown) {
    const err = e as Error
    logStore.logMessage('error', err.message || t('users.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(searchQuery, () => {
  currentPage.value = 1
  loadUsers()
})
watch(includeVirtual, () => {
  currentPage.value = 1
  loadUsers()
})

onMounted(loadUsers)

const handleSortChange = ({ prop, order }: { prop: string, order: string }) => {
  if (!prop || !sortableProps.includes(prop as typeof sortableProps[number])) return
  sortBy.value = prop as typeof sortableProps[number]
  sortDesc.value = order === 'descending'
  currentPage.value = 1
  loadUsers()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadUsers()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadUsers()
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    virtual: false,
    tag: '',
    expire: '',
    username: '',
    password: '',
    admin: false,
    max_storage: '100G',
    permission: 'UNSET'
  }
  dialogVisible.value = true
}

const handleEdit = (user: UserRecord) => {
  isEdit.value = true
  form.value = {
    virtual: false,
    tag: '',
    expire: '',
    username: user.username,
    password: '',
    admin: Boolean(user.is_admin),
    max_storage: user.max_storage ? `${user.max_storage / (1024 * 1024 * 1024)}G` : '100G',
    permission: user.permission === 1 ? 'PUBLIC' : user.permission === 2 ? 'PROTECTED' : user.permission === 3 ? 'PRIVATE' : 'UNSET'
  }
  dialogVisible.value = true
}

const openPeerDialog = (user: UserRecord) => {
  peerTargetUsername.value = user.username
  peerDialogVisible.value = true
}

const generateRandomPassword = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_'
  let password = ''
  for (let i = 0; i < 32; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  form.value.password = password
}

const copyToken = async () => {
  try {
    await navigator.clipboard.writeText(userToken.value)
    logStore.logMessage('success', t('users.tokenCopied'))
  } catch {
    logStore.logMessage('error', t('users.copyTokenFailed'))
  }
}

const handleDelete = async (user: UserRecord) => {
  try {
    await ElMessageBox.confirm(t('users.confirmDeleteNamed', { username: user.username }), t('users.warningTitle'), {
      type: 'warning'
    })
    await conn.deleteUser(user.username)
    logStore.logMessage('success', t('users.success'))
    loadUsers()
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      logStore.logMessage('error', err.message || t('users.failed'))
    }
  }
}

const handleSetExpire = async (user: UserRecord) => {
  try {
    const currentExpire = userExpireMap.value[user.username]
    const defaultValue = currentExpire !== null && currentExpire !== undefined && currentExpire > 0
      ? String(currentExpire)
      : ''
    const { value } = (await ElMessageBox.prompt(
      t('users.expirePrompt', { username: user.username }),
      t('users.expireTitle', { username: user.username }),
      {
        confirmButtonText: t('users.confirm'),
        cancelButtonText: t('users.cancel'),
        inputPlaceholder: t('users.expirePlaceholder'),
        inputValue: defaultValue,
      }
    )) as any
    let input = String(value || '').trim()
    // if input is pure number, treat it as seconds
    if (/^\d+$/.test(input)) { input += 's' }
    const result = await conn.setUserExpire(user.username, input || undefined)
    userExpireMap.value[user.username] = result.expire_seconds
    logStore.logMessage('success', t('users.expireUpdated', { username: user.username }))
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      logStore.logMessage('error', err.message || t('users.failed'))
    }
  }
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      const params: { username: string, password?: string, admin?: boolean, max_storage?: string, permission?: string } = {
        username: form.value.username,
        admin: form.value.admin,
        max_storage: form.value.max_storage,
        permission: form.value.permission
      }
      if (form.value.password) {
        params.password = form.value.password
      }
      await conn.updateUser(params)
      logStore.logMessage('success', t('users.success'))
    } else if (form.value.virtual) {
      if (form.value.expire && /^\d+$/.test(form.value.expire)) {
        form.value.expire += 's'
      }
      const created = await conn.addVirtualUser({
        tag: form.value.tag,
        max_storage: form.value.max_storage,
        expire: form.value.expire || undefined,
      })
      includeVirtual.value = true
      peerTargetUsername.value = created.username
      peerDialogVisible.value = true
      logStore.logMessage('success', t('users.virtualCreated', { username: created.username }))
    } else {
      const params: { username: string, password?: string, admin?: boolean, max_storage?: string, permission?: string } = {
        username: form.value.username,
        admin: form.value.admin,
        max_storage: form.value.max_storage,
        permission: form.value.permission
      }
      if (form.value.password) {
        params.password = form.value.password
      }
      await conn.addUser(params)
      logStore.logMessage('success', t('users.success'))
    }
    dialogVisible.value = false
    loadUsers()
  } catch (e: unknown) {
    const err = e as Error
    logStore.logMessage('error', err.message || t('users.failed'))
  }
}
</script>

<template>
  <el-card shadow="hover" class="w-full">
    <template #header>
      <UserToolbar
        v-model:search-query="searchQuery"
        v-model:include-virtual="includeVirtual"
        @add="handleAdd"
        @refresh="loadUsers"
      />
    </template>

    <UserTable
      :users="users"
      :loading="loading"
      :current-username="userStore.userInfo?.username"
      :expire-map="userExpireMap"
      :user-storage-used-map="userStorageUsedMap"
      @sort="handleSortChange"
      @edit="handleEdit"
      @delete="handleDelete"
      @peers="openPeerDialog"
      @expire="handleSetExpire"
    />

    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="totalUsers"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? t('users.edit') : t('users.addUser')"
      width="500px"
    >
      <el-form :model="form" label-width="120px">
        <el-form-item v-if="!isEdit" :label="t('users.virtualUser')">
          <el-switch v-model="form.virtual" />
        </el-form-item>
        <el-form-item v-if="!form.virtual || isEdit" :label="t('users.username')">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="form.virtual && !isEdit" :label="t('users.virtualTag')">
          <el-input v-model="form.tag" :placeholder="t('users.virtualTagPlaceholder')" />
        </el-form-item>
        <el-form-item v-if="!form.virtual || isEdit" :label="t('users.password')">
          <div class="flex flex-col w-full gap-2">
            <div class="flex gap-2">
              <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? t('users.leaveBlank') : ''" />
              <el-button @click="generateRandomPassword" :title="t('users.randomPassword')">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
            <div v-if="form.password" class="text-xs text-gray-500 break-all flex items-center gap-2">
              {{ userToken }}
              <el-button link type="primary" @click="copyToken" :title="t('users.copyToken')">
                <el-icon><DocumentCopy /></el-icon>
              </el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="!form.virtual || isEdit" :label="t('users.role')">
          <el-switch v-model="form.admin" :active-text="t('dashboard.admin')" :inactive-text="t('dashboard.user')" />
        </el-form-item>
        <el-form-item :label="t('users.storage')">
          <el-input v-model="form.max_storage" :placeholder="t('users.storagePlaceholder')" />
        </el-form-item>
        <el-form-item v-if="form.virtual && !isEdit" :label="t('users.expireIn')">
          <el-input v-model="form.expire" :placeholder="t('users.expirePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">{{ t('users.cancel') }}</el-button>
          <el-button type="primary" @click="handleSubmit">{{ t('users.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>

    <PeerAccessDialog
      v-model:visible="peerDialogVisible"
      :username="peerTargetUsername"
      @saved="loadUsers"
    />
  </el-card>
</template>
