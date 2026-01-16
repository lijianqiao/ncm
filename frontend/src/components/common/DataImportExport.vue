<script setup lang="ts">
import { ref } from 'vue'
import {
  NButton,
  NIcon,
  NModal,
  NCheckbox,
  NAlert,
  NUpload,
  NUploadDragger,
  NSpace,
} from 'naive-ui'
import { CloudUploadOutline as ImportIcon, DownloadOutline as ExportIcon } from '@vicons/ionicons5'
import { $alert } from '@/utils/alert'
import type {
  ResponseBase,
  ImportValidateResponse,
  ImportCommitRequest,
  ImportCommitResponse,
} from '@/types/api'
import type { AxiosResponse } from 'axios'

// ==================== Props & Emits ====================

const props = withDefaults(
  defineProps<{
    /** 模块标题，用于显示和文件名生成 */
    title?: string
    /** 是否显示导入按钮 */
    showImport?: boolean
    /** 是否显示导出按钮 */
    showExport?: boolean
    /** 导出文件名（不含扩展名），默认使用 title + _export */
    exportName?: string
    /** 导入模板文件名 */
    templateName?: string
    /** 允许覆盖的提示文本 */
    overwriteText?: string

    // API Functions
    /** 导出 API */
    exportApi?: (fmt?: 'csv' | 'xlsx') => Promise<AxiosResponse<Blob>>
    /** 下载模板 API */
    importTemplateApi?: () => Promise<AxiosResponse<Blob>>
    /** 上传校验 API */
    importValidateApi?: (
      file: File,
      allowOverwrite: boolean,
    ) => Promise<ResponseBase<ImportValidateResponse>>
    /** 确认导入 API */
    importCommitApi?: (data: ImportCommitRequest) => Promise<ResponseBase<ImportCommitResponse>>
  }>(),
  {
    title: '数据',
    showImport: false,
    showExport: false,
    templateName: 'import_template.xlsx',
    overwriteText: '允许覆盖（根据唯一标识）',
  },
)

const emit = defineEmits<{
  (e: 'success'): void
}>()

// ==================== Export Logic ====================

const exporting = ref(false)

const getFilenameFromContentDisposition = (value: string | null | undefined) => {
  if (!value) return null
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const match = value.match(/filename="?([^"]+)"?/i)
  return match?.[1] || null
}

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

const handleExportCsv = async () => {
  if (!props.exportApi) return

  exporting.value = true
  try {
    const res = await props.exportApi('csv')
    const cd = res.headers?.['content-disposition'] as string | undefined
    const defaultName = props.exportName || `${props.title}_export.csv`
    const filename = getFilenameFromContentDisposition(cd) || defaultName
    downloadBlob(res.data, filename)
    $alert.success('导出已开始')
  } catch (e) {
    // 错误通常由拦截器处理，这里可补充处理
    console.error(e)
  } finally {
    exporting.value = false
  }
}

// ==================== Import Logic ====================

const showImportModal = ref(false)
const importUploading = ref(false)
const importCommitting = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<ImportValidateResponse | null>(null)
const allowOverwrite = ref(false)

const handleDownloadImportTemplate = async () => {
  if (!props.importTemplateApi) return

  try {
    const res = await props.importTemplateApi()
    const cd = res.headers?.['content-disposition'] as string | undefined
    const filename = getFilenameFromContentDisposition(cd) || props.templateName
    downloadBlob(res.data, filename)
  } catch (e) {
    console.error(e)
  }
}

const resetImportState = () => {
  importFile.value = null
  importResult.value = null
  allowOverwrite.value = false
}

const handleOpenImport = () => {
  resetImportState()
  showImportModal.value = true
}

const handleImportFileChange = (options: { file: { file?: File | null } }) => {
  importFile.value = options.file.file || null
  importResult.value = null
}

const handleUploadAndValidate = async () => {
  if (!props.importValidateApi) return
  if (!importFile.value) {
    $alert.warning('请选择要导入的文件')
    return
  }

  importUploading.value = true
  try {
    const res = await props.importValidateApi(importFile.value, allowOverwrite.value)
    importResult.value = res.data
    if (importResult.value.error_rows > 0) {
      $alert.warning('存在校验错误，整批不可导入')
    } else {
      $alert.success('校验通过，可确认导入')
    }
  } catch (e) {
    console.error(e)
  } finally {
    importUploading.value = false
  }
}

const handleCommitImport = async () => {
  if (!props.importCommitApi || !importResult.value) return

  if (importResult.value.error_rows > 0) {
    $alert.warning('存在校验错误，无法导入')
    return
  }

  importCommitting.value = true
  try {
    await props.importCommitApi({
      import_id: importResult.value.import_id,
      checksum: importResult.value.checksum,
      allow_overwrite: allowOverwrite.value,
    })
    $alert.success('导入成功')
    showImportModal.value = false
    emit('success')
  } catch (e) {
    console.error(e)
  } finally {
    importCommitting.value = false
  }
}
</script>

<template>
  <div class="data-import-export" style="display: inline-block">
    <n-space>
      <!-- Export Button -->
      <n-button v-if="showExport" circle secondary title="导出 CSV" :loading="exporting"
        :disabled="exporting || !exportApi" @click="handleExportCsv">
        <template #icon>
          <n-icon>
            <ExportIcon />
          </n-icon>
        </template>
      </n-button>

      <!-- Import Button -->
      <n-button v-if="showImport" circle type="primary" secondary title="导入" :disabled="!importValidateApi"
        @click="handleOpenImport">
        <template #icon>
          <n-icon>
            <ImportIcon />
          </n-icon>
        </template>
      </n-button>
    </n-space>

    <!-- Import Modal -->
    <n-modal v-model:show="showImportModal" preset="dialog" :title="`导入${title}`" style="width: 720px"
      @after-leave="resetImportState">
      <n-space vertical>
        <n-alert type="info" title="导入流程" :bordered="false">
          上传文件后会进行全量校验；只要有一行错误，整批不会导入。
        </n-alert>

        <n-upload :default-upload="false" :max="1" accept=".csv,.xlsx,.xlsm,.xls" @change="handleImportFileChange">
          <n-upload-dragger>
            <div style="padding: 12px 0">点击或拖拽上传 CSV / Excel</div>
          </n-upload-dragger>
        </n-upload>

        <n-space justify="space-between">
          <n-button tertiary @click="handleDownloadImportTemplate" :disabled="!importTemplateApi">
            下载模板
          </n-button>
          <n-space>
            <n-checkbox v-model:checked="allowOverwrite">{{ overwriteText }}</n-checkbox>
            <n-button type="primary" :loading="importUploading" :disabled="importUploading || !importFile"
              @click="handleUploadAndValidate">
              上传并校验
            </n-button>
          </n-space>
        </n-space>

        <n-alert v-if="importResult" :type="importResult.error_rows > 0 ? 'warning' : 'success'" :bordered="false">
          总行数：{{ importResult.total_rows }}；可导入：{{ importResult.valid_rows }}；错误行：{{
            importResult.error_rows
          }}
        </n-alert>

        <div v-if="importResult?.errors?.length">
          <n-alert type="warning" :bordered="false" title="错误明细（最多展示前 200 条）">
            <div v-for="(e, idx) in importResult.errors" :key="idx">
              第 {{ e.row_number }} 行：{{ e.field ? e.field + ' - ' : '' }}{{ e.message }}
            </div>
          </n-alert>
        </div>
      </n-space>

      <template #action>
        <n-button @click="showImportModal = false">取消</n-button>
        <n-button type="primary" :loading="importCommitting" :disabled="!importResult || importResult.error_rows > 0 || importUploading || importCommitting
          " @click="handleCommitImport">
          确认导入
        </n-button>
      </template>
    </n-modal>
  </div>
</template>
