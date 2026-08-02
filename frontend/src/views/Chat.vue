<template>
  <div class="chat-wrap">
    <div class="chat-list" ref="listEl">
      <div v-if="!msgs.length" class="empty">
        <div class="empty-hello">
          <h1>{{ persona?.name || '小绊' }}在等你 ✨</h1>
          <p>说点什么吧～她会记得你说过的每一件重要的事。</p>
          <p v-if="!healthOk" class="empty-warn">
            ⚠ 请先在「LLM 设置」里填写你的 API Key。
          </p>
        </div>
      </div>

      <div v-for="m in msgs" :key="m.id" :class="['msg', m.role]">
        <div class="avatar">
          <span v-if="m.role === 'assistant'">{{ personaEmoji }}</span>
          <span v-else>🧑</span>
        </div>
        <div class="bubble">
          <div class="bubble-text">{{ m.content }}</div>
          <div class="bubble-meta">
            <span v-if="m.role === 'assistant' && m.memory_synced" title="这次对话被记住了">🧠 已记住</span>
            <span class="time">{{ fmt(m.created_at) }}</span>
          </div>
        </div>
      </div>

      <div v-if="typing" class="msg assistant">
        <div class="avatar">{{ personaEmoji }}</div>
        <div class="bubble bubble-typing">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </div>

    <div class="input-row">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="和她说点什么…（Enter 发送 / Shift+Enter 换行）"
        @keydown="onKey"
        :disabled="typing"
      />
      <el-button type="warning" @click="send" :loading="typing" :disabled="!input.trim()">
        发送
      </el-button>
    </div>

    <div v-if="lastDelta" class="delta-toast">
      💖 好感 {{ fmtDelta(lastDelta.affection) }} · 😊 心情 {{ fmtDelta(lastDelta.mood) }}
      <span v-if="lastDelta.memories_used" class="d-s">· 调用 {{ lastDelta.memories_used }} 条记忆</span>
      <span v-if="lastDelta.new_memories_saved" class="d-s">· 新记住 {{ lastDelta.new_memories_saved }} 件事</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({ persona: Object })
const emit = defineEmits(['persona-updated'])

const msgs = ref([])
const input = ref('')
const typing = ref(false)
const listEl = ref(null)
const lastDelta = ref(null)
const healthOk = ref(true)

const personaEmoji = computed(() => {
  const p = props.persona
  if (!p) return '🌙'
  if ((p.gender || '').includes('男')) return '🌟'
  return '🌙'
})

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
    const r = await axios.get('/api/chat/history', { params: { limit: 100 } })
    msgs.value = r.data
  } catch(e) {}
  await scrollBottom()
}

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function send() {
  const txt = input.value.trim()
  if (!txt) return
  input.value = ''
  const tmpUser = { id: Date.now(), role: 'user', content: txt, created_at: new Date().toISOString() }
  msgs.value.push(tmpUser)
  typing.value = true
  lastDelta.value = null
  await scrollBottom()

  try {
    const r = await axios.post('/api/chat', { text: txt })
    const d = r.data
    msgs.value.push({
      id: Date.now()+1, role: 'assistant', content: d.reply,
      created_at: new Date().toISOString(), memory_synced: !!d.new_memories_saved,
    })
    lastDelta.value = d
    setTimeout(() => lastDelta.value = null, 5200)
    // 通知侧边栏刷新好感心情
    emit('persona-updated')
  } catch (e) {
    ElMessage.error('发送失败: ' + (e.response?.data?.detail || e.message))
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

onMounted(async () => {
  try {
    const h = (await axios.get('/api/health')).data
    healthOk.value = !!h.llm_initialized
  } catch(_) { healthOk.value = false }
  await loadHistory()
})
</script>

<style scoped lang="scss">
.chat-wrap { display: flex; flex-direction: column; height: 100%; gap: 10px; }
.chat-list {
  flex: 1; overflow-y: auto; padding: 16px 10px;
  display: flex; flex-direction: column; gap: 14px;
}
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.empty-hello { text-align: center; color: var(--text-soft); }
.empty-hello h1 { color: var(--accent); margin-bottom: 8px; }
.empty-warn { color: var(--accent-2); margin-top: 10px; }

.msg { display: flex; gap: 10px; align-items: flex-end; }
.msg.user { flex-direction: row-reverse; }
.avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-panel-2); flex-shrink: 0; font-size: 18px;
  border: 1px solid var(--border);
}
.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px; line-height: 1.65; white-space: pre-wrap; word-break: break-word;
}
.msg.assistant .bubble { background: var(--bubble-ai); border: 1px solid var(--border); border-top-left-radius: 2px; }
.msg.user .bubble {
  background: linear-gradient(135deg, #7a4a10, #5d3608);
  color: #fff6e0;
  border-top-right-radius: 2px;
}
.bubble-meta { font-size: 10px; color: var(--text-dim); margin-top: 4px; display: flex; gap: 8px; justify-content: flex-end; }
.msg.user .bubble-meta { color: rgba(255,255,255,0.5); }
.bubble-typing { display: flex; gap: 4px; padding: 14px 18px; }
.bubble-typing .dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--text-dim);
  animation: blink 1.3s infinite;
}
.bubble-typing .dot:nth-child(2) { animation-delay: 0.2s; }
.bubble-typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100%{opacity:0.3;} 40%{opacity:1;} }

.input-row {
  display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 8px 0 0;
  :deep(.el-textarea__inner) {
    background: var(--bg-panel); color: var(--text);
    border-color: var(--border);
  }
}

.delta-toast {
  position: fixed; bottom: 90px; right: 30px;
  background: rgba(30,30,40,0.9);
  border: 1px solid var(--accent);
  padding: 8px 14px;
  border-radius: 20px;
  font-size: 12px; color: var(--accent);
  animation: pop 0.3s ease-out, fadeout 0.6s ease-in 4.6s both;
  pointer-events: none;
  .d-s { color: var(--text-soft); margin-left: 4px; }
}
@keyframes pop { from{transform: translateY(10px); opacity: 0;} }
@keyframes fadeout { to { opacity: 0; transform: translateY(-8px); } }
</style>
