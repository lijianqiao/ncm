<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import {
  NButton,
  NModal,
  NSpace,
  NCard,
  NStatistic,
  NGrid,
  NGridItem,
  NTable,
  NProgress,
  NAlert,
  useDialog,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getTopology,
  getTopologyLinks,
  refreshTopology,
  getTopologyTaskStatus,
  rebuildTopologyCache,
  type TopologyResponse,
  type TopologyLinkItem,
  type TopologyTaskStatus,
} from '@/api/topology'
import { useTaskPolling } from '@/composables'

defineOptions({
  name: 'TopologyManagement',
})

const dialog = useDialog()

// ==================== 拓扑数据 ====================

const topologyData = ref<TopologyResponse | null>(null)
const loading = ref(false)
const networkContainer = ref<HTMLDivElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let networkInstance: any = null
let isUnmounted = false // 防止异步导入完成后组件已卸载

const fetchTopology = async () => {
  loading.value = true
  try {
    const res = await getTopology()
    topologyData.value = res.data
    await nextTick()
    renderNetwork()
  } catch {
    // Error handled
  } finally {
    loading.value = false
  }
}

const renderNetwork = async () => {
  if (!topologyData.value || !networkContainer.value || isUnmounted) return

  try {
    // 动态导入 vis-network
    const { Network, DataSet } = await import('vis-network/standalone')

    // 异步导入完成后再次检查组件是否已卸载
    if (isUnmounted || !networkContainer.value) return

    const nodes = new DataSet(
      topologyData.value.nodes.map((node) => ({
        id: node.id,
        label: node.label,
        title: `IP: ${node.ip_address || 'N/A'}\n厂商: ${node.vendor || 'N/A'}\n状态: ${node.status || 'N/A'}`,
        shape: getNodeShape(node.device_type),
        color: getNodeColor(node.status),
      })),
    )

    const edges = new DataSet(
      topologyData.value.edges.map((edge) => ({
        id: edge.id,
        from: edge.from,
        to: edge.to,
        title: `${edge.local_port || ''} <-> ${edge.remote_port || ''}`,
        arrows: 'to,from',
        // vis-network 类型要求包含 enabled/roundness，避免 vue-tsc 报错
        smooth: { enabled: true, type: 'continuous', roundness: 0.3 },
      })),
    )

    const options = {
      nodes: {
        font: { size: 14 },
        borderWidth: 2,
      },
      edges: {
        width: 2,
        color: { color: '#848484', highlight: '#2B7CE9' },
      },
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 150,
          springConstant: 0.08,
        },
        stabilization: {
          iterations: 100,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        navigationButtons: true,
        keyboard: true,
      },
    }

    if (networkInstance) {
      networkInstance.destroy()
    }

    networkInstance = new Network(networkContainer.value, { nodes, edges }, options)

    networkInstance.on('click', (params: { nodes: Array<string | number> }) => {
      if (params.nodes.length > 0) {
        const nodeId = String(params.nodes[0])
        const node = topologyData.value?.nodes.find((n) => n.id === nodeId)
        if (node) {
          selectedNode.value = node
          showNodeDetail.value = true
        }
      }
    })
  } catch (error) {
    console.error('Failed to load vis-network:', error)
    $alert.error('加载拓扑可视化库失败，请确保已安装 vis-network')
  }
}

const getNodeShape = (deviceType: string | null): string => {
  switch (deviceType) {
    case 'router':
      return 'diamond'
    case 'switch':
      return 'box'
    case 'firewall':
      return 'triangle'
    case 'server':
      return 'database'
    default:
      return 'dot'
  }
}

const getNodeColor = (status: string | null): string => {
  switch (status) {
    case 'active':
      return '#18a058'
    case 'maintenance':
      return '#f0a020'
    case 'offline':
      return '#d03050'
    default:
      return '#909399'
  }
}

onMounted(() => {
  fetchTopology()
})

onUnmounted(() => {
  isUnmounted = true // 标记组件已卸载
  if (networkInstance) {
    networkInstance.destroy()
    networkInstance = null
  }
})

// ==================== 节点详情 ====================

const showNodeDetail = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const selectedNode = ref<any>(null)

// ==================== 链路列表 ====================

const showLinksModal = ref(false)
const links = ref<TopologyLinkItem[]>([])
const linksLoading = ref(false)

const handleShowLinks = async () => {
  linksLoading.value = true
  showLinksModal.value = true
  try {
    const res = await getTopologyLinks({ page_size: 100 })
    links.value = res.data.items || []
  } catch {
    showLinksModal.value = false
  } finally {
    linksLoading.value = false
  }
}

// ==================== 刷新拓扑 ====================

const showRefreshModal = ref(false)

// 使用 useTaskPolling composable
const {
  taskStatus,
  start: startPollingTaskStatus,
  stop: stopPollingTaskStatus,
  reset: resetTask,
  isPolling,
} = useTaskPolling<TopologyTaskStatus>((taskId) => getTopologyTaskStatus(taskId), {
  onComplete: () => fetchTopology(),
})

const taskPolling = isPolling

const handleRefreshTopology = () => {
  dialog.info({
    title: '刷新拓扑',
    content: '确定要刷新网络拓扑吗？这将重新采集所有设备的 LLDP 邻居信息。',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await refreshTopology({ async_mode: true })
        if (res.data.task_id) {
          $alert.success('拓扑采集任务已提交')
          showRefreshModal.value = true
          startPollingTaskStatus(res.data.task_id)
        } else {
          $alert.success('拓扑刷新请求已完成')
          fetchTopology()
        }
      } catch {
        // Error handled
      }
    },
  })
}

const closeRefreshModal = () => {
  stopPollingTaskStatus()
  showRefreshModal.value = false
  resetTask()
}

// ==================== 重建缓存 ====================

const handleRebuildCache = () => {
  dialog.warning({
    title: '重建拓扑缓存',
    content: '确定要重建拓扑缓存吗？',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await rebuildTopologyCache()
        $alert.success('拓扑缓存重建任务已提交')
      } catch {
        // Error handled
      }
    },
  })
}

// ==================== 导出 ====================

const handleExport = () => {
  if (!topologyData.value) {
    $alert.warning('暂无拓扑数据')
    return
  }
  const dataStr = JSON.stringify(topologyData.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `topology_${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}

// ==================== 操作按钮 ====================

const handleFitView = () => {
  if (networkInstance) {
    networkInstance.fit()
  }
}
</script>

<template>
  <div class="topology-management">
    <!-- 统计卡片 -->
    <n-card class="stats-card" :bordered="false" size="small">
      <n-grid :cols="4" :x-gap="16">
        <n-grid-item>
          <n-statistic label="节点数" :value="topologyData?.stats?.total_nodes || 0" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="链路数" :value="topologyData?.stats?.total_edges || 0" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="设备类型">
            <template #default>
              {{ Object.keys(topologyData?.stats?.device_types || {}).length }} 种
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-space>
            <n-button type="primary" @click="handleRefreshTopology" :loading="loading">
              刷新拓扑
            </n-button>
            <n-button @click="handleShowLinks">链路列表</n-button>
            <n-button @click="handleExport">导出</n-button>
            <n-button @click="handleRebuildCache">重建缓存</n-button>
          </n-space>
        </n-grid-item>
      </n-grid>
    </n-card>

    <!-- 拓扑图容器 -->
    <n-card class="topology-card" :bordered="false" size="small">
      <template #header>
        <n-space justify="space-between" align="center">
          <span>网络拓扑图</span>
          <n-space>
            <n-button size="small" @click="handleFitView">适应视图</n-button>
            <n-button size="small" @click="fetchTopology" :loading="loading">刷新</n-button>
          </n-space>
        </n-space>
      </template>
      <div v-if="loading" class="loading-container">加载中...</div>
      <div v-else ref="networkContainer" class="network-container"></div>
    </n-card>

    <!-- 节点详情 Modal -->
    <n-modal v-model:show="showNodeDetail" preset="card" title="节点详情" style="width: 400px">
      <template v-if="selectedNode">
        <n-table :bordered="false" :single-line="false">
          <tbody>
            <tr>
              <td>名称</td>
              <td>{{ selectedNode.label }}</td>
            </tr>
            <tr>
              <td>IP 地址</td>
              <td>{{ selectedNode.ip_address || '-' }}</td>
            </tr>
            <tr>
              <td>设备类型</td>
              <td>{{ selectedNode.device_type || '-' }}</td>
            </tr>
            <tr>
              <td>厂商</td>
              <td>{{ selectedNode.vendor || '-' }}</td>
            </tr>
            <tr>
              <td>状态</td>
              <td>{{ selectedNode.status || '-' }}</td>
            </tr>
          </tbody>
        </n-table>
      </template>
    </n-modal>

    <!-- 链路列表 Modal -->
    <n-modal v-model:show="showLinksModal" preset="card" title="链路列表" style="width: 900px">
      <div v-if="linksLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else>
        <n-table :bordered="false" :single-line="false">
          <thead>
            <tr>
              <th>源设备ID</th>
              <th>源端口</th>
              <th>目标设备ID</th>
              <th>目标端口</th>
              <th>链路类型</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="link in links" :key="link.id">
              <td>{{ link.source_device_id }}</td>
              <td>{{ link.source_interface }}</td>
              <td>{{ link.target_device_id || '-' }}</td>
              <td>{{ link.target_interface || '-' }}</td>
              <td>{{ link.link_type || '-' }}</td>
            </tr>
            <tr v-if="links.length === 0">
              <td colspan="5" style="text-align: center">暂无链路数据</td>
            </tr>
          </tbody>
        </n-table>
      </template>
    </n-modal>

    <!-- 刷新任务状态 Modal -->
    <n-modal
      v-model:show="showRefreshModal"
      preset="card"
      title="拓扑采集任务"
      style="width: 500px"
      :closable="!taskPolling"
      :mask-closable="!taskPolling"
      @close="closeRefreshModal"
    >
      <template v-if="taskStatus">
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ taskStatus.task_id }}</p>
            <p>状态: {{ taskStatus.status }}</p>
          </div>
          <n-progress
            v-if="taskStatus.progress !== null"
            type="line"
            :percentage="taskStatus.progress"
            :status="
              taskStatus.status === 'SUCCESS'
                ? 'success'
                : taskStatus.status === 'FAILURE'
                  ? 'error'
                  : 'default'
            "
          />
          <template v-if="taskStatus.result">
            <div style="text-align: center">
              <p>总设备: {{ taskStatus.result.total_devices }}</p>
              <p>成功: {{ taskStatus.result.success_count }}</p>
              <p>失败: {{ taskStatus.result.failed_count }}</p>
              <p>新链路: {{ taskStatus.result.new_links }}</p>
            </div>
          </template>
          <n-alert v-if="taskStatus.error" type="error" :title="taskStatus.error" />
        </n-space>
        <div
          v-if="taskStatus.status === 'SUCCESS' || taskStatus.status === 'FAILURE'"
          style="margin-top: 20px; text-align: right"
        >
          <n-button @click="closeRefreshModal">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.topology-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.stats-card {
  border-radius: 8px;
}

.topology-card {
  flex: 1;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.topology-card :deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.network-container {
  flex: 1;
  min-height: 500px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
}

.loading-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}
</style>
