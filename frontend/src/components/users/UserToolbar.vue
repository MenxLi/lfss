<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const searchQuery = defineModel<string>('searchQuery', { default: '' })
const includeVirtual = defineModel<boolean>('includeVirtual', { default: false })

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'refresh'): void
}>()
</script>

<template>
  <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
    <div class="font-bold flex items-center gap-2">
      <el-icon><User /></el-icon>
      {{ t('menu.users') }}
    </div>
    <div class="flex flex-wrap lg:flex-nowrap items-center gap-2 w-full sm:w-auto">
      <el-input
        v-model="searchQuery"
        :placeholder="t('users.searchPlaceholder')"
        clearable
        class="w-full sm:w-44 lg:w-40 xl:w-44"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-checkbox v-model="includeVirtual">
        {{ t('users.showVirtualUsers') }}
      </el-checkbox>
      <el-button @click="emit('refresh')">
        <el-icon class="mr-1"><Refresh /></el-icon>
        {{ t('users.refresh') }}
      </el-button>
      <el-button type="primary" @click="emit('add')">
        <el-icon class="mr-1"><Plus /></el-icon>
        {{ t('users.addUser') }}
      </el-button>
    </div>
  </div>
</template>
