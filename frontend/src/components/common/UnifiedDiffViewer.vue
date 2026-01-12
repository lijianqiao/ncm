<script setup lang="ts">
import { computed } from 'vue'

type DiffLineKind = 'meta' | 'hunk' | 'add' | 'del' | 'ctx'

const props = withDefaults(
  defineProps<{
    diff?: string | null
    maxHeight?: number | string
  }>(),
  {
    diff: '',
    maxHeight: 600,
  },
)

const diffLines = computed(() => {
  const content = props.diff || ''
  return content ? content.split('\n') : []
})

const normalizeMaxHeight = (v: number | string): string => {
  if (typeof v === 'number') return `${v}px`
  return v
}

const getDiffLineKind = (line: string): DiffLineKind => {
  if (line.startsWith('+++') || line.startsWith('---')) return 'meta'
  if (line.startsWith('@@')) return 'hunk'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  return 'ctx'
}
</script>

<template>
  <div class="diff-box" :style="{ maxHeight: normalizeMaxHeight(maxHeight) }">
    <div
      v-for="(line, idx) in diffLines"
      :key="idx"
      class="diff-line"
      :class="'diff-' + getDiffLineKind(line)"
    >
      {{ line || ' ' }}
    </div>
  </div>
</template>

<style scoped>
.diff-box {
  overflow: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  padding: 8px 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  background: rgba(0, 0, 0, 0.02);
}

.diff-line {
  padding: 0 12px;
  white-space: pre;
}

.diff-add {
  color: #00a000;
  background: rgba(0, 160, 0, 0.16);
}

.diff-del {
  color: #d00020;
  background: rgba(208, 0, 32, 0.12);
}

.diff-hunk {
  color: #1d4ed8;
  background: rgba(29, 78, 216, 0.08);
}

.diff-meta {
  color: rgba(0, 0, 0, 0.6);
  background: rgba(0, 0, 0, 0.04);
}

.diff-ctx {
  color: rgba(0, 0, 0, 0.86);
}
</style>
