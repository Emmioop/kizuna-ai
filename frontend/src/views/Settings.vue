<template>
  <div style="display:flex;flex-direction:column;gap:16px;">
    <!-- 后端地址配置卡片：GitHub Pages / 公网静态托管使用 -->
    <section class="card" v-if="showBackendSetting">
      <h3>🌐 贾维斯后端地址</h3>
      <p class="sub">
        当前前端由 <b>GitHub Pages 静态托管</b>，您需要把后端跑在自己的电脑 / 服务器上，再把公网地址填在这里，我才能连上您的大脑。
        <a href="https://github.com/Emmioop/kizuna-ai/blob/main/docs/%E6%89%8B%E6%9C%BA%E8%AE%BF%E9%97%AE%E4%B8%8E%E6%89%93%E5%8C%85App%E6%8C%87%E5%8D%97.md" target="_blank" style="color:var(--accent)">看这里拿公网地址 👉</a>
      </p>

      <el-form :model="bCfg" label-width="100px" style="margin-top:10px;">
        <el-form-item label="后端地址">
          <el-input
            v-model="bCfg.url"
            placeholder="例如：https://xxx-xxx.trycloudflare.com   （Cloudflare Tunnel 给您的 HTTPS 公网地址，末尾不要带 /api）"
          />
          <div class="sub2">
            不知道填什么？先在电脑上跑 <code>cloudflared tunnel --url http://localhost:8000</code>，把它给的 trycloudflare.com 域名粘过来。
          </div>
        </el-form-item>
      </el-form>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
        <div class="current">
          <el-tag v-if="bStatus==='ok'" type="success">✓ 已连接到后端</el-tag>
          <el-tag v-else-if="bStatus==='fail'" type="danger">✗ 连不上后端，请检查地址</el-tag>
          <el-tag v-else type="warning">尚未连接</el-tag>
          <span v-if="bMsg" class="bMsg">{{ bMsg }}</span>
        </div>
        <div>
          <el-button @click="bStatus='idle';bMsg='';setBackendBase('');bCfg.url='';load();">清空</el-button>
          <el-button @click="testBackend">测试连接</el-button>
          <el-button type="primary" @click="saveBackend">保存</el-button>
        </div>
      </div>
    </section>

    <section class="card">
      <h3>LLM 连接设置</h3>
      <p class="sub">贾维斯不训练模型，而是使用您自己的 Key 调用各大厂商的模型 API。您的对话、记忆、人格全部存在本地后端。</p>

      <el-form :model="cfg" label-width="100px" style="margin-top:14px;">
        <el-form-item label="供应商">
          <el-select v-model="cfg.provider" style="width:100%" @change="onProviderChange">
            <el-option v-for="(m, k) in providers" :key="k" :label="m.name + (m.default_model ? '（默认 ' + m.default_model + '）' : '')" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="cfg.api_key" type="password" show-password placeholder="从对应官网获取的 Key" />
          <div class="sub2">
            <a v-if="docUrl" :href="docUrl" target="_blank" style="color:var(--accent)">点我去 {{ providerName }} 获取 Key →</a>
          </div>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="cfg.base_url" :placeholder="providerMeta?.base || '自定义兼容接口的 URL'"/>
          <div class="sub2">留空则使用供应商默认。供应商是「自定义」时必须填写。</div>
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="cfg.model" :placeholder="providerMeta?.default_model || '自定义模型名'"/>
        </el-form-item>
        <el-form-item label="创造性">
          <el-slider v-model="cfg.temperature" :min="0" :max="2" :step="0.05" show-input :style="{width:'70%'}"/>
          <div class="sub2">越低越严谨，越高越有想象力。聊天推荐 0.75</div>
        </el-form-item>
        <el-form-item label="最大长度">
          <el-input-number v-model="cfg.max_tokens" :min="100" :max="16000" :step="100" />
          <span style="color:var(--text-dim);margin-left:10px;">单次回复的最大 token 数</span>
        </el-form-item>
      </el-form>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
        <div class="current">
          <span v-if="health?.llm_initialized">当前：{{ health.llm_provider }} · {{ health.llm_model }}</span>
          <el-tag v-else type="danger">尚未连接到任何模型</el-tag>
        </div>
        <div>
          <el-button @click="ping">测试连接</el-button>
          <el-button type="warning" @click="save">保存并启用</el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, defineExpose } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getBackendBase, setBackendBase } from '../main.js'

const cfg = reactive({
  provider: 'zhipu', api_key: '', base_url: '', model: '',
  temperature: 0.75, max_tokens: 1200,
})
const providers = ref({})
const health = ref(null)

// 后端地址（仅 Pages 托管时展示）
const showBackendSetting = computed(() => {
  const host = window.location.hostname
  return !(
    host === 'localhost' || host === '127.0.0.1' ||
    host.startsWith('192.168.') || host.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host)
  )
})
const bCfg = reactive({ url: getBackendBase() || '' })
const bStatus = ref('idle')   // idle/ok/fail
const bMsg = ref('')

const providerMeta = computed(() => providers.value[cfg.provider] || {})
const providerName = computed(() => providerMeta.value?.name || cfg.provider)
const docUrl = computed(() => ({
  zhipu: 'https://open.bigmodel.cn/',
  deepseek: 'https://platform.deepseek.com/',
  openai: 'https://platform.openai.com/api-keys',
  qwen: 'https://dashscope.console.aliyun.com/',
  moonshot: 'https://platform.moonshot.cn/',
  ollama: 'https://ollama.com/',
  custom: '',
})[cfg.provider])

async function load() {
  try {
    providers.value = (await axios.get('/api/providers')).data
  } catch(_) {}
  try {
    health.value = (await axios.get('/api/health')).data
  } catch(_) { health.value = null }
}

function onProviderChange() {
  const pm = providerMeta.value
  if (pm?.base) cfg.base_url = pm.base
  if (pm?.default_model) cfg.model = pm.default_model
}

async function save() {
  try {
    const r = await axios.post('/api/config/llm', cfg)
    ElMessage.success('已保存：' + r.data.provider + ' · ' + r.data.model)
    health.value = (await axios.get('/api/health')).data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

async function ping() {
  try {
    const r = await axios.post('/api/chat', { text: '请用一句话介绍你自己（不超过10个字）' }, { timeout: 15000 })
    ElMessage.success('连接成功！它回复：' + r.data.reply)
  } catch (e) {
    ElMessage.error('连接失败：' + (e.response?.data?.detail || e.message))
  }
}

async function testBackend() {
  const base = (bCfg.url || '').trim().replace(/\/+$/, '')
  if (!base) { ElMessage.warning('请先填写后端地址'); return }
  bStatus.value = 'idle'
  bMsg.value = '正在测试…'
  try {
    const r = await axios.get(base + '/api/health', { timeout: 8000 })
    if (r.data?.ok) {
      bStatus.value = 'ok'
      const prov = r.data.llm_initialized ? `${r.data.llm_provider} · ${r.data.llm_model}` : '尚未接模型'
      bMsg.value = '后端版本：' + (r.data.version || 'OK') + ' ｜ LLM 状态：' + prov
    } else {
      bStatus.value = 'fail'; bMsg.value = '后端返回异常：' + JSON.stringify(r.data).slice(0, 80)
    }
  } catch (e) {
    bStatus.value = 'fail'
    bMsg.value = '错误：' + (e.message || String(e)).slice(0, 80)
  }
}

async function saveBackend() {
  const base = (bCfg.url || '').trim().replace(/\/+$/, '')
  if (!base) { ElMessage.warning('地址为空：您可以点「清空」回到本地相对路径模式'); return }
  // 先保存，再测试
  setBackendBase(base)
  bCfg.url = getBackendBase() || base
  // 加载最新 LLM 状态（相当于验证路径 OK）
  try {
    await axios.get('/api/health', { timeout: 8000 })
    ElMessage.success('后端地址已保存 ✓')
  } catch (_) {
    ElMessage.warning('保存成功，但暂时连不上后端。请确认 cloudflared tunnel 正在跑，再点「测试连接」。')
  }
  await load()
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped lang="scss">
.card {
  background: var(--bg-panel); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px 24px;
  max-width: 820px; margin: 0 auto;
}
.card h3 { margin: 0 0 6px; color: var(--accent); font-size: 16px; letter-spacing: 0.04em; }
.sub { color: var(--text-soft); font-size: 13px; line-height: 1.7; }
.sub2 { color: var(--text-dim); font-size: 11px; margin-top: 4px; line-height: 1.6; }
.sub code {
  background: rgba(63,213,255,0.08);
  padding: 1px 6px; border-radius: 3px;
  color: var(--accent); font-size: 11.5px;
  border: 1px solid var(--border);
}
.current { color: var(--text-soft); font-size: 13px; display: flex; align-items: center; gap: 8px; }
.bMsg { color: var(--text-dim); font-size: 12.5px; margin-left: 4px; }
:deep(.el-input__wrapper) { background: var(--bg-panel-2); box-shadow: 0 0 0 1px var(--border) inset; color: var(--text); }
:deep(.el-input__inner) { color: var(--text); }
:deep(.el-textarea__inner) { background: var(--bg-panel-2); color: var(--text); border-color: var(--border); }
</style>
