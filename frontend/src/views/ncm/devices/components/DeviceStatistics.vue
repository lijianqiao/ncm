<!--
@Author: li
@Email: lijianqiao2906@live.com
@FileName: DeviceStatistics.vue
@DateTime: 2026-01-12
@Docs: 设备生命周期统计卡片组件
-->

<script setup lang="ts">
import { NCard, NGrid, NGridItem, NStatistic } from 'naive-ui'

interface Props {
  /** 入库设备数 */
  stock: number
  /** 运行中设备数 */
  running: number
  /** 维护中设备数 */
  maintenance: number
  /** 已报废设备数 */
  retired: number
  /** 总设备数 */
  total: number
}

withDefaults(defineProps<Props>(), {
  stock: 0,
  running: 0,
  maintenance: 0,
  retired: 0,
  total: 0,
})
</script>

<template>
  <n-card class="device-statistics" :bordered="false" size="small">
    <n-grid :cols="5" :x-gap="16">
      <n-grid-item>
        <n-statistic label="总设备数" :value="total" />
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="入库">
          <template #default>
            <span class="text-gray">{{ stock }}</span>
          </template>
        </n-statistic>
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="运行中">
          <template #default>
            <span class="text-success">{{ running }}</span>
          </template>
        </n-statistic>
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="维护中">
          <template #default>
            <span class="text-warning">{{ maintenance }}</span>
          </template>
        </n-statistic>
      </n-grid-item>
      <n-grid-item>
        <n-statistic label="已报废">
          <template #default>
            <span class="text-error">{{ retired }}</span>
          </template>
        </n-statistic>
      </n-grid-item>
    </n-grid>
  </n-card>
</template>

<style scoped>
.device-statistics {
  border-radius: 8px;
}

.text-gray {
  color: #909399;
}

.text-success {
  color: #18a058;
}

.text-warning {
  color: #f0a020;
}

.text-error {
  color: #d03050;
}
</style>
