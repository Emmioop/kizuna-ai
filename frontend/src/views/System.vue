<template>
  <div class="sys-wrap">
    <!-- 顶部：总览指标卡 -->
    <div class="overview">
      <div class="stat jarvis-card">
        <div class="stat-label">累计对话指令</div>
        <div class="stat-num">{{ counts?.chats ?? 0 }}</div>
        <div class="stat-sub">已记录 {{ counts?.messages ?? 0 }} 条消息</div>
      </div>
      <div class="stat jarvis-card">
        <div class="stat-label">长期记忆档案</div>
        <div class="stat-num accent2">{{ counts?.memories ?? 0 }}</div>
        <div class="stat-sub">用户画像 · 重要事件 · 纪念日</div>
      </div>
      <div class="stat jarvis-card">
        <div class="stat-label">待触发提醒</div>
        <div class="stat-num accent3">{{ counts?.pending_reminders ?? 0 }}</div>
        <div class="stat-sub">将按设定时间自动推送</div>
      </div>
      <div class="stat jarvis-card">
        <div class="stat-label">工具调用次数</div>
        <div class="stat-num warn">{{ counts?.tool_runs ?? 0 }}</div>
        <div class="stat-sub">所有工具执行均留下审计痕迹</div>
      </div>
    </div>

    <div class="grid-2">
      <!-- 左：人格 / 管家状态 -->
      <div class="jarvis-card">
        <div class="card-title">
          <span class="dot live"></span> 管家核心状态
        </div>
        <div class="persona-head">
          <div class="persona-arc"></div>
          <div>
            <h2>{{ persona?.name || '贾维斯' }}</h2>
            <p class="nick">称呼您为 · {{ persona?.nickname || '先生' }}</p>
          </div>
        </div>
        <div class="bar-row">
          <div class="bar-label">主人信任度 <b>{{ persona?.trust?.toFixed(0) || 0 }}%</b></div>
          <el-progress :percentage="persona?.trust || 0" :show-text="false" :stroke-width="10" :color="trustColor(persona?.trust)"/>
        </div>
        <div class="bar-row">
          <div class="bar-label">系统稳定度 <b>{{ persona?.stability?.toFixed(0) || 0 }}%</b></div>
          <el-progress :percentage="persona?.stability || 0" :show-text="false" :stroke-width="10" :color="stabColor(persona?.stability)"/>
        </div>
        <div class="mood-reason">状态说明：{{ persona?.mood_reason || '一切正常' }}</div>
        <div class="last-chat">上次指令：{{ persona?.last_chat_at ? fmtTime(persona.last_chat_at) : '从未' }}</div>
      </div>

      <!-- 右：本机系统信息 -->
      <div class="jarvis-card">
        <div class="card-title">
          <span class="dot ok"></span> 本机运行诊断
        </div>
        <div class="sys-grid">
          <div class="sys-item">
            <div class="sys-k">操作系统</div>
            <div class="sys-v">{{ sys?.platform || 'N/A' }}</div>
          </div>
          <div class="sys-item">
            <div class="sys-k">主机名</div>
            <div class="sys-v mono">{{ sys?.hostname || 'N/A' }}</div>
          </div>
          <div class="sys-item">
            <div class="sys-k">Python 解释器</div>
            <div class="sys-v mono">{{ sys?.python || 'N/A' }}</div>
          </div>
          <div class="sys-item">
            <div class="sys-k">进程 PID</div>
            <div class="sys-v mono">{{ sys?.pid || 'N/A' }}</div>
          </div>
          <div class="sys-item" v-if="sys?.loadavg">
            <div class="sys-k">系统负载 1/5/15m</div>
            <div class="sys-v mono">{{ sys.loadavg.map(v => v.toFixed(2)).join(' · ') }}</div>
          </div>
        </div>

        <div class="bar-row">
          <div class="bar-label">
            磁盘 / <b>{{ sys?.disk_used_gb || 0 }} GB</b> / {{ sys?.disk_total_gb || 0 }} GB
          </div>
          <el-progress :percentage="sys?.disk_usage_pct || 0" :show-text="false" :stroke-width="8" color="#1e90ff"/>
          <span class="pct">{{ sys?.disk_usage_pct?.toFixed(1) }}%</span>
        </div>

        <div class="bar-row">
          <div class="bar-label">
            物理内存 <b>{{ sys?.mem_used_mb || 0 }} MB</b> / {{ sys?.mem_total_mb || 0 }} MB
          </div>
          <el-progress :percentage="sys?.mem_usage_pct || 0" :show-text="false" :stroke-width="8" color="#3fd5ff"/>
          <span class="pct">{{ sys?.mem_usage_pct?.toFixed(1) }}%</span>
        </div>

        <el-button size="small" class="refresh-btn" @click="load">
          <el-icon><Refresh /></el-icon> 刷新诊断
        </el-button>
      </div>
    </div>

    <div class="grid-2">
      <!-- 待办提醒列表 -->
      <div class="jarvis-card">
        <div class="card-title with-actions">
          <span><span class="dot warn"></span> 待触发提醒 · PENDING REMINDERS</span>
          <el-button size="small" @click="showAddRem = true"><el-icon><Plus /></el-icon> 新增</el-button>
        </div>
        <el-table :data="reminders" size="small" class="hud-table" empty-text="暂无待触发提醒">
          <el-table-column label="ID" width="60" prop="id"/>
          <el-table-column label="内容" min-width="180">
            <template #default="{ row }">{{ row.note }}</template>
          </el-table-column>
          <el-table-column label="触发时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.trigger_time) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <span class="tag pending">待触发</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button size="small" @click="dismiss(row)">忽略</el-button>
              <el-button size="small" type="danger" @click="delRem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 最近工具调用日志 -->
      <div class="jarvis-card">
        <div class="card-title">
          <span class="dot live"></span> 工具调用日志 · TOOL AUDIT LOG
        </div>
        <el-table :data="toolLogs" size="small" class="hud-table" max-height="320" empty-text="暂无工具调用">
          <el-table-column label="时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="工具" width="110">
            <template #default="{ row }">
              <span class="tool-name">{{ row.tool }}</span>
            </template>
          </el-table-column>
          <el-table-column label="触发">
            <template #default="{ row }">
              <span class="ellipsis">{{ row.user_text }}</span>
            </template>
          </el-table-column>
          <el-table-column label="结果" width="70">
            <template #default="{ row }">
              <span class="tag" :class="row.success ? 'ok' : 'err'">{{ row.success ? '成功' : '失败' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">{{ row.duration_ms }}ms</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 新增提醒弹窗 -->
    <el-dialog v-model="showAddRem" title="登记提醒 · REMINDER SETUP" width="500px" class="hud-dialog">
      <el-form label-width="80px">
        <el-form-item label="提醒内容">
          <el-input v-model="newRem.note" placeholder="例如：30 分钟后开会" />
        </el-form-item>
        <el-form-item label="多少分钟后">
          <el-input-number v-model="newRem.minutes" :min="0.1" :max="525600" :step="5"/>
          <span style="margin-left:10px;color:var(--text-dim);font-size:12px;">
            将在 {{ afterTime() }} 触发
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRem = false">取消</el-button>
        <el-button type="primary" @click="addRem">确认登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({ persona: Object })
defineEmits(['persona-updated'])

const counts = ref(null)
const persona = ref(null)
const sys = ref(null)
const reminders = ref([])
const toolLogs = ref([])

const showAddRem = ref(false)
const newRem = reactive({ note: '', minutes: 30 })

function trustColor(v) {
  if (v >= 80) return '#00ffaa'
  if (v >= 50) return '#3fd5ff'
  if (v >= 30) return '#ffca3a'
  return '#ff4757'
}
function stabColor(v) {
  if (v >= 80) return '#00ffaa'
  if (v >= 55) return '#3fd5ff'
  if (v >= 30) return '#ffca3a'
  return '#ff4757'
}
function fmtTime(iso) {
  if (!iso) return 'N/A'
  const d = new Date(iso)
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
function afterTime() {
  const d = new Date(Date.now() + (newRem.minutes || 0) * 60000)
  const p = n => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}`
}

async function load() {
  try {
    const r = await axios.get('/api/dashboard')
    counts.value = r.data.counts
    persona.value = r.data.persona
    sys.value = r.data.system
  } catch (e) {
    ElMessage.error('加载总览失败')
  }
  try { reminders.value = (await axios.get('/api/reminders', { params: { only_pending: true } })).data } catch(_) {}
  try { toolLogs.value = (await axios.get('/api/tools/logs', { params: { limit: 50 } })).data } catch(_) {}
}

async function dismiss(row) {
  await axios.post(`/api/reminders/${row.id}/dismiss`)
  ElMessage.success('已标记为已忽略')
  load()
}
async function delRem(row) {
  await axios.delete(`/api/reminders/${row.id}`)
  ElMessage.success('已删除')
  load()
}
async function addRem() {
  if (!newRem.note.trim()) { ElMessage.warning('请写提醒内容'); return }
  await axios.post('/api/reminders', { note: newRem.note, minutes: newRem.minutes })
  ElMessage.success('已登记提醒')
  newRem.note = ''; newRem.minutes = 30
  showAddRem.value = false
  load()
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped lang="scss">
.sys-wrap { display: flex; flex-direction: column; gap: 16px; }

.overview {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
  @media (max-width: 960px) { grid-template-columns: repeat(2, 1fr); }
}
.stat {
  padding: 18px 20px;
}
.stat-label { font-size: 12px; color: var(--text-dim); letter-spacing: 0.12em; }
.stat-num {
  font-size: 32px; font-weight: 700; margin-top: 8px;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  color: var(--accent);
  text-shadow: 0 0 12px rgba(63,213,255,0.4);
}
.stat-num.accent2 { color: var(--accent-2); text-shadow: 0 0 12px rgba(30,144,255,0.45); }
.stat-num.accent3 { color: var(--accent-3); text-shadow: 0 0 12px rgba(0,255,170,0.45); }
.stat-num.warn { color: var(--accent-warn); text-shadow: 0 0 12px rgba(255,202,58,0.45); }
.stat-sub { font-size: 11.5px; color: var(--text-dim); margin-top: 4px; }

.grid-2 {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  @media (max-width: 960px) { grid-template-columns: 1fr; }
}

.persona-head {
  display: flex; align-items: center; gap: 14px; margin-bottom: 14px;
}
.persona-arc {
  width: 56px; height: 56px; border-radius: 50%;
  background: radial-gradient(circle, #fff 0%, var(--accent) 28%, var(--accent-2) 65%, transparent 72%);
  box-shadow: 0 0 18px var(--accent);
  animation: pulse 2.4s ease-in-out infinite;
}
.persona-head h2 {
  font-size: 20px; margin: 0; color: var(--accent); letter-spacing: 0.1em;
}
.nick { margin: 3px 0 0; font-size: 12.5px; color: var(--text-dim); }

.bar-row {
  display: grid;
  grid-template-columns: 220px 1fr 60px;
  gap: 10px; align-items: center;
  margin-bottom: 10px;
  @media (max-width: 600px) { grid-template-columns: 1fr; }
}
.bar-label { font-size: 12.5px; color: var(--text-soft); }
.bar-label b { color: var(--accent); font-weight: 600; }
.pct { text-align: right; font-size: 12px; color: var(--accent); font-family: Menlo, Consolas, monospace; }
.mood-reason { margin-top: 8px; font-size: 12.5px; color: var(--text-soft); line-height: 1.7; }
.last-chat { margin-top: 4px; font-size: 11.5px; color: var(--text-dim); }

.sys-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; margin-bottom: 14px;
}
.sys-item {
  display: flex; justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dashed rgba(63,213,255,0.15);
  font-size: 12.5px;
}
.sys-k { color: var(--text-dim); }
.sys-v { color: var(--text); }
.mono { font-family: Menlo, Consolas, monospace; }
.refresh-btn { margin-top: 12px; width: 100%; }

.card-title {
  font-size: 12.5px; color: var(--text-soft); letter-spacing: 0.14em;
  margin-bottom: 14px; display: flex; align-items: center; gap: 6px;
}
.card-title.with-actions {
  justify-content: space-between;
}
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.dot.live { background: var(--accent); box-shadow: 0 0 6px var(--accent); animation: blink 1.4s ease-in-out infinite; }
.dot.ok { background: var(--accent-3); }
.dot.warn { background: var(--accent-warn); box-shadow: 0 0 6px var(--accent-warn); animation: blink 1.6s infinite; }
.dot.err { background: var(--accent-danger); }
@keyframes blink { 50% { opacity: 0.35; } }
@keyframes pulse { 0%,100% { opacity: 0.9; transform: scale(1); } 50% { opacity: 1; transform: scale(1.06); } }

.hud-table {
  background: transparent;
  :deep(.el-table) {
    --el-table-bg-color: transparent;
    --el-table-tr-bg-color: transparent;
    --el-table-header-bg-color: rgba(63,213,255,0.05);
    --el-table-row-hover-bg-color: rgba(63,213,255,0.06);
    --el-table-border-color: var(--border);
    --el-table-header-text-color: var(--accent);
    --el-table-text-color: var(--text);
    font-size: 12.5px;
  }
  :deep(.el-table th) { letter-spacing: 0.08em; font-size: 11.5px; }
}

.tag {
  padding: 2px 8px; border-radius: 10px; font-size: 11px;
  border: 1px solid;
}
.tag.ok { color: var(--accent-3); border-color: rgba(0,255,170,0.35); background: rgba(0,255,170,0.05); }
.tag.err { color: var(--accent-danger); border-color: rgba(255,71,87,0.35); background: rgba(255,71,87,0.05); }
.tag.pending { color: var(--accent-warn); border-color: rgba(255,202,58,0.35); background: rgba(255,202,58,0.05); }
.tool-name {
  font-family: Menlo, Consolas, monospace;
  background: rgba(63,213,255,0.08);
  padding: 2px 8px; border-radius: 4px;
  color: var(--accent); font-size: 11.5px;
  border: 1px solid rgba(63,213,255,0.2);
}
.ellipsis {
  display: inline-block; max-width: 220px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  vertical-align: middle;
}

.hud-dialog {
  :deep(.el-dialog) {
    background: var(--bg-panel);
    border: 1px solid var(--accent);
    box-shadow: 0 0 30px rgba(63,213,255,0.2);
  }
  :deep(.el-dialog__title) {
    color: var(--accent); letter-spacing: 0.14em; font-size: 14px;
  }
}
</style>
