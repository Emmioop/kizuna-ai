<template>
  <div class="chat-wrap">
    <div class="chat-list" ref="listEl">
      <div v-if="!msgs.length" class="empty">
        <div class="empty-hello">
          <div class="big-core">
            <div class="big-core-inner"></div>
          </div>
          <h1>{{ persona?.name || '贾维斯' }} 已就绪，先生。</h1>
          <p>随时为您服务。需要什么请直接说，或输入 <code>/help</code> 查看快捷命令。</p>
          <p v-if="!healthOk" class="empty-warn">
            ⚠ 请先在「LLM 接入」页填写您的 API Key。
          </p>

          <div class="quick-chips">
            <div class="chip" @click="sendText('/sys')">💻 系统诊断</div>
            <div class="chip" @click="sendText('/weather 北京')">🌤 北京天气</div>
            <div class="chip" @click="sendText('/time')">🕐 当前时间</div>
            <div class="chip" @click="sendText('/timer 5 测试提醒')">⏰ 5 分钟后提醒我</div>
            <div class="chip" @click="sendText('计算根号 144 等于多少')">🧮 计算示例</div>
          </div>
        </div>
      </div>

      <div v-for="m in msgs" :key="m.id" :class="['msg', m.role]">
        <div class="avatar">
          <span v-if="m.role === 'assistant'" class="av-jarvis">J</span>
          <span v-else>🧑</span>
        </div>
        <div class="bubble-wrap">
          <!-- 工具调用结果卡片（附在 AI 消息上方） -->
          <div v-if="m.role === 'assistant' && m._tool_display" class="tool-card" v-html="m._tool_rendered"></div>
          <div class="bubble" :class="{ 'has-tool': m._tool_display }">
            <div class="bubble-text" v-html="m._rendered || m.content"></div>
            <div class="bubble-meta">
              <span v-if="m.role === 'assistant' && m._tool_name" class="tool-tag" :class="m._tool_success ? 'ok' : 'err'">
                🔧 {{ m._tool_name }} {{ m._tool_success ? '✓' : '✗' }}
              </span>
              <span v-if="m.role === 'assistant' && m.memory_synced" title="重要信息已归档">🧠 已记录</span>
              <span v-if="m._reminders > 0" class="rem-tag">⏰ +{{ m._reminders }} 条提醒</span>
              <span class="time">{{ fmt(m.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="typing" class="msg assistant">
        <div class="avatar"><span class="av-jarvis">J</span></div>
        <div class="bubble bubble-typing">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          <span class="typing-text">正在处理…</span>
        </div>
      </div>
    </div>

    <div class="input-row">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="请下达指令，先生。快捷命令以 / 开头，例如 /sys /weather 北京 /timer 30 开会"
        @keydown="onKey"
        :disabled="typing"
      />
      <el-button type="primary" class="send-btn" @click="send" :loading="typing" :disabled="!input.trim()">
        发送 <el-icon><Promotion /></el-icon>
      </el-button>
    </div>

    <div v-if="lastDelta" class="delta-toast">
      <span class="delta-main">🛡 信任 {{ fmtDelta(lastDelta.affection) }} · ⚡稳定 {{ fmtDelta(lastDelta.mood) }}</span>
      <span v-if="lastDelta.memories_used" class="d-s">· 档案 {{ lastDelta.memories_used }}</span>
      <span v-if="lastDelta.new_memories_saved" class="d-s">· 新增 {{ lastDelta.new_memories_saved }}</span>
      <span v-if="lastDelta.tool_used" class="d-s" :class="lastDelta.tool_success ? 'ok' : 'err'">
        · 🔧 {{ lastDelta.tool_used }}
      </span>
      <span v-if="lastDelta.reminders_added" class="d-s rem">· ⏰ 登记 {{ lastDelta.reminders_added }} 条提醒</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed, watch, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({ persona: Object })
const emit = defineEmits(['persona-updated'])

const msgs = ref([])
const input = ref('')
const typing = ref(false)
const listEl = ref(null)
const lastDelta = ref(null)
const healthOk = ref(true)

function renderMarkdown(s) {
  try {
    if (!s) return ''
    return marked.parse(String(s))
  } catch (_) {
    return String(s)
  }
}

function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  if (d.toDateString() === today.toDateString()) {
    return d.toTimeString().slice(0, 5)
  }
  return (d.getMonth()+1) + '/' + d.getDate() + ' ' + d.toTimeString().slice(0,5)
}
function fmtDelta(v) {
  if (v === 0 || v === '0.00' || (!v && v !== 0)) return '±0'
  const n = Number(v).toFixed(1)
  return (Number(n) >= 0 ? '+' : '') + n
}

async function loadHistory() {
  try {
    const r = await axios.get('/api/chat/history', { params: { limit: 150 } })
    msgs.value = r.data.map(decorateMsg)
  } catch(e) {}
  await scrollBottom()
}

function decorateMsg(m) {
  m._rendered = renderMarkdown(m.content)
  return m
}

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function sendText(txt) {
  input.value = txt
  send()
}

async function send() {
  const txt = input.value.trim()
  if (!txt) return
  input.value = ''
  const tmpUser = decorateMsg({
    id: Date.now(), role: 'user', content: txt,
    created_at: new Date().toISOString()
  })
  msgs.value.push(tmpUser)
  typing.value = true
  lastDelta.value = null
  await scrollBottom()

  try {
    const r = await axios.post('/api/chat', { text: txt })
    const d = r.data
    const aiMsg = decorateMsg({
      id: Date.now()+1, role: 'assistant', content: d.reply,
      created_at: new Date().toISOString(),
      memory_synced: !!d.new_memories_saved,
      _tool_name: d.tool_used,
      _tool_success: !!d.tool_success,
      _tool_display: d.tool_display || '',
      _tool_rendered: renderMarkdown(d.tool_display || ''),
      _reminders: d.reminders_added || 0,
    })
    msgs.value.push(aiMsg)
    lastDelta.value = d
    setTimeout(() => lastDelta.value = null, 6000)
    emit('persona-updated')
  } catch (e) {
    ElMessage.error('指令失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    typing.value = false
    await scrollBottom()
  }
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

let pollTimer = null

onMounted(async () => {
  try {
    const h = (await axios.get('/api/health')).data
    healthOk.value = !!h.llm_initialized
  } catch(_) { healthOk.value = false }
  await loadHistory()

  // 每 10s 轮询一次看看有没有新消息（倒计时提醒会插 assistant 消息进来）
  pollTimer = setInterval(async () => {
    try {
      const r = await axios.get('/api/chat/history', { params: { limit: 150 } })
      const arr = r.data
      if (arr.length !== msgs.value.length ||
          (arr.length && msgs.value.length &&
           arr[arr.length-1].id !== msgs.value[msgs.value.length-1].id)) {
        msgs.value = arr.map(decorateMsg)
        await scrollBottom()
      }
    } catch(_) {}
  }, 10000)
})

onBeforeUnmount(() => pollTimer && clearInterval(pollTimer))
</script>

<style scoped lang="scss">
.chat-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 10px;
}
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scroll-behavior: smooth;
}
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 30px 0;
}
.empty-hello {
  text-align: center;
  color: var(--text-soft);
  max-width: 620px;
}
.big-core {
  width: 120px; height: 120px; border-radius: 50%;
  margin: 0 auto 24px;
  position: relative;
  background: radial-gradient(circle at 50% 50%, rgba(63,213,255,0.3), transparent 70%);
  display: flex; align-items: center; justify-content: center;
}
.big-core-inner {
  width: 70px; height: 70px; border-radius: 50%;
  background: radial-gradient(circle, #fff 0%, var(--accent) 28%, var(--accent-2) 60%, transparent 72%);
  box-shadow: 0 0 20px var(--accent), 0 0 50px var(--accent-2);
  animation: bigpulse 2.4s ease-in-out infinite;
}
@keyframes bigpulse {
  0%,100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.08); opacity: 1; }
}
.empty-hello h1 {
  color: var(--accent);
  margin-bottom: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.empty-hello code {
  background: rgba(63,213,255,0.08);
  border: 1px solid var(--border);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: Menlo, Consolas, monospace;
  font-size: 12.5px;
}
.empty-warn { color: var(--accent-warn); margin-top: 10px; }

.quick-chips {
  margin-top: 22px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}
.chip {
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: rgba(63,213,255,0.05);
  color: var(--text-soft);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.chip:hover {
  background: rgba(63,213,255,0.12);
  color: var(--accent);
  border-color: var(--accent);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(63,213,255,0.15);
}

.msg {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.msg.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-panel-2);
  flex-shrink: 0;
  font-size: 18px;
  border: 1px solid var(--border);
}
.av-jarvis {
  font-family: Georgia, serif;
  font-weight: 700;
  color: #fff;
  background: radial-gradient(circle, var(--accent-2), var(--accent));
  width: 30px; height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center; justify-content: center;
  font-size: 15px;
  box-shadow: 0 0 10px rgba(63,213,255,0.6);
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 75%;
}
.bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;
  border: 1px solid var(--border);
  :deep(p) { margin: 2px 0; }
  :deep(pre) {
    background: rgba(0,0,0,0.5);
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    border: 1px solid var(--border);
  }
  :deep(code) {
    background: rgba(63,213,255,0.08);
    padding: 1px 5px;
    border-radius: 3px;
    font-family: Menlo, Consolas, monospace;
    font-size: 12.5px;
    color: var(--accent);
  }
  :deep(pre code) { background: transparent; padding: 0; }
  :deep(ul) { padding-left: 20px; }
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 8px 0 4px; color: var(--accent); }
  :deep(blockquote) {
    border-left: 3px solid var(--accent);
    padding-left: 10px;
    margin: 6px 0;
    color: var(--text-soft);
  }
  :deep(table) {
    border-collapse: collapse;
    margin: 6px 0;
    width: 100%;
    th, td { border: 1px solid var(--border); padding: 4px 8px; font-size: 13px; }
    th { background: rgba(63,213,255,0.06); color: var(--accent); }
  }
}
.msg.assistant .bubble {
  background: linear-gradient(180deg, rgba(10,26,48,0.8), #081828);
  border-color: rgba(63,213,255,0.25);
  border-top-left-radius: 3px;
  color: var(--text);
  box-shadow: inset 0 0 30px rgba(63,213,255,0.03);
}
.msg.assistant .bubble.has-tool {
  border-top-left-radius: 10px;
}
.msg.user .bubble {
  background: linear-gradient(135deg, #0e2a4d, #0b2040);
  color: #e0f2ff;
  border-color: rgba(30,144,255,0.3);
  border-top-right-radius: 3px;
}

/* 工具结果卡片（AI 用了工具就显示在对话上方） */
.tool-card {
  border-radius: 8px;
  padding: 10px 14px;
  background:
    linear-gradient(135deg, rgba(0,255,170,0.04), rgba(63,213,255,0.04));
  border: 1px solid rgba(0,255,170,0.2);
  font-size: 13px;
  color: var(--text-soft);
  line-height: 1.7;
  :deep(p) { margin: 3px 0; }
  :deep(code) {
    background: rgba(63,213,255,0.08);
    padding: 1px 5px;
    border-radius: 3px;
    color: var(--accent);
    font-size: 12px;
  }
  :deep(pre) {
    background: rgba(0,0,0,0.55);
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    border: 1px solid var(--border);
    margin: 6px 0;
  }
}

.bubble-meta {
  font-size: 10.5px;
  color: var(--text-dim);
  margin-top: 5px;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}
.msg.user .bubble-meta { color: rgba(214,236,255,0.45); }
.tool-tag {
  padding: 1px 8px;
  border-radius: 10px;
  font-family: Menlo, Consolas, monospace;
  font-size: 10.5px;
  border: 1px solid;
}
.tool-tag.ok {
  color: var(--accent-3);
  border-color: rgba(0,255,170,0.35);
  background: rgba(0,255,170,0.05);
}
.tool-tag.err {
  color: var(--accent-danger);
  border-color: rgba(255,71,87,0.35);
  background: rgba(255,71,87,0.05);
}
.rem-tag {
  padding: 1px 7px;
  border-radius: 10px;
  color: var(--accent-warn);
  font-size: 10.5px;
  background: rgba(255,202,58,0.08);
  border: 1px solid rgba(255,202,58,0.3);
}

.bubble-typing {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 18px;
}
.bubble-typing .dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 5px var(--accent);
  animation: blink 1.3s infinite;
}
.bubble-typing .dot:nth-child(2) { animation-delay: 0.2s; }
.bubble-typing .dot:nth-child(3) { animation-delay: 0.4s; }
.bubble-typing .typing-text {
  margin-left: 6px;
  color: var(--text-dim);
  font-size: 12px;
}
@keyframes blink { 0%,80%,100%{opacity:0.25;} 40%{opacity:1;} }

.input-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  padding: 8px 0 0;
  :deep(.el-textarea__inner) {
    background: var(--bg-panel);
    color: var(--text);
    border-color: var(--border);
    font-family: inherit;
    font-size: 14px;
  }
  :deep(.el-textarea__inner:focus) {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(63,213,255,0.15);
  }
}
.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 20px;
  background: linear-gradient(135deg, var(--accent-2), var(--accent));
  border: none;
  color: #001018;
  font-weight: 600;
  box-shadow: 0 6px 22px rgba(63,213,255,0.25);
}
.send-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.delta-toast {
  position: fixed;
  bottom: 90px; right: 30px;
  background: rgba(2,6,12,0.92);
  border: 1px solid var(--accent);
  padding: 10px 16px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--accent);
  backdrop-filter: blur(6px);
  box-shadow: 0 6px 24px rgba(63,213,255,0.25);
  animation: pop 0.25s ease-out, fadeout 0.6s ease-in 5.4s both;
  pointer-events: none;
  z-index: 100;
  .delta-main { font-weight: 600; }
  .d-s { color: var(--text-soft); margin-left: 6px; }
  .d-s.ok { color: var(--accent-3); }
  .d-s.err { color: var(--accent-danger); }
  .d-s.rem { color: var(--accent-warn); }
}
@keyframes pop { from { transform: translateY(10px); opacity: 0; } }
@keyframes fadeout { to { opacity: 0; transform: translateY(-8px); } }

@media (max-width: 680px) {
  .bubble-wrap { max-width: calc(100% - 56px); }
  .delta-toast { right: 12px; left: 12px; bottom: 88px; }
}
</style>
