<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import Connector from '@/api'
import type { UserRecord } from '@/api'
import { useUserStore } from '@/store/user'
import { useI18n } from 'vue-i18n'

type PeerLevel = 'READ' | 'WRITE'
type PeerItem = { username: string, level: PeerLevel }

const props = defineProps<{
  visible: boolean
  username: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
  (e: 'saved'): void
}>()

const { t } = useI18n()
const userStore = useUserStore()

const conn = new Connector()
conn.config = {
  endpoint: localStorage.getItem('endpoint') || window.location.origin,
  token: userStore.token
}

const loading = ref(false)
const saving = ref(false)
const optionsLoading = ref(false)
const candidateQuery = ref('')
const candidateOptions = ref<UserRecord[]>([])
const selectedCandidate = ref('')
const selectedLevel = ref<PeerLevel>('READ')
const peers = ref<PeerItem[]>([])
const incoming = ref(true)

const initialPeerMap = ref<Map<string, PeerLevel>>(new Map())

const visibleProxy = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value)
})

const sortedPeers = computed(() => {
  return [...peers.value].sort((a, b) => a.username.localeCompare(b.username))
})

const refreshCurrentPeers = async () => {
  if (!props.username) {
    peers.value = []
    return
  }

  loading.value = true
  try {
    const [readPeers, writePeers] = await Promise.all([
      conn.listPeers({ level: 1, incoming: incoming.value, admin: false, as_user: props.username }),
      conn.listPeers({ level: 2, incoming: incoming.value, admin: false, as_user: props.username })
    ])

    const map = new Map<string, PeerLevel>()

    for (const peer of readPeers) {
      map.set(peer.username, 'READ')
    }
    for (const peer of writePeers) {
      map.set(peer.username, 'WRITE')
    }

    initialPeerMap.value = new Map(map)
    peers.value = [...map.entries()].map(([username, level]) => ({ username, level }))
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('users.loadPeersFailed'))
  } finally {
    loading.value = false
  }
}

const searchUsers = async (query?: string) => {
  optionsLoading.value = true
  try {
    const results = await conn.listUsers({
      username_filter: query || undefined,
      include_virtual: true,
      order_by: 'username',
      limit: 20
    })
    const existing = new Set(peers.value.map((peer) => peer.username))
    candidateOptions.value = results.filter(
      (user) => user.username !== props.username && !existing.has(user.username)
    )
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('users.searchUsersFailed'))
  } finally {
    optionsLoading.value = false
  }
}

const addPeer = () => {
  if (!selectedCandidate.value) {
    return
  }
  if (peers.value.some((peer) => peer.username === selectedCandidate.value)) {
    return
  }
  peers.value.push({ username: selectedCandidate.value, level: selectedLevel.value })
  selectedCandidate.value = ''
  selectedLevel.value = 'READ'
  searchUsers(candidateQuery.value)
}

const removePeer = (username: string) => {
  peers.value = peers.value.filter((peer) => peer.username !== username)
  searchUsers(candidateQuery.value)
}

const savePeers = async () => {
  saving.value = true
  try {
    const currentMap = new Map<string, PeerLevel>()
    for (const peer of peers.value) {
      currentMap.set(peer.username, peer.level)
    }

    const changedUsers = new Set<string>([
      ...initialPeerMap.value.keys(),
      ...currentMap.keys()
    ])

    for (const username of changedUsers) {
      const before = initialPeerMap.value.get(username)
      const after = currentMap.get(username)
      if (before === after) {
        continue
      }

      const srcUsername = incoming.value ? username : props.username
      const dstUsername = incoming.value ? props.username : username
      await conn.setPeer(srcUsername, dstUsername, after ?? 'NONE')
    }

    initialPeerMap.value = new Map(currentMap)
    ElMessage.success(t('users.peersSaved'))
    emit('saved')
    visibleProxy.value = false
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err.message || t('users.savePeersFailed'))
  } finally {
    saving.value = false
  }
}

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      candidateQuery.value = ''
      selectedCandidate.value = ''
      selectedLevel.value = 'READ'
      incoming.value = true
      await refreshCurrentPeers()
      await searchUsers('')
    }
  }
)

watch(incoming, async () => {
  if (!props.visible) {
    return
  }
  await refreshCurrentPeers()
  await searchUsers(candidateQuery.value)
})
</script>

<template>
  <el-dialog
    v-model="visibleProxy"
    :title="t('users.peerEditorFor', { username })"
    width="700px"
  >
    <div class="space-y-4" v-loading="loading">
      <div class="grid grid-cols-1 md:grid-cols-[1fr,140px,auto] gap-3 items-center">
        <el-select
          v-model="selectedCandidate"
          filterable
          remote
          clearable
          :remote-method="searchUsers"
          :loading="optionsLoading"
          :placeholder="t('users.searchUsersPlaceholder')"
        >
          <el-option
            v-for="item in candidateOptions"
            :key="item.username"
            :label="item.username"
            :value="item.username"
          />
        </el-select>

        <div class="flex gap-2 items-center">
          <el-select v-model="selectedLevel">
            <el-option value="READ" :label="t('dashboard.accessRead')" />
            <el-option value="WRITE" :label="t('dashboard.accessWrite')" />
          </el-select>
          <!-- <el-checkbox v-model="incoming">
            {{ t('users.incomingAccess') }}
          </el-checkbox> -->
          <el-switch v-model="incoming"
            :active-text="t('dashboard.incomingAccess')" 
            :inactive-text="t('dashboard.outcomingAccess')" 
            inline-prompt/>
        </div>


        <el-button type="primary" @click="addPeer" :disabled="!selectedCandidate">
          {{ t('users.addPeer') }}
        </el-button>
      </div>

      <el-table :data="sortedPeers" size="small" max-height="340">
        <el-table-column prop="username" :label="t('users.peerUser')" min-width="220" />
        <el-table-column :label="t('users.accessLevel')" width="180">
          <template #default="{ row }">
            <el-select v-model="row.level" size="small">
              <el-option value="READ" :label="t('dashboard.accessRead')" />
              <el-option value="WRITE" :label="t('dashboard.accessWrite')" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="removePeer(row.username)">
              {{ t('users.removePeer') }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="t('users.noPeers')" >
          </el-empty> 
        </template>
      </el-table>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visibleProxy = false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="savePeers">{{ t('users.savePeers') }}</el-button>
      </span>
    </template>
  </el-dialog>
</template>
