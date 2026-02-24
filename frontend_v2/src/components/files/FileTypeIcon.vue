<script setup lang="ts">
import { computed } from 'vue'
import {
  Box,
  Cpu,
  Document,
  Files,
  Grid,
  Headset,
  Picture,
  VideoPlay,
} from '@element-plus/icons-vue'

const props = defineProps<{
  url?: string
  mimeType?: string
}>()

const extension = computed(() => {
  if (!props.url) return ''
  const cleanUrl = props.url.split('?')[0]
  return cleanUrl.split('.').pop()?.toLowerCase() || ''
})

const iconComponent = computed(() => {
  const mime = (props.mimeType || '').toLowerCase()

  if (mime.startsWith('image/')) return Picture
  if (mime.startsWith('video/')) return VideoPlay
  if (mime.startsWith('audio/')) return Headset
  if (mime.startsWith('text/')) return Document

  if (mime === 'application/pdf') return Files

  if (
    mime.includes('json') ||
    mime.includes('xml') ||
    mime.includes('javascript') ||
    mime.includes('typescript')
  ) {
    return Cpu
  }

  if (
    mime.includes('spreadsheet') ||
    mime.includes('excel') ||
    mime.includes('csv')
  ) {
    return Grid
  }

  if (
    mime.includes('zip') ||
    mime.includes('rar') ||
    mime.includes('tar') ||
    mime.includes('compressed')
  ) {
    return Box
  }

  if (
    [
      'js',
      'ts',
      'jsx',
      'tsx',
      'vue',
      'py',
      'java',
      'c',
      'cpp',
      'h',
      'hpp',
      'go',
      'rs',
      'sh',
      'sql',
      'html',
      'css',
      'json',
      'xml',
      'yml',
      'yaml',
    ].includes(extension.value)
  ) {
    return Cpu
  }

  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(extension.value)) {
    return Picture
  }

  if (['mp4', 'webm', 'mkv', 'avi', 'mov'].includes(extension.value)) {
    return VideoPlay
  }

  if (['mp3', 'wav', 'flac', 'aac', 'ogg'].includes(extension.value)) {
    return Headset
  }

  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(extension.value)) {
    return Box
  }

  if (['xls', 'xlsx', 'csv'].includes(extension.value)) {
    return Grid
  }

  if (extension.value === 'pdf') {
    return Files
  }

  return Document
})
</script>

<template>
  <component :is="iconComponent" />
</template>