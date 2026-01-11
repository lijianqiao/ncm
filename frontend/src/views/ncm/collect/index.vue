<script setup lang="ts">
import { ref } from 'vue'
import {
  NButton,
  NModal,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NCard,
  NTable,
  NProgress,
  NAlert,
  NTabs,
  NTabPane,
  NCheckbox,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  collectDevice,
  batchCollectAsync,
  getCollectTaskStatus,
  getDeviceARPTable,
  getDeviceMACTable,
  locateIP,
  locateMAC,
  type ARPTableResponse,
  type MACTableResponse,
  type CollectTaskStatus,
  type LocateResponse,
} from '@/api/collect'
import { getDevices, type Device } from '@/api/devices'
import { formatDateTime } from '@/utils/date'
import { useTaskPolling } from '@/composables'

defineOptions({
  name: 'CollectManagement',
})

// ==================== 设备选项 ====================

const deviceOptions = ref<{ label: string; value: string }[]>([])
const deviceLoading = ref(false)

const fetchDevices = async () => {
  deviceLoading.value = true
  try {
    const res = await getDevices({ status: 'active', page_size: 100 })
    deviceOptions.value = res.data.items.map((d: Device) => ({
      label: `${d.name} (${d.ip_address})`,
      value: d.id,
    }))
  } catch {
    // Error handled
  } finally {
    deviceLoading.value = false
  }
}

// ==================== 手动采集 ====================

const showCollectModal = ref(false)
const collectModel = ref({
  device_id: '',
})
const collectLoading = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const collectResult = ref<any>(null)

const handleManualCollect = async () => {
  await fetchDevices()
  collectModel.value.device_id = ''
  collectResult.value = null
  showCollectModal.value = true
}

const submitManualCollect = async () => {
  if (!collectModel.value.device_id) {
    $alert.warning('请选择设备')
    return
  }
  collectLoading.value = true
  try {
    const res = await collectDevice(collectModel.value.device_id)
    collectResult.value = res.data
    $alert.success('采集完成')
  } catch {
    // Error handled
  } finally {
    collectLoading.value = false
  }
}

// ==================== 批量采集 ====================

const showBatchCollectModal = ref(false)
const batchCollectModel = ref({
  device_ids: [] as string[],
  collect_arp: true,
  collect_mac: true,
  otp_code: '',
})

// 使用 useTaskPolling composable
const {
  taskStatus: batchTaskStatus,
  start: startPollingTaskStatus,
  stop: stopPollingTaskStatus,
  reset: resetBatchTask,
} = useTaskPolling<CollectTaskStatus>((taskId) => getCollectTaskStatus(taskId))

const handleBatchCollect = async () => {
  await fetchDevices()
  batchCollectModel.value = {
    device_ids: [],
    collect_arp: true,
    collect_mac: true,
    otp_code: '',
  }
  resetBatchTask()
  showBatchCollectModal.value = true
}

const submitBatchCollect = async () => {
  if (batchCollectModel.value.device_ids.length === 0) {
    $alert.warning('请选择设备')
    return
  }
  try {
    const res = await batchCollectAsync({
      device_ids: batchCollectModel.value.device_ids,
      collect_arp: batchCollectModel.value.collect_arp,
      collect_mac: batchCollectModel.value.collect_mac,
      otp_code: batchCollectModel.value.otp_code || undefined,
    })
    $alert.success('批量采集任务已提交')
    startPollingTaskStatus(res.data.task_id)
  } catch {
    // Error handled
  }
}

const closeBatchCollectModal = () => {
  stopPollingTaskStatus()
  showBatchCollectModal.value = false
  resetBatchTask()
}

// ==================== 查看 ARP/MAC 表 ====================

const showTableModal = ref(false)
const tableType = ref<'arp' | 'mac'>('arp')
const tableData = ref<ARPTableResponse | MACTableResponse | null>(null)
const tableLoading = ref(false)
const selectedDeviceForTable = ref('')

const handleViewTable = async (type: 'arp' | 'mac') => {
  await fetchDevices()
  tableType.value = type
  selectedDeviceForTable.value = ''
  tableData.value = null
  showTableModal.value = true
}

const fetchTable = async () => {
  if (!selectedDeviceForTable.value) {
    $alert.warning('请选择设备')
    return
  }
  tableLoading.value = true
  try {
    if (tableType.value === 'arp') {
      const res = await getDeviceARPTable(selectedDeviceForTable.value)
      tableData.value = res.data
    } else {
      const res = await getDeviceMACTable(selectedDeviceForTable.value)
      tableData.value = res.data
    }
  } catch {
    // Error handled
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
        <n-button @click="handleViewTable('arp')">查看 ARP 表</n-button>
        <n-button @click="handleViewTable('mac')">查看 MAC 表</n-button>
        <n-button type="warning" @click="handleLocate('ip')">IP 定位</n-button>
        <n-button type="warning" @click="handleLocate('mac')">MAC 定位</n-button>
      </n-space>
    </n-card>

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
          <n-alert type="success" title="采集完成">
            <p>设备: {{ collectResult.device_name }}</p>
            <p>ARP 条目: {{ collectResult.arp_count }}</p>
            <p>MAC 条目: {{ collectResult.mac_count }}</p>
            <p>采集时间: {{ formatDateTime(collectResult.collected_at) }}</p>
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
          <n-form-item label="OTP 验证码（可选）">
            <n-input v-model:value="batchCollectModel.otp_code" placeholder="如果设备需要 OTP" />
          </n-form-item>
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
              <p>总数: {{ batchTaskStatus.result.total }}</p>
              <p>成功: {{ batchTaskStatus.result.success_count }}</p>
              <p>失败: {{ batchTaskStatus.result.failed_count }}</p>
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

    <!-- 查看 ARP/MAC 表 Modal -->
    <n-modal
      v-model:show="showTableModal"
      preset="card"
      :title="`查看 ${tableType.toUpperCase()} 表`"
      style="width: 900px; max-height: 80vh"
    >
      <n-space vertical style="width: 100%">
        <n-space>
          <n-select
            v-model:value="selectedDeviceForTable"
            :options="deviceOptions"
            :loading="deviceLoading"
            placeholder="请选择设备"
            filterable
            style="width: 300px"
          />
          <n-button type="primary" :loading="tableLoading" @click="fetchTable">查询</n-button>
        </n-space>
        <template v-if="tableData">
          <div>
            <p>设备: {{ tableData.device_name }}</p>
            <p>采集时间: {{ formatDateTime(tableData.collected_at) }}</p>
            <p>条目数: {{ tableData.entries.length }}</p>
          </div>
          <n-table :bordered="false" :single-line="false" style="max-height: 400px; overflow: auto">
            <thead>
              <tr v-if="tableType === 'arp'">
                <th>IP 地址</th>
                <th>MAC 地址</th>
                <th>接口</th>
                <th>VLAN</th>
                <th>类型</th>
              </tr>
              <tr v-else>
                <th>MAC 地址</th>
                <th>VLAN</th>
                <th>接口</th>
                <th>类型</th>
              </tr>
            </thead>
            <tbody>
              <template v-if="tableType === 'arp'">
                <tr v-for="(entry, index) in (tableData as ARPTableResponse).entries" :key="index">
                  <td>{{ entry.ip_address }}</td>
                  <td>{{ entry.mac_address }}</td>
                  <td>{{ entry.interface }}</td>
                  <td>{{ entry.vlan || '-' }}</td>
                  <td>{{ entry.type || '-' }}</td>
                </tr>
              </template>
              <template v-else>
                <tr v-for="(entry, index) in (tableData as MACTableResponse).entries" :key="index">
                  <td>{{ entry.mac_address }}</td>
                  <td>{{ entry.vlan }}</td>
                  <td>{{ entry.interface }}</td>
                  <td>{{ entry.type || '-' }}</td>
                </tr>
              </template>
              <tr v-if="tableData.entries.length === 0">
                <td :colspan="tableType === 'arp' ? 5 : 4" style="text-align: center">暂无数据</td>
              </tr>
            </tbody>
          </n-table>
        </template>
      </n-space>
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
            <p v-if="locateResult.located_at">定位时间: {{ formatDateTime(locateResult.located_at) }}</p>
          </n-alert>
        </template>
      </n-space>
    </n-modal>
  </div>
</template>

<style scoped>
.collect-management {
  height: 100%;
}

.p-4 {
  padding: 16px;
}
</style>
