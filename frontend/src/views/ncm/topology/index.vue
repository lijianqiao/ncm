<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, h } from 'vue'
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
  NButtonGroup,
} from 'naive-ui'
import { $alert } from '@/utils/alert'
import {
  getTopology,
  getTopologyLinks,
  refreshTopology,
  getTopologyTaskStatus,
  rebuildTopologyCache,
  resetTopology,
  type TopologyResponse,
  type TopologyLinkItem,
  type TopologyTaskStatus,
  type TopologyNode,
} from '@/api/topology'
import { useTaskPolling } from '@/composables'
import { formatDateTime } from '@/utils/date'
import { globalOtpFlow } from '@/composables/useOtpFlow'

defineOptions({
  name: 'TopologyManagement',
})

const dialog = useDialog()

// ==================== 拓扑数据 ====================

const topologyData = ref<TopologyResponse | null>(null)
const loading = ref(false)
const networkContainer = ref<HTMLDivElement | null>(null)
const networkContainerHeight = ref('600px')
const isFullscreen = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let networkInstance: any = null
let isUnmounted = false // 防止异步导入完成后组件已卸载

const fetchTopology = async () => {
  loading.value = true
  try {
    const res = await getTopology()
    topologyData.value = res.data
  } catch {
    // Error handled
  } finally {
    loading.value = false
  }
  await nextTick()
  renderNetwork()
}

const layoutMode = ref<'force' | 'hierarchical'>('force')

const getNodeGroupOptions = (group?: string) => {
  switch (group) {
    case 'core':
      return { shape: 'diamond', color: '#e74c3c' }
    case 'distribution':
      return { shape: 'square', color: '#f39c12' }
    case 'access':
      return { shape: 'dot', color: '#3498db' }
    case 'unknown':
      return { shape: 'triangle', color: '#999999' }
    default:
      return { shape: 'dot', color: '#909399' }
  }
}

const updateNetworkContainerHeight = () => {
  if (!networkContainer.value) return
  const viewportHeight = window.innerHeight
  const isElementFullscreen = document.fullscreenElement === networkContainer.value
  const rect = networkContainer.value.getBoundingClientRect()
  const next = Math.max(520, isElementFullscreen ? viewportHeight : viewportHeight - rect.top - 24)
  networkContainerHeight.value = `${Math.floor(next)}px`
  if (networkInstance?.setSize) {
    networkInstance.setSize('100%', networkContainerHeight.value)
  }
}

const handleFullscreenChange = () => {
  isFullscreen.value = document.fullscreenElement === networkContainer.value
  updateNetworkContainerHeight()
  networkInstance?.fit()
}

const renderNetwork = async () => {
  if (!topologyData.value || !networkContainer.value || isUnmounted) return

  try {
    // 动态导入 vis-network
    const { Network, DataSet } = await import('vis-network/standalone')

    // 异步导入完成后再次检查组件是否已卸载
    if (isUnmounted || !networkContainer.value) return

    const nodes = new DataSet(
      topologyData.value.nodes.map((node) => {
        const style = getNodeGroupOptions(node.group)
        return {
          id: node.id,
          label: node.label,
          title: node.title || `IP: ${node.ip || node.ip_address || 'N/A'}\n厂商: ${node.vendor || 'N/A'}`,
          shape: style.shape,
          color: style.color,
          size: node.size || 20,
        }
      }),
    )

    const edges = new DataSet(
      topologyData.value.edges.map((edge) => ({
        id: edge.id,
        from: edge.from,
        to: edge.to,
        title: edge.title || `${edge.source_interface || edge.local_port || '?'} <-> ${edge.target_interface || edge.remote_port || '?'}`,
        arrows: edge.arrows || 'to,from',
        smooth: { enabled: true, type: 'continuous', roundness: 0.3 },
      })),
    )

    const options = {
      nodes: {
        font: { size: 14, color: '#333' },
        borderWidth: 2,
      },
      edges: {
        width: 2,
        color: { color: '#848484', highlight: '#2B7CE9' },
      },
      physics: {
        enabled: layoutMode.value === 'force',
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
      layout: {
        hierarchical:
          layoutMode.value === 'hierarchical'
            ? {
              enabled: true,
              direction: 'UD',
              sortMethod: 'directed',
              nodeSpacing: 150,
              levelSpacing: 150,
            }
            : { enabled: false },
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
    updateNetworkContainerHeight()
    networkInstance.fit()

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

const toggleLayout = (mode: 'force' | 'hierarchical') => {
  if (layoutMode.value === mode) return
  layoutMode.value = mode
  renderNetwork() // 重新渲染以应用布局变化
}

onMounted(() => {
  fetchTopology()
  window.addEventListener('resize', updateNetworkContainerHeight)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  nextTick(() => updateNetworkContainerHeight())
})

onUnmounted(() => {
  isUnmounted = true // 标记组件已卸载
  if (networkInstance) {
    networkInstance.destroy()
    networkInstance = null
  }
  window.removeEventListener('resize', updateNetworkContainerHeight)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
})

// ==================== 节点详情 ====================

const showNodeDetail = ref(false)
const selectedNode = ref<TopologyNode | null>(null)

// ==================== 图例数据 ====================
const legendItems = [
  { label: '核心层', color: '#e74c3c', shape: 'diamond' },
  { label: '汇聚层', color: '#f39c12', shape: 'square' },
  { label: '接入层', color: '#3498db', shape: 'dot' },
  { label: '未知设备', color: '#999999', shape: 'triangle' },
]

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
  // 自定义完成判断：otp_required 也算完成（需要用户介入）
  isComplete: (status) => {
    const completedStatuses = ['SUCCESS', 'FAILURE', 'success', 'failed', 'REVOKED', 'otp_required']
    return completedStatuses.includes(status.status)
  },
  onComplete: (status) => {
    // 检查是否需要 OTP
    if (status.status === 'otp_required' && status.result?.otp_required) {
      const result = status.result
      // 打开 OTP 弹窗，输入成功后重新发起任务
      globalOtpFlow.open(
        {
          dept_id: result.otp_dept_id || '未知',
          device_group: result.otp_device_group || '未知',
          failed_devices: result.otp_failed_devices || [],
          message: status.error || '需要输入 OTP 验证码',
        },
        async () => {
          // OTP 验证成功后，重新发起拓扑刷新任务
          closeRefreshModal()
          await doRefreshTopology()
        },
      )
      return
    }
    // 正常完成，刷新拓扑数据
    fetchTopology()
  },
})

const taskPolling = isPolling

// 实际执行刷新拓扑的逻辑（可被 OTP 回调复用）
const doRefreshTopology = async () => {
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
    // Error handled by global interceptor
  }
}

const handleRefreshTopology = () => {
  dialog.info({
    title: '刷新拓扑',
    content: '确定要刷新网络拓扑吗？这将重新采集所有设备的 LLDP 邻居信息。',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: doRefreshTopology,
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

// 重置拓扑（清除所有链路后重新采集）
const handleResetTopology = () => {
  dialog.error({
    title: '重置拓扑',
    content: () =>
      h('div', { style: 'white-space: pre-line' }, [
        '此操作将清除所有拓扑链路数据，然后重新采集。',
        '\n\n通常在以下情况使用：',
        '\n• 设备大规模变更后需要重建拓扑',
        '\n• 拓扑数据累积过多需要清理',
        '\n• 切换网络环境后需要重新采集',
        '\n\n确定要重置拓扑吗？',
      ]),
    positiveText: '确认重置',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        // 1. 清除所有链路
        const resetRes = await resetTopology(false)
        $alert.success(`已清除 ${resetRes.data.deleted_links} 条链路`)

        // 2. 重新采集
        await doRefreshTopology()
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

const handleToggleFullscreen = async () => {
  if (!networkContainer.value) return
  if (document.fullscreenElement === networkContainer.value) {
    await document.exitFullscreen()
    return
  }
  await networkContainer.value.requestFullscreen()
}
</script>

<template>
  <div class="topology-management">
    <!-- 统计卡片 -->
    <n-card class="stats-card" :bordered="false" size="small">
      <n-grid :cols="5" :x-gap="16">
        <n-grid-item>
          <n-statistic label="节点总数" :value="topologyData?.stats?.total_nodes || 0" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="链路总数" :value="topologyData?.stats?.total_edges || 0" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="CMDB 已录入" :value="topologyData?.stats?.cmdb_devices || 0">
            <template #suffix>
              <span style="font-size: 12px; color: #18a058">已纳管</span>
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="未知设备" :value="topologyData?.stats?.unknown_devices || 0">
            <template #suffix>
              <span style="font-size: 12px; color: #d03050">未纳管</span>
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-space vertical align="end">
            <n-space>
              <n-button type="primary" @click="handleRefreshTopology" :loading="loading">
                刷新拓扑
              </n-button>
              <n-button type="warning" @click="handleResetTopology">重置拓扑</n-button>
              <n-button @click="handleShowLinks">链路列表</n-button>
              <n-button @click="handleExport">导出</n-button>
              <n-button @click="handleRebuildCache">重建缓存</n-button>
            </n-space>
            <div v-if="topologyData?.stats?.collected_at" style="font-size: 12px; color: #999">
              采集时间: {{ formatDateTime(topologyData.stats.collected_at) }}
            </div>
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
            <n-button-group size="small">
              <n-button :type="layoutMode === 'force' ? 'primary' : 'default'" @click="toggleLayout('force')">
                力导向布局
              </n-button>
              <n-button :type="layoutMode === 'hierarchical' ? 'primary' : 'default'"
                @click="toggleLayout('hierarchical')">
                分层布局
              </n-button>
            </n-button-group>
            <n-button size="small" @click="handleFitView">适应视图</n-button>
            <n-button size="small" @click="fetchTopology" :loading="loading">刷新</n-button>
            <n-button size="small" @click="handleToggleFullscreen">
              {{ isFullscreen ? '退出全屏' : '全屏' }}
            </n-button>
          </n-space>
        </n-space>
      </template>
      <div ref="networkContainer" class="network-container" :class="{ 'network-container--fullscreen': isFullscreen }"
        :style="{ height: networkContainerHeight }">
        <div v-if="loading" class="loading-container">加载中...</div>
        <div class="legend-overlay">
          <div v-for="item in legendItems" :key="item.label" class="legend-item">
            <span class="legend-icon"
              :style="{ backgroundColor: item.color, borderRadius: item.shape === 'dot' ? '50%' : '0' }"></span>
            <span class="legend-label">{{ item.label }}</span>
          </div>
        </div>
      </div>
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
              <td>{{ selectedNode.ip || selectedNode.ip_address || '-' }}</td>
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
              <td>设备分组</td>
              <td>{{ selectedNode.device_group || selectedNode.group || '-' }}</td>
            </tr>
            <tr>
              <td>设备状态</td>
              <td>{{ selectedNode.status || '-' }}</td>
            </tr>
            <tr>
              <td>纳管状态</td>
              <td>{{ selectedNode.in_cmdb ? '已纳管' : '未纳管' }}</td>
            </tr>
          </tbody>
        </n-table>
      </template>
    </n-modal>

    <!-- 链路列表 Modal -->
    <n-modal v-model:show="showLinksModal" preset="card" title="链路列表" class="links-modal">
      <div v-if="linksLoading" style="text-align: center; padding: 40px">加载中...</div>
      <template v-else>
        <div class="links-table-container">
          <table class="links-table">
            <thead>
              <tr>
                <th>源设备</th>
                <th>源端口</th>
                <th>目标设备</th>
                <th>目标端口</th>
                <th>链路类型</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="link in links" :key="link.id">
                <td>{{ link.source_device_name || link.source_device_id }}</td>
                <td>{{ link.source_interface }}</td>
                <td>{{ link.target_device_name || link.target_hostname || link.target_device_id || '-' }}</td>
                <td>{{ link.target_interface || '-' }}</td>
                <td>{{ link.link_type || '-' }}</td>
              </tr>
              <tr v-if="links.length === 0">
                <td colspan="5" style="text-align: center">暂无链路数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </n-modal>

    <!-- 刷新任务状态 Modal -->
    <n-modal v-model:show="showRefreshModal" preset="card" title="拓扑采集任务" style="width: 500px" :closable="!taskPolling"
      :mask-closable="!taskPolling" @close="closeRefreshModal">
      <template v-if="taskStatus">
        <n-space vertical style="width: 100%">
          <div style="text-align: center">
            <p>任务 ID: {{ taskStatus.task_id }}</p>
            <p>状态: {{ taskStatus.status }}</p>
          </div>
          <n-progress v-if="taskStatus.progress !== null" type="line" :percentage="taskStatus.progress" :status="taskStatus.status === 'SUCCESS'
            ? 'success'
            : taskStatus.status === 'FAILURE'
              ? 'error'
              : 'default'
            " />
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
        <div v-if="taskStatus.status === 'SUCCESS' || taskStatus.status === 'FAILURE'"
          style="margin-top: 20px; text-align: right">
          <n-button @click="closeRefreshModal">关闭</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.topology-management {
  height: 100%;
  min-height: 100vh;
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
  min-height: 600px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.topology-card :deep(.n-card__content) {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.network-container {
  flex: 1;
  min-height: 500px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  position: relative;
}

.network-container--fullscreen {
  border-radius: 0;
}

.legend-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.legend-icon {
  width: 12px;
  height: 12px;
  display: inline-block;
}

.loading-container {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.7);
  z-index: 5;
}
</style>

<style>
/* 链路列表弹窗样式（需要全局样式因为modal使用teleport） */
.links-modal {
  width: 900px;
  max-height: 80vh;
}

.links-modal .n-card__content {
  padding: 0 !important;
  max-height: calc(80vh - 80px);
  overflow: hidden;
}

.links-table-container {
  max-height: calc(80vh - 100px);
  overflow-y: auto;
}

.links-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.links-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
}

.links-table th {
  background: #fafafc;
  padding: 12px 8px;
  text-align: left;
  font-weight: 500;
  border-bottom: 1px solid #e0e0e6;
  white-space: nowrap;
}

.links-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #e0e0e6;
  word-break: break-all;
}

.links-table tbody tr:hover {
  background: #f5f5f5;
}
</style>
