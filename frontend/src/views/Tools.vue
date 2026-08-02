<template>
  <div class="tools-wrap">
    <!-- 顶部：快捷命令帮助 -->
    <div class="jarvis-card help-card">
      <div class="card-title"><span class="dot live"></span> 快捷命令清单 · QUICK COMMANDS</div>
      <div class="cmd-grid">
        <div v-for="c in quickCmds" :key="c.cmd" class="cmd-item">
          <code class="cmd-code">{{ c.cmd }}</code>
          <div class="cmd-desc">{{ c.desc }}</div>
        </div>
      </div>
    </div>

    <!-- 工具列表：每个工具一张卡片 -->
    <div class="tools-grid">
      <div v-for="t in tools" :key="t.name" class="tool-card jarvis-card" :class="{ disabled: !t.enabled }">
        <div class="tool-card-head">
          <div>
            <div class="tool-name">{{ t.name }}
              <span class="tool-cat" :class="t.category">{{ catLabel(t.category) }}</span>
              <el-tag v-if="t.dangerous" class="danger-tag" size="small" effect="dark" type="danger">需授权</el-tag>
            </div>
            <div class="tool-desc">{{ t.description }}</div>
          </div>
          <el-switch v-model="t.enabled" @change="onToggle(t)" active-text="开" inactive-text="关"/>
        </div>

        <div v-if="t.examples && t.examples.length" class="tool-examples">
          <div class="ex-label">适用场景示例：</div>
          <div class="ex-list">
            <span v-for="(e, i) in t.examples" :key="i" class="ex-chip">"{{ e }}"</span>
          </div>
        </div>

        <!-- 参数表单 + 手动执行 -->
        <details class="run-panel">
          <summary>▶ 手动执行 / 调参测试</summary>
          <div class="run-body">
            <div v-if="Object.keys(t.params_schema || {}).length === 0" class="no-param">本工具无需参数，直接执行。</div>
            <el-form v-else label-width="100px" size="small">
              <el-form-item
                v-for="(schema, pname) in t.params_schema"
                :key="pname"
                :label="pname + (schema.required ? ' *' : '')"
              >
                <el-input
                  v-if="schema.type === 'string'"
                  v-model="runParams[t.name][pname]"
                  :placeholder="schema.desc"
                />
                <el-input-number
                  v-else-if="schema.type === 'number'"
                  v-model="runParams[t.name][pname]"
                  :step="1"
                  :controls-position="right"
                  placeholder="数字"
                />
              </el-form-item>
            </el-form>
            <div class="run-actions">
              <el-button
                size="small"
                type="primary"
                :disabled="!t.enabled || running[t.name]"
                @click="run(t)"
              >
                <el-icon v-if="running[t.name]"><Loading /></el-icon>
                <el-icon v-else><VideoPlay /></el-icon>
                {{ running[t.name] ? '执行中…' : '执行工具' }}
              </el-button>
              <el-button size="small" @click="resetParams(t)">重置参数</el-button>
            </div>

            <div v-if="lastResult[t.name]" class="run-result" :class="lastResult[t.name].success ? 'ok' : 'err'">
              <div class="r-head">
                <span class="r-status">{{ lastResult[t.name].success ? '✓ 执行成功' : '✗ 执行失败' }}</span>
                <span class="r-time">耗时 {{ lastResult[t.name].duration_ms }}ms</span>
              </div>
              <div class="r-display" v-html="renderMd(lastResult[t.name].display || lastResult[t.name].output)"></div>
            </div>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
marked.setOptions({ breaks: true, gfm: true })

defineProps({ persona: Object })
defineEmits(['persona-updated'])

const tools = ref([])
const runParams = reactive({})
const running = reactive({})
const lastResult = reactive({})

const quickCmds = [
  { cmd: '/time', desc: '查询当前时间（含日期、星期、时区）' },
  { cmd: '/date', desc: '今天日期 + 未来 7 天概览' },
  { cmd: '/sys', desc: '系统诊断（CPU、内存、磁盘、负载）' },
  { cmd: '/weather 城市名', desc: '城市实时天气（默认北京）' },
  { cmd: '/calc 算式', desc: '计算器，例：/calc 2^10' },
  { cmd: '/timer N 内容', desc: 'N 分钟后提醒，例：/timer 30 开会' },
  { cmd: '/list_dir ~', desc: '列出家目录（或指定路径）' },
  { cmd: '/read_file 路径', desc: '读取安全目录下的文本文件' },
  { cmd: '/shell date', desc: '白名单命令：date / uptime / df -h 等' },
]

function catLabel(c) {
  return {
    general: '通用', system: '系统', info: '信息查询', reminder: '提醒',
  }[c] || c
}

function renderMd(s) {
  try { return marked.parse(String(s || '')) } catch (_) { return String(s || '') }
}

async function load() {
  try {
    tools.value = (await axios.get('/api/tools')).data
    // 初始化参数
    for (const t of tools.value) {
      if (!runParams[t.name]) runParams[t.name] = {}
      for (const pname in (t.params_schema || {})) {
        if (!(pname in runParams[t.name])) runParams[t.name][pname] = ''
      }
    }
  } catch (e) {
    ElMessage.error('加载工具清单失败')
  }
}

async function onToggle(t) {
  try {
    await axios.post('/api/tools/toggle', { name: t.name, enabled: t.enabled })
    ElMessage.success(`${t.name} 已${t.enabled ? '启用' : '禁用'}`)
  } catch (e) {
    t.enabled = !t.enabled  // 还原
    ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
  }
}

function resetParams(t) {
  if (!runParams[t.name]) runParams[t.name] = {}
  for (const pname in (t.params_schema || {})) runParams[t.name][pname] = ''
  lastResult[t.name] = null
}

async function run(t) {
  running[t.name] = true
  try {
    const r = await axios.post('/api/tools/run', {
      name: t.name,
      params: runParams[t.name] || {},
    })
    lastResult[t.name] = r.data
    ElMessage.success(`${t.name} 执行完成`)
  } catch (e) {
    lastResult[t.name] = { success: false, output: e.response?.data?.detail || e.message, duration_ms: 0 }
    ElMessage.error('执行失败：' + (e.response?.data?.detail || e.message))
  } finally {
    running[t.name] = false
  }
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped lang="scss">
.tools-wrap { display: flex; flex-direction: column; gap: 16px; }

.help-card { padding: 18px 22px; }
.cmd-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px 20px; margin-top: 4px;
}
.cmd-item {
  padding: 10px 12px;
  border: 1px solid rgba(63,213,255,0.18);
  border-radius: 4px;
  background: rgba(63,213,255,0.03);
  transition: all 0.18s ease;
  &:hover {
    border-color: var(--accent);
    background: rgba(63,213,255,0.08);
    transform: translateY(-1px);
  }
}
.cmd-code {
  display: inline-block;
  background: rgba(63,213,255,0.08);
  border: 1px solid var(--border);
  color: var(--accent);
  padding: 2px 8px;
  border-radius: 3px;
  font-family: Menlo, Consolas, monospace;
  font-size: 12.5px;
}
.cmd-desc { margin-top: 6px; font-size: 12px; color: var(--text-soft); }

.tools-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 14px;
}
.tool-card {
  padding: 16px 18px;
  display: flex; flex-direction: column;
  &.disabled { opacity: 0.55; }
}
.tool-card-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 10px;
}
.tool-name {
  font-family: Menlo, Consolas, monospace;
  font-size: 15px;
  color: var(--accent);
  font-weight: 600;
  display: flex; align-items: center; gap: 8px;
}
.tool-cat {
  font-family: inherit;
  font-size: 10.5px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid;
  letter-spacing: 0.06em;
  &.general { color: var(--accent-2); border-color: rgba(30,144,255,0.35); background: rgba(30,144,255,0.06); }
  &.system { color: var(--accent); border-color: rgba(63,213,255,0.35); background: rgba(63,213,255,0.06); }
  &.info { color: var(--accent-3); border-color: rgba(0,255,170,0.35); background: rgba(0,255,170,0.06); }
  &.reminder { color: var(--accent-warn); border-color: rgba(255,202,58,0.35); background: rgba(255,202,58,0.06); }
}
.danger-tag {
  background: rgba(255,71,87,0.15) !important;
  border-color: var(--accent-danger) !important;
  color: var(--accent-danger) !important;
}
.tool-desc {
  font-size: 12.5px;
  color: var(--text-soft);
  margin-top: 6px;
  line-height: 1.65;
}
.tool-examples {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(63,213,255,0.15);
}
.ex-label { font-size: 11px; color: var(--text-dim); letter-spacing: 0.08em; margin-bottom: 6px; }
.ex-list { display: flex; flex-wrap: wrap; gap: 6px; }
.ex-chip {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 11.5px;
  color: var(--text-soft);
  background: rgba(63,213,255,0.04);
  border: 1px solid rgba(63,213,255,0.12);
}

.run-panel {
  margin-top: 14px;
  border: 1px solid rgba(63,213,255,0.15);
  border-radius: 4px;
  padding: 10px 14px;
  background: rgba(0,0,0,0.2);
  summary {
    cursor: pointer;
    font-size: 12px;
    color: var(--accent);
    letter-spacing: 0.08em;
    padding: 4px 0;
    user-select: none;
  }
  summary:hover { color: var(--accent-3); }
}
.run-body { margin-top: 10px; }
.no-param {
  font-size: 12.5px; color: var(--text-dim);
  padding: 8px 0 12px;
}
.run-actions {
  display: flex; gap: 8px;
  margin-top: 4px;
  padding-bottom: 8px;
}
.run-result {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 4px;
  border: 1px solid;
  &.ok {
    border-color: rgba(0,255,170,0.3);
    background: rgba(0,255,170,0.04);
  }
  &.err {
    border-color: rgba(255,71,87,0.3);
    background: rgba(255,71,87,0.04);
  }
  :deep(p) { margin: 3px 0; }
  :deep(pre) {
    background: rgba(0,0,0,0.6);
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 6px 0;
    border: 1px solid var(--border);
    font-size: 12px;
  }
  :deep(code) {
    background: rgba(63,213,255,0.08);
    padding: 1px 5px;
    border-radius: 3px;
    color: var(--accent);
    font-size: 12px;
  }
  :deep(pre code) { background: transparent; }
}
.r-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
  font-size: 11.5px;
}
.r-status.ok, .ok .r-status { color: var(--accent-3); font-weight: 600; }
.err .r-status { color: var(--accent-danger); font-weight: 600; }
.r-time {
  font-family: Menlo, Consolas, monospace;
  color: var(--text-dim);
}
.r-display {
  font-size: 13px;
  color: var(--text);
  line-height: 1.7;
}

.card-title {
  font-size: 12.5px; color: var(--text-soft); letter-spacing: 0.14em;
  margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
}
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.dot.live { background: var(--accent); box-shadow: 0 0 6px var(--accent); animation: blink 1.4s ease-in-out infinite; }
@keyframes blink { 50% { opacity: 0.35; } }
</style>
