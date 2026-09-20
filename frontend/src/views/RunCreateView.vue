<template>
  <div class="page">
    <h1>新建实验 Run</h1>
    <p class="muted">提交 StartRun 命令：写入 event_store 并投影为 running</p>
    <div class="card" style="max-width: 720px">
      <n-alert
        v-if="errorMsg"
        type="error"
        closable
        style="margin-bottom: 16px"
        @close="errorMsg = ''"
      >
        {{ errorMsg }}
      </n-alert>
      <n-alert v-else-if="dupWarning" type="warning" style="margin-bottom: 16px">
        {{ dupWarning }}
      </n-alert>
      <n-form label-placement="top">
        <n-form-item label="项目 project" required>
          <n-input v-model:value="form.project" placeholder="protein-folding" />
        </n-form-item>
        <n-form-item label="名称 name" required>
          <n-input v-model:value="form.name" placeholder="实验名称" />
        </n-form-item>
        <n-form-item label="数据集指纹 dataset_content_sha256（64 位 hex）" required>
          <n-input v-model:value="form.dataset_content_sha256" class="mono" placeholder="64 hex" />
          <n-button text type="primary" style="margin-top: 4px" @click="fillDataset">用示例填充</n-button>
        </n-form-item>
        <n-form-item label="代码提交 code_commit_sha" required>
          <n-input v-model:value="form.code_commit_sha" class="mono" placeholder="git commit sha" />
          <n-button text type="primary" style="margin-top: 4px" @click="fillCommit">用示例填充</n-button>
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" type="textarea" :rows="3" />
        </n-form-item>
        <n-button type="primary" :loading="loading" @click="submit">启动 Run</n-button>
      </n-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { createRun, listRuns } from '../api/client'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const errorMsg = ref('')
const dupWarning = ref('')

const form = reactive({
  project: 'protein-folding',
  name: '',
  dataset_content_sha256: '',
  code_commit_sha: '',
  description: '',
  expected_version: 0,
})

// 预检：同 project 下若已有未结束（running）的同名 Run，提前在页面上提示。
// 仅作提示，最终以服务端校验为准。
let dupTimer = null
watch([() => form.project, () => form.name], () => {
  errorMsg.value = ''
  dupWarning.value = ''
  clearTimeout(dupTimer)
  const project = form.project.trim()
  const name = form.name.trim()
  if (!project || !name) return
  dupTimer = setTimeout(async () => {
    try {
      const runs = await listRuns({ project, status: 'running' })
      if (runs.some((r) => r.name === name)) {
        dupWarning.value = `项目「${project}」下已存在进行中的同名 Run「${name}」，需先完成或中止该 Run 后才能再次使用此名称`
      }
    } catch {
      /* 预检失败不阻塞提交，以服务端校验为准 */
    }
  }, 400)
})

function randomHex(n) {
  const bytes = new Uint8Array(n)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

function fillDataset() {
  form.dataset_content_sha256 = randomHex(32)
}

function fillCommit() {
  form.code_commit_sha = randomHex(20)
}

async function submit() {
  if (!form.name.trim()) {
    message.warning('请填写名称')
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const run = await createRun({ ...form })
    message.success('Run 已启动')
    router.push(`/runs/${run.id}`)
  } catch (e) {
    // 服务端拒绝（如同名未结束 Run 冲突 409）时，在新建页展示原因
    errorMsg.value = e.message || '创建失败'
  } finally {
    loading.value = false
  }
}
</script>
