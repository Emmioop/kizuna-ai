<template>
  <div>
    <section class="card">
      <h3>LLM 连接设置</h3>
      <p class="sub">羁绊 AI 不训练模型，而是使用你自己的 Key 调用各大厂商的模型 API。你的对话、记忆、人格全部存在本地。</p>

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
import { ref, reactive, onMounted, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const cfg = reactive({
  provider: 'zhipu', api_key: '', base_url: '', model: '',
  temperature: 0.75, max_tokens: 1200,
})
const providers = ref({})
const health = ref(null)

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
  } catch(_) {}
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
  // 用一段测试 prompt 试一下
  try {
    const r = await axios.post('/api/chat', { text: '请用一句话介绍你自己（不超过10个字）' }, { timeout: 15000 })
    ElMessage.success('连接成功！她回复：' + r.data.reply)
  } catch (e) {
    ElMessage.error('连接失败：' + (e.response?.data?.detail || e.message))
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.card {
  background: var(--bg-panel); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px 24px;
  max-width: 820px; margin: 0 auto;
}
.card h3 { margin: 0 0 6px; color: var(--accent); font-size: 16px; }
.sub { color: var(--text-soft); font-size: 13px; }
.sub2 { color: var(--text-dim); font-size: 11px; margin-top: 4px; }
.current { color: var(--text-soft); font-size: 13px; }
:deep(.el-input__wrapper) { background: var(--bg-panel-2); box-shadow: 0 0 0 1px var(--border) inset; color: var(--text); }
:deep(.el-input__inner) { color: var(--text); }
:deep(.el-textarea__inner) { background: var(--bg-panel-2); color: var(--text); border-color: var(--border); }
</style>
