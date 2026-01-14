<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NCard,
  NDataTable,
  NProgress,
  NAlert,
  NTabs,
  NTabPane,
  NDivider,
  NCheckbox,
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  collectDevice,
  batchCollectAsync,
  getCollectTaskStatus,
  getDeviceARPTable,
  getDeviceMACTable,
  locateIP,
  locateMAC,
  type ARPEntry,
  type ARPTableResponse,
  type MACEntry,
  type MACTableResponse,
  type CollectTaskStatus,
  type LocateResponse,
  type DeviceCollectResult,
} from '@/api/collect'
import { type Device } from '@/api/devices'
import { formatDateTime } from '@/utils/date'
import { useDeviceOptions, useOtpFlow, useTaskPolling } from '@/composables'
import OtpModal from '@/components/common/OtpModal.vue'

defineOptions({
  name: 'CollectManagement',
})

// ==================== 设备选项 ====================

const {
  deviceOptions,
  loading: deviceLoading,
  load: loadDevices,
  getDevice,
} = useDeviceOptions({
  status: 'active',
})

// ==================== 手动采集 ====================

const showCollectModal = ref(false)
const collectModel = ref({
  device_id: '',
})
const collectLoading = ref(false)
const collectResult = ref<DeviceCollectResult | null>(null)

const getSelectedDevice = (deviceId: string): Device | null => {
  if (!deviceId) return null
  return getDevice(deviceId)
}

const isOtpManualDevice = (device: Device | null): boolean => {
  if (!device) return false
  return String(device.auth_type) === 'otp_manual'
}

const handleManualCollect = async () => {
  await loadDevices()
  collectModel.value.device_id = ''
  collectResult.value = null
  showCollectModal.value = true
}

const otpFlow = useOtpFlow({ length: 6 })
const showOTPModal = otpFlow.show
const otpLoading = otpFlow.loading
const otpInfoItems = otpFlow.infoItems
const submitOTP = otpFlow.confirm
const closeOTP = otpFlow.close

const getRequestErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) return error.message
  const maybe = error as { message?: unknown }
  if (typeof maybe?.message === 'string' && maybe.message.trim()) return maybe.message
  return '请求失败'
}

const runManualCollect = async (deviceId: string, otpCode?: string) => {
  collectLoading.value = true
  try {
    const res = await collectDevice(deviceId, otpCode ? { otp_code: otpCode } : undefined)
    collectResult.value = res.data
    if (res.data.success) {
      $alert.success('采集完成')
    } else {
      $alert.error(res.data.error_message || res.message || '采集失败')
    }
  } catch (error: unknown) {
    const err = error as { response?: { status?: number } }
    if (err?.response?.status === 428) throw error

    const device = getSelectedDevice(deviceId)
    collectResult.value = {
      device_id: deviceId,
      device_name: device?.name || null,
      success: false,
      arp_count: 0,
      mac_count: 0,
      error_message: getRequestErrorMessage(error),
      duration_ms: null,
    }
  } finally {
    collectLoading.value = false
  }
}

const submitManualCollect = async () => {
  if (!collectModel.value.device_id) {
    $alert.warning('请选择设备')
    return
  }

  const device = getSelectedDevice(collectModel.value.device_id)
  if (isOtpManualDevice(device)) {
    otpFlow.open(
      {
        dept_id: device?.dept_id || '',
        device_group: String(device?.device_group || 'access'),
        failed_devices: [],
      },
      async (otpCode) => {
        await runManualCollect(collectModel.value.device_id, otpCode)
      },
    )
    return
  }

  await runManualCollect(collectModel.value.device_id)
}

// ==================== 批量采集 ====================

const showBatchCollectModal = ref(false)
const batchCollectModel = ref({
  device_ids: [] as string[],
  collect_arp: true,
  collect_mac: true,
})

// 使用 useTaskPolling composable
const {
  taskStatus: batchTaskStatus,
  isPolling: batchTaskPolling,
  start: startPollingTaskStatus,
  stop: stopPollingTaskStatus,
  reset: resetBatchTask,
} = useTaskPolling<CollectTaskStatus>((taskId) => getCollectTaskStatus(taskId))

const hasAutoPromptedOtpRetry = ref(false)

const handleBatchCollect = async () => {
  await loadDevices()
  batchCollectModel.value = {
    device_ids: [],
    collect_arp: true,
    collect_mac: true,
  }
  hasAutoPromptedOtpRetry.value = false
  resetBatchTask()
  showBatchCollectModal.value = true
}

const submitBatchCollect = async () => {
  if (batchCollectModel.value.device_ids.length === 0) {
    $alert.warning('请选择设备')
    return
  }

  // 如果包含 otp_manual 且未输入 OTP，则先弹 OTP（减少一次无效任务提交）
  const selectedDevices = batchCollectModel.value.device_ids
    .map((id) => getSelectedDevice(id))
    .filter((d): d is Device => Boolean(d))
  const otpManualDevices = selectedDevices.filter((d) => String(d.auth_type) === 'otp_manual')

  if (otpManualDevices.length > 0) {
    const groups = new Set(
      otpManualDevices.map((d) => `${d.dept_id || 'null'}::${String(d.device_group || 'null')}`),
    )
    if (groups.size === 1) {
      const first = otpManualDevices[0]!
      otpFlow.open(
        {
          dept_id: first.dept_id || '',
          device_group: String(first.device_group || 'access'),
          failed_devices: [],
        },
        async (otpCode) => {
          await submitBatchCollectInternal(otpCode)
        },
      )
      return
    }
    $alert.warning('所选设备包含多个部门/分组的 OTP 手动认证设备，建议按部门+分组分批采集')
  }

  await submitBatchCollectInternal()
}

const submitBatchCollectInternal = async (otpCode?: string) => {
  try {
    if (otpCode && !/^\d{6}$/.test(otpCode)) {
      $alert.warning('OTP 验证码需为 6 位数字')
      return
    }
    const res = await batchCollectAsync({
      device_ids: batchCollectModel.value.device_ids,
      collect_arp: batchCollectModel.value.collect_arp,
      collect_mac: batchCollectModel.value.collect_mac,
      otp_code: otpCode || undefined,
    })
    $alert.success('批量采集任务已提交')
    startPollingTaskStatus(res.data.task_id)
  } catch (error: unknown) {
    otpFlow.tryHandleOtpRequired(error, async (nextOtp) => {
      await submitBatchCollectInternal(nextOtp)
    })
  }
}

const otpExpiredDeviceIdsFromTask = computed(() => {
  const result = batchTaskStatus.value?.result
  if (!result?.results?.length) return []
  const matched = result.results
    .filter((r) => !r.success && (r.error_message || '').includes('需要输入 OTP'))
    .map((r) => r.device_id)
  return Array.from(new Set(matched))
})

const retryOtpExpiredDevices = () => {
  const ids = otpExpiredDeviceIdsFromTask.value
  if (ids.length === 0) {
    $alert.warning('没有需要重试的设备')
    return
  }
  batchCollectModel.value.device_ids = ids
  const first = getSelectedDevice(ids[0] || '')
  otpFlow.open(
    {
      dept_id: first?.dept_id || '',
      device_group: String(first?.device_group || 'access'),
      failed_devices: [],
    },
    async (otpCode) => {
      await submitBatchCollectInternal(otpCode)
    },
  )
}

const closeBatchCollectModal = () => {
  stopPollingTaskStatus()
  showBatchCollectModal.value = false
  hasAutoPromptedOtpRetry.value = false
  resetBatchTask()
}

watch(
  () => batchTaskStatus.value?.status,
  (status) => {
    if (!status) return
    if (status !== 'SUCCESS' && status !== 'FAILURE') return
    if (hasAutoPromptedOtpRetry.value) return
    if (otpExpiredDeviceIdsFromTask.value.length === 0) return

    hasAutoPromptedOtpRetry.value = true
    retryOtpExpiredDevices()
  },
)

// ==================== 查看 ARP/MAC 表 ====================

const activeTableTab = ref<'arp' | 'mac'>('arp')
const tableLoading = ref(false)

const arpTableData = ref<ARPTableResponse | null>(null)
const macTableData = ref<MACTableResponse | null>(null)
const selectedDeviceForTable = ref('')

const arpSearch = ref('')
const macSearch = ref('')

const normalizeText = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  return String(value).toLowerCase()
}

const filterArpEntries = computed(() => {
  const entries = (arpTableData.value?.entries || []) as ARPEntry[]
  const q = normalizeText(arpSearch.value).trim()
  if (!q) return entries
  return entries.filter((e: ARPEntry) => {
    const text = [
      e.ip_address,
      e.mac_address,
      e.interface,
      e.vlan_id,
      e.vlan,
      e.entry_type,
      e.type,
      e.updated_at,
    ]
      .map(normalizeText)
      .join(' ')
    return text.includes(q)
  })
})

const filterMacEntries = computed(() => {
  const entries = (macTableData.value?.entries || []) as MACEntry[]
  const q = normalizeText(macSearch.value).trim()
  if (!q) return entries
  return entries.filter((e: MACEntry) => {
    const text = [
      e.mac_address,
      e.interface,
      e.vlan_id,
      e.vlan,
      e.entry_type,
      e.type,
      e.state,
      e.updated_at,
    ]
      .map(normalizeText)
      .join(' ')
    return text.includes(q)
  })
})

const compareText = (a: unknown, b: unknown): number =>
  normalizeText(a).localeCompare(normalizeText(b))
const compareDateTime = (a: unknown, b: unknown): number => {
  const ta = Date.parse(String(a ?? ''))
  const tb = Date.parse(String(b ?? ''))
  const va = Number.isFinite(ta) ? ta : 0
  const vb = Number.isFinite(tb) ? tb : 0
  return va - vb
}
const compareVlan = (a: unknown, b: unknown): number => {
  const na = Number.parseInt(String(a ?? ''), 10)
  const nb = Number.parseInt(String(b ?? ''), 10)
  const va = Number.isFinite(na) ? na : Number.MAX_SAFE_INTEGER
  const vb = Number.isFinite(nb) ? nb : Number.MAX_SAFE_INTEGER
  return va - vb
}

const arpColumns = computed<DataTableColumns<ARPEntry>>(() => {
  return [
    {
      title: 'IP 地址',
      key: 'ip_address',
      sorter: (r1: ARPEntry, r2: ARPEntry) => compareText(r1.ip_address, r2.ip_address),
    },
    {
      title: 'MAC 地址',
      key: 'mac_address',
      sorter: (r1: ARPEntry, r2: ARPEntry) => compareText(r1.mac_address, r2.mac_address),
    },
    {
      title: '接口',
      key: 'interface',
      render: (row: ARPEntry) => row.interface || '-',
      sorter: (r1: ARPEntry, r2: ARPEntry) => compareText(r1.interface, r2.interface),
    },
    {
      title: 'VLAN',
      key: 'vlan_id',
      render: (row: ARPEntry) => row.vlan_id || row.vlan || '-',
      sorter: (r1: ARPEntry, r2: ARPEntry) =>
        compareVlan(r1.vlan_id || r1.vlan, r2.vlan_id || r2.vlan),
    },
    {
      title: '类型',
      key: 'entry_type',
      render: (row: ARPEntry) => row.entry_type || row.type || '-',
      sorter: (r1: ARPEntry, r2: ARPEntry) =>
        compareText(r1.entry_type || r1.type, r2.entry_type || r2.type),
    },
    {
      title: '最后更新时间',
      key: 'updated_at',
      render: (row: ARPEntry) => (row.updated_at ? formatDateTime(row.updated_at) : '-'),
      sorter: (r1: ARPEntry, r2: ARPEntry) => compareDateTime(r1.updated_at, r2.updated_at),
    },
  ]
})

const macColumns = computed<DataTableColumns<MACEntry>>(() => {
  return [
    {
      title: 'MAC 地址',
      key: 'mac_address',
      sorter: (r1: MACEntry, r2: MACEntry) => compareText(r1.mac_address, r2.mac_address),
    },
    {
      title: 'VLAN',
      key: 'vlan_id',
      render: (row: MACEntry) => row.vlan_id || row.vlan || '-',
      sorter: (r1: MACEntry, r2: MACEntry) =>
        compareVlan(r1.vlan_id || r1.vlan, r2.vlan_id || r2.vlan),
    },
    {
      title: '接口',
      key: 'interface',
      render: (row: MACEntry) => row.interface || '-',
      sorter: (r1: MACEntry, r2: MACEntry) => compareText(r1.interface, r2.interface),
    },
    {
      title: '类型',
      key: 'entry_type',
      render: (row: MACEntry) => row.entry_type || row.type || '-',
      sorter: (r1: MACEntry, r2: MACEntry) =>
        compareText(r1.entry_type || r1.type, r2.entry_type || r2.type),
    },
    {
      title: '状态',
      key: 'state',
      render: (row: MACEntry) => row.state || '-',
      sorter: (r1: MACEntry, r2: MACEntry) => compareText(r1.state, r2.state),
    },
    {
      title: '最后更新时间',
      key: 'updated_at',
      render: (row: MACEntry) => (row.updated_at ? formatDateTime(row.updated_at) : '-'),
      sorter: (r1: MACEntry, r2: MACEntry) => compareDateTime(r1.updated_at, r2.updated_at),
    },
  ]
})

const ensureTableDevicesLoaded = async () => {
  if (deviceOptions.value.length === 0) {
    await loadDevices()
  }
}

const fetchTables = async () => {
  await ensureTableDevicesLoaded()
  if (!selectedDeviceForTable.value) {
    $alert.warning('请选择设备')
    return
  }
  tableLoading.value = true
  try {
    const deviceId = selectedDeviceForTable.value
    const [arpResult, macResult] = await Promise.allSettled([
      getDeviceARPTable(deviceId),
      getDeviceMACTable(deviceId),
    ])

    if (arpResult.status === 'fulfilled') {
      arpTableData.value = arpResult.value.data
    }
    if (macResult.status === 'fulfilled') {
      macTableData.value = macResult.value.data
    }
  } finally {
    tableLoading.value = false
  }
}

// ==================== IP/MAC 定位 ====================

const showLocateModal = ref(false)
const locateType = ref<'ip' | 'mac'>('ip')
const locateQuery = ref('')
const locateResult = ref<LocateResponse | null>(null)
const locateLoading = ref(false)

const handleLocate = (type: 'ip' | 'mac') => {
  locateType.value = type
  locateQuery.value = ''
  locateResult.value = null
  showLocateModal.value = true
}

const submitLocate = async () => {
  if (!locateQuery.value) {
    $alert.warning(`请输入${locateType.value === 'ip' ? 'IP' : 'MAC'}地址`)
    return
  }
  locateLoading.value = true
  try {
    if (locateType.value === 'ip') {
      const res = await locateIP(locateQuery.value)
      locateResult.value = res.data
    } else {
      const res = await locateMAC(locateQuery.value)
      locateResult.value = res.data
    }
  } catch {
    // Error handled
  } finally {
    locateLoading.value = false
  }
}
</script>

<template>
  <div class="collect-management p-4">
    <n-card title="ARP/MAC 采集与定位" :bordered="false">
      <n-space>
        <n-button type="primary" @click="handleManualCollect">手动采集</n-button>
        <n-button type="info" @click="handleBatchCollect">批量采集</n-button>
        <n-button type="warning" @click="handleLocate('ip')">IP 定位</n-button>
        <n-button type="warning" @click="handleLocate('mac')">MAC 定位</n-button>
      </n-space>
    </n-card>

    <n-divider style="margin: 16px 0" />

    <div>
      <n-space align="center" style="margin-bottom: 12px">
        <n-select
          v-model:value="selectedDeviceForTable"
          :options="deviceOptions"
          :loading="deviceLoading"
          placeholder="选择设备查看表数据"
          filterable
          style="width: 360px"
          @focus="() => loadDevices()"
        />
        <n-button type="primary" :loading="tableLoading" @click="fetchTables"> 查询 </n-button>
      </n-space>

      <n-tabs v-model:value="activeTableTab" type="line" animated>
        <n-tab-pane name="arp" tab="ARP 表">
          <n-space vertical style="width: 100%">
            <n-space justify="space-between" align="center">
              <div>
                <div>设备: {{ arpTableData?.device_name || '-' }}</div>
                <div v-if="arpTableData?.cached_at">
                  缓存时间: {{ formatDateTime(arpTableData.cached_at) }}
                </div>
                <div v-else>缓存时间: -</div>
                <div>条目数: {{ arpTableData?.total ?? 0 }}</div>
              </div>
              <n-input
                v-model:value="arpSearch"
                placeholder="搜索：IP/MAC/接口/VLAN/类型"
                clearable
                style="max-width: 360px"
              />
            </n-space>

            <n-data-table
              :columns="arpColumns"
              :data="filterArpEntries"
              :bordered="false"
              :single-line="false"
              :max-height="520"
              size="small"
            />
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="mac" tab="MAC 表">
          <n-space vertical style="width: 100%">
            <n-space justify="space-between" align="center">
              <div>
                <div>设备: {{ macTableData?.device_name || '-' }}</div>
                <div v-if="macTableData?.cached_at">
                  缓存时间: {{ formatDateTime(macTableData.cached_at) }}
                </div>
                <div v-else>缓存时间: -</div>
                <div>条目数: {{ macTableData?.total ?? 0 }}</div>
              </div>
              <n-input
                v-model:value="macSearch"
                placeholder="搜索：MAC/接口/VLAN/类型/状态"
                clearable
                style="max-width: 360px"
              />
            </n-space>

            <n-data-table
              :columns="macColumns"
              :data="filterMacEntries"
              :bordered="false"
              :single-line="false"
              :max-height="520"
              size="small"
            />
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </div>

    <!-- 手动采集 Modal -->
    <n-modal v-model:show="showCollectModal" preset="card" title="手动采集" style="width: 500px">
      <n-space vertical style="width: 100%">
        <n-form-item label="选择设备">
          <n-select
            v-model:value="collectModel.device_id"
            :options="deviceOptions"
            :loading="deviceLoading"
            placeholder="请选择设备"
            filterable
          />
        </n-form-item>
        <n-button type="primary" :loading="collectLoading" @click="submitManualCollect">
          开始采集
        </n-button>
        <template v-if="collectResult">
          <n-alert
            :type="collectResult.success ? 'success' : 'error'"
            :title="collectResult.success ? '采集完成' : '采集失败'"
          >
            <p>设备: {{ collectResult.device_name }}</p>
            <p>ARP 条目: {{ collectResult.arp_count }}</p>
            <p>MAC 条目: {{ collectResult.mac_count }}</p>
            <p v-if="collectResult.duration_ms !== null">
              耗时: {{ collectResult.duration_ms }} ms
            </p>
            <p v-if="!collectResult.success">原因: {{ collectResult.error_message || '-' }}</p>
          </n-alert>
        </template>
      </n-space>
    </n-modal>

    <!-- 批量采集 Modal -->
    <n-modal
      v-model:show="showBatchCollectModal"
      preset="card"
      title="批量采集"
      style="width: 600px"
      :closable="!batchTaskPolling"
      :mask-closable="!batchTaskPolling"
      @close="closeBatchCollectModal"
    >
      <template v-if="!batchTaskStatus">
        <n-space vertical style="width: 100%">
          <n-form-item label="选择设备">
            <n-select
              v-model:value="batchCollectModel.device_ids"
              :options="deviceOptions"
              :loading="deviceLoading"
              placeholder="请选择设备"
              filterable
              multiple
              max-tag-count="responsive"
            />
          </n-form-item>
          <n-space>
            <n-checkbox v-model:checked="batchCollectModel.collect_arp">采集 ARP</n-checkbox>
            <n-checkbox v-model:checked="batchCollectModel.collect_mac">采集 MAC</n-checkbox>
          </n-space>
        </n-space>
        <div style="margin-top: 20px; text-align: right">
          <n-space>
            <n-button @click="closeBatchCollectModal">取消</n-button>
            <n-button type="primary" @click="submitBatchCollect">开始采集</n-button>
          </n-space>
        </div>
      </template>
      <template v-else>
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ batchTaskStatus.task_id }}</p>
            <p>状态: {{ batchTaskStatus.status }}</p>
          </div>
          <n-progress
            v-if="batchTaskStatus.progress !== null"
            type="line"
            :percentage="batchTaskStatus.progress"
            :status="
              batchTaskStatus.status === 'SUCCESS'
                ? 'success'
                : batchTaskStatus.status === 'FAILURE'
                  ? 'error'
                  : 'default'
            "
          />
          <template v-if="batchTaskStatus.result">
            <div style="text-align: center">
              <p>总数: {{ batchTaskStatus.result.total_devices }}</p>
              <p>成功: {{ batchTaskStatus.result.success_count }}</p>
              <p>失败: {{ batchTaskStatus.result.failed_count }}</p>
            </div>
            <div style="text-align: center" v-if="otpExpiredDeviceIdsFromTask.length > 0">
              <n-button type="warning" @click="retryOtpExpiredDevices">
                OTP 失效，输入新 OTP 重试失败设备（{{ otpExpiredDeviceIdsFromTask.length }}）
              </n-button>
            </div>
          </template>
          <n-alert v-if="batchTaskStatus.error" type="error" :title="batchTaskStatus.error" />
        </n-space>
        <div
          v-if="batchTaskStatus.status === 'SUCCESS' || batchTaskStatus.status === 'FAILURE'"
          style="margin-top: 20px; text-align: right"
        >
          <n-button @click="closeBatchCollectModal">关闭</n-button>
        </div>
      </template>
    </n-modal>

    <!-- IP/MAC 定位 Modal -->
    <n-modal
      v-model:show="showLocateModal"
      preset="card"
      :title="`${locateType.toUpperCase()} 地址定位`"
      style="width: 500px"
    >
      <n-space vertical style="width: 100%">
        <n-form-item :label="`输入 ${locateType.toUpperCase()} 地址`">
          <n-input
            v-model:value="locateQuery"
            :placeholder="locateType === 'ip' ? '例如: 192.168.1.100' : '例如: aa:bb:cc:dd:ee:ff'"
          />
        </n-form-item>
        <n-button type="primary" :loading="locateLoading" @click="submitLocate">定位</n-button>
        <template v-if="locateResult">
          <n-alert type="info" title="定位结果">
            <p v-if="locateResult.ip_address">IP 地址: {{ locateResult.ip_address }}</p>
            <p>MAC 地址: {{ locateResult.mac_address }}</p>
            <p>设备: {{ locateResult.device_name || locateResult.device_id || '未知' }}</p>
            <p>接口: {{ locateResult.interface || '-' }}</p>
            <p>VLAN: {{ locateResult.vlan || '-' }}</p>
            <p v-if="locateResult.located_at">
              定位时间: {{ formatDateTime(locateResult.located_at) }}
            </p>
          </n-alert>
        </template>
      </n-space>
    </n-modal>

    <OtpModal
      v-model:show="showOTPModal"
      :loading="otpLoading"
      :info-items="otpInfoItems"
      @update:show="(v) => (!v ? closeOTP() : undefined)"
      @confirm="submitOTP"
    />
  </div>
</template>

<style scoped>
.collect-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}

.otp-center {
  width: 100%;
  display: flex;
  justify-content: center;
}
</style>
