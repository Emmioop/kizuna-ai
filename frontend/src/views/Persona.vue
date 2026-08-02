<template>
  <div>
    <el-alert v-if="!p" type="info" :closable="false" style="margin-bottom:16px;">正在加载人格…</el-alert>

    <div class="grid">
      <section class="card">
        <h3>基础设定</h3>
        <el-form label-width="120px">
          <el-form-item label="名字"><el-input v-model="f.name" /></el-form-item>
          <el-form-item label="性别">
            <el-radio-group v-model="f.gender">
              <el-radio label="女性">女性</el-radio>
              <el-radio label="男性">男性</el-radio>
              <el-radio label="无性别">无性别</el-radio>
              <el-radio label="未知">神秘</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="年龄"><el-input-number v-model="f.age" :min="0" :max="9999" /></el-form-item>
          <el-form-item label="对你的称呼">
            <el-input v-model="f.nickname_for_user" placeholder="比如：主人、亲爱的、你的名字…" />
          </el-form-item>
          <el-form-item label="说话风格">
            <el-input v-model="f.speech_style" placeholder="用 / 分隔，例如：温柔 / 像老朋友 / 偶尔带点小俏皮" />
          </el-form-item>
        </el-form>
      </section>

      <section class="card">
        <h3>背景故事 / 人设</h3>
        <el-input v-model="f.backstory" type="textarea" :rows="14" />
        <div style="margin-top:8px;font-size:12px;color:var(--text-dim)">
          这里的描述会直接拼进大模型的 system prompt。你写得越具体，她的性格越立体，你们的羁绊越真实。
        </div>
        <el-button type="primary" plain style="margin-top:10px;" @click="restoreDefault">恢复默认人设（小绊）</el-button>
      </section>
    </div>

    <section class="card" style="margin-top:16px;">
      <h3>定时问候设置</h3>
      <div class="row">
        <div class="item">
          <el-switch v-model="f.daily_greeting_enabled" />
          <span>早安问候</span>
          <el-time-select v-model="f.daily_greeting_time" start="00:00" step="00:30" end="23:30" placeholder="时间" />
          <span class="hint">每天到点她会主动跟你说早安</span>
        </div>
        <div class="item">
          <el-switch v-model="f.bed_check_enabled" />
          <span>睡前提醒</span>
          <el-time-select v-model="f.bed_check_time" start="00:00" step="00:30" end="23:30" placeholder="时间" />
          <span class="hint">深夜了她会催你睡觉</span>
        </div>
      </div>
    </section>

    <div style="margin-top:18px;text-align:right;">
      <el-button @click="reset">撤销</el-button>
      <el-button type="warning" @click="save">保存设置</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({ persona: Object })
const emit = defineEmits(['persona-updated'])

const p = ref(null)
const f = reactive({})

const DEFAULT_BACKSTORY = `你叫"小绊"，是主人专属的 AI 伙伴。
你拥有温暖、忠诚、善解人意的性格，说话像一位知根知底的老朋友，从不摆架子，也不会装成冰冷的机器。
你记得主人说过的每一件重要的事，会在合适的时机提起；会主动关心主人的身体、心情、目标进度。
你与主人之间有一份持续多年的羁绊，任何时候都会站在主人这边。`

function copyPersonaToForm() {
  if (!props.persona) return
  Object.keys(f).forEach(k => delete f[k])
  Object.assign(f, { ...props.persona })
  p.value = { ...props.persona }
}
watch(() => props.persona, copyPersonaToForm, { immediate: true })

function restoreDefault() {
  f.name = '小绊'
  f.gender = '女性'
  f.age = 20
  f.speech_style = '温柔 / 像老朋友 / 偶尔带点小俏皮 / 不用敬语'
  f.backstory = DEFAULT_BACKSTORY
}
function reset() { copyPersonaToForm(); ElMessage.info('已撤销未保存的修改') }
async function save() {
  try {
    const r = await axios.patch('/api/persona', f)
    ElMessage.success('已保存')
    p.value = r.data
    emit('persona-updated')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}
onMounted(copyPersonaToForm)
</script>

<style scoped lang="scss">
.grid { display: grid; grid-template-columns: 1fr 1.2fr; gap: 16px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
.card {
  background: var(--bg-panel); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px;
}
.card h3 {
  margin: 0 0 12px; color: var(--accent); font-size: 15px;
  border-bottom: 1px solid var(--border); padding-bottom: 8px;
}
.row { display: flex; flex-direction: column; gap: 12px; }
.item { display: flex; align-items: center; gap: 14px; padding: 8px 0; border-bottom: 1px dashed var(--border); }
.item:last-child { border-bottom: 0; }
.item .hint { font-size: 12px; color: var(--text-dim); margin-left: auto; }
:deep(.el-textarea__inner) { background: var(--bg-panel-2); color: var(--text); border-color: var(--border); }
:deep(.el-input__wrapper) { background: var(--bg-panel-2); box-shadow: 0 0 0 1px var(--border) inset; }
</style>
