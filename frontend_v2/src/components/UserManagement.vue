<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import Connector from '@/api'
import type { UserRecord } from '@/api'
import { useUserStore } from '@/store/user'

const { t } = useI18n()
const userStore = useUserStore()

const users = ref<UserRecord[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)

const form = ref({
  username: '',
  password: '',
  admin: false,
  max_storage: '100G',
  permission: 'UNSET'
})

const conn = new Connector()
conn.config = { 
  endpoint: localStorage.getItem('endpoint') || window.location.origin, 
  token: userStore.token 
}

const loadUsers = async () => {
  loading.value = true
  try {
    users.value = await conn.listPeers({ level: 1, incoming: true, admin: true })
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || 'Failed to load users')
  } finally {
    loading.value = false
  }
}

onMounted(loadUsers)

const handleAdd = () => {
  isEdit.value = false
  form.value = {
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
    username: user.username,
    password: '',
    admin: user.is_admin,
    max_storage: user.max_storage ? `${user.max_storage / (1024 * 1024 * 1024)}G` : '100G',
    permission: 'UNSET'
  }
  dialogVisible.value = true
}

const handleDelete = async (user: UserRecord) => {
  try {
    await ElMessageBox.confirm(t('users.confirmDelete'), 'Warning', {
      type: 'warning'
    })
    await conn.deleteUser(user.username)
    ElMessage.success(t('users.success'))
    loadUsers()
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as Error
      ElMessage.error(err.message || t('users.failed'))
    }
  }
}

const handleSubmit = async () => {
  try {
    const params: { username: string, password?: string, admin?: boolean, max_storage?: string, permission?: string } = {
      username: form.value.username,
      admin: form.value.admin,
      max_storage: form.value.max_storage,
      permission: form.value.permission
    }
    if (form.value.password) {
      params.password = form.value.password
    }

    if (isEdit.value) {
      await conn.updateUser(params)
    } else {
      await conn.addUser(params)
    }
    
    ElMessage.success(t('users.success'))
    dialogVisible.value = false
    loadUsers()
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('users.failed'))
  }
}
</script>

<template>
  <el-card shadow="hover" class="w-full">
    <template #header>
      <div class="flex justify-between items-center">
        <div class="font-bold flex items-center gap-2">
          <el-icon><User /></el-icon>
          {{ t('menu.users') }}
        </div>
        <el-button type="primary" size="small" @click="handleAdd">
          <el-icon class="mr-1"><Plus /></el-icon>
          {{ t('users.addUser') }}
        </el-button>
      </div>
    </template>

    <div v-loading="loading">
      <el-table :data="users" style="width: 100%">
        <el-table-column prop="username" :label="t('users.username')" />
        <el-table-column :label="t('users.role')">
          <template #default="{ row }">
            <el-tag :type="row.is_admin ? 'danger' : 'success'">
              {{ row.is_admin ? t('dashboard.admin') : t('dashboard.user') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.storage')">
          <template #default="{ row }">
            {{ row.max_storage ? `${(row.max_storage / (1024 * 1024 * 1024)).toFixed(2)} GB` : t('dashboard.unlimited') }}
          </template>
        </el-table-column>
        <el-table-column :label="t('users.actions')" width="150" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)" :disabled="row.username === userStore.userInfo?.username">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? t('users.edit') : t('users.addUser')"
      width="500px"
    >
      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('users.username')">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item :label="t('users.password')">
          <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? 'Leave blank to keep unchanged' : ''" />
        </el-form-item>
        <el-form-item :label="t('users.role')">
          <el-switch v-model="form.admin" :active-text="t('dashboard.admin')" :inactive-text="t('dashboard.user')" />
        </el-form-item>
        <el-form-item :label="t('users.storage')">
          <el-input v-model="form.max_storage" placeholder="e.g. 100G" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">Cancel</el-button>
          <el-button type="primary" @click="handleSubmit">Confirm</el-button>
        </span>
      </template>
    </el-dialog>
  </el-card>
</template>
