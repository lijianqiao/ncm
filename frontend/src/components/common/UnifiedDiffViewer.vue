<script setup lang="ts">
import { computed } from 'vue'

type DiffLineKind = 'meta' | 'hunk' | 'add' | 'del' | 'ctx'

interface ParsedDiffLine {
  content: string
  kind: DiffLineKind
  oldLineNum: number | null // 旧文件行号
  newLineNum: number | null // 新文件行号
}

const props = withDefaults(
  defineProps<{
    diff?: string | null
    maxHeight?: number | string
    showLineNumbers?: boolean
  }>(),
  {
    diff: '',
    maxHeight: 600,
    showLineNumbers: true,
  },
)

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

// 解析 hunk header: @@ -oldStart,oldCount +newStart,newCount @@
const parseHunkHeader = (line: string): { oldStart: number; newStart: number } | null => {
  const match = line.match(/^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/)
  if (match && match[1] && match[2]) {
    return {
      oldStart: parseInt(match[1], 10),
      newStart: parseInt(match[2], 10),
    }
  }
  return null
}

// 解析 diff 内容，计算每行的行号
const parsedLines = computed<ParsedDiffLine[]>(() => {
  const content = props.diff || ''
  if (!content) return []

  const lines = content.split('\n')
  const result: ParsedDiffLine[] = []

  let oldLine = 0
  let newLine = 0

  for (const line of lines) {
    const kind = getDiffLineKind(line)

    if (kind === 'hunk') {
      // 解析 hunk header 获取起始行号
      const hunk = parseHunkHeader(line)
      if (hunk) {
        oldLine = hunk.oldStart
        newLine = hunk.newStart
      }
      result.push({ content: line, kind, oldLineNum: null, newLineNum: null })
    } else if (kind === 'meta') {
      // 文件头信息不显示行号
      result.push({ content: line, kind, oldLineNum: null, newLineNum: null })
    } else if (kind === 'add') {
      // 新增行：只有新文件行号
      result.push({ content: line, kind, oldLineNum: null, newLineNum: newLine })
      newLine++
    } else if (kind === 'del') {
      // 删除行：只有旧文件行号
      result.push({ content: line, kind, oldLineNum: oldLine, newLineNum: null })
      oldLine++
    } else {
      // 上下文行：两边都有行号
      result.push({ content: line, kind, oldLineNum: oldLine, newLineNum: newLine })
      oldLine++
      newLine++
    }
  }

  return result
})

// 计算行号列宽度（根据最大行号位数）
const lineNumWidth = computed(() => {
  let maxNum = 1
  for (const line of parsedLines.value) {
    if (line.oldLineNum && line.oldLineNum > maxNum) maxNum = line.oldLineNum
    if (line.newLineNum && line.newLineNum > maxNum) maxNum = line.newLineNum
  }
  const digits = String(maxNum).length
  return Math.max(digits * 8 + 8, 32) // 每位约 8px，最小 32px
})
</script>

<template>
  <div class="diff-box" :style="{ maxHeight: normalizeMaxHeight(maxHeight) }">
    <div
      v-for="(line, idx) in parsedLines"
      :key="idx"
      class="diff-line"
      :class="'diff-' + line.kind"
    >
      <!-- 行号列 -->
      <template v-if="showLineNumbers">
        <span class="line-num line-num-old" :style="{ width: lineNumWidth + 'px' }">
          {{ line.oldLineNum ?? '' }}
        </span>
        <span class="line-num line-num-new" :style="{ width: lineNumWidth + 'px' }">
          {{ line.newLineNum ?? '' }}
        </span>
      </template>
      <!-- 内容 -->
      <span class="line-content">{{ line.content || ' ' }}</span>
    </div>
  </div>
</template>

<style scoped>
.diff-box {
  overflow: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  background: rgba(0, 0, 0, 0.02);
}

.diff-line {
  display: flex;
  white-space: pre;
}

.line-num {
  flex-shrink: 0;
  padding: 0 6px;
  text-align: right;
  color: rgba(0, 0, 0, 0.4);
  background: rgba(0, 0, 0, 0.04);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  user-select: none;
}

.line-num-old {
  border-right-color: rgba(0, 0, 0, 0.06);
}

.line-num-new {
  border-right-color: rgba(0, 0, 0, 0.1);
}

.line-content {
  flex: 1;
  padding: 0 12px;
  min-width: 0;
}

/* 行类型样式 */
.diff-add {
  background: rgba(0, 160, 0, 0.12);
}

.diff-add .line-content {
  color: #00a000;
}

.diff-add .line-num {
  background: rgba(0, 160, 0, 0.08);
  color: rgba(0, 128, 0, 0.6);
}

.diff-del {
  background: rgba(208, 0, 32, 0.08);
}

.diff-del .line-content {
  color: #d00020;
}

.diff-del .line-num {
  background: rgba(208, 0, 32, 0.06);
  color: rgba(208, 0, 32, 0.5);
}

.diff-hunk {
  background: rgba(29, 78, 216, 0.06);
}

.diff-hunk .line-content {
  color: #1d4ed8;
  padding: 4px 12px;
}

.diff-hunk .line-num {
  background: rgba(29, 78, 216, 0.04);
}

.diff-meta {
  background: rgba(0, 0, 0, 0.03);
}

.diff-meta .line-content {
  color: rgba(0, 0, 0, 0.6);
  padding: 2px 12px;
}

.diff-ctx .line-content {
  color: rgba(0, 0, 0, 0.86);
}
</style>
