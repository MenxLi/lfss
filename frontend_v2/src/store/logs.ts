import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export interface LogEntry {
    id: number
    timestamp: number
    type: 'success' | 'warning' | 'info' | 'error'
    message: string
}

export const useLogStore = defineStore('logs', () => {
    const logs = ref<LogEntry[]>([])
    let nextId = 1
    const MAX_TOAST_MESSAGE_LENGTH = 180

    const addLog = (type: LogEntry['type'], message: string) => {
        logs.value.unshift({
            id: nextId++,
            timestamp: Date.now(),
            type,
            message
        })

        // Keep only last 1000 logs
        if (logs.value.length > 1000) {
            logs.value.pop()
        }
    }

    const clearLogs = () => {
        logs.value = []
    }

    const logMessage = (type: LogEntry['type'], message: string) => {
        addLog(type, message)

        const displayMessage = message.length > MAX_TOAST_MESSAGE_LENGTH
            ? `${message.slice(0, MAX_TOAST_MESSAGE_LENGTH)}...`
            : message

        ElMessage({
            type,
            message: displayMessage
        })
    }

    return {
        logs,
        addLog,
        clearLogs,
        logMessage
    }
})
