<template>
  <div class="chat-page">
    <div ref="messagesEl" class="messages">
      <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-row', msg.role]"
      >
        <div v-if="msg.role === 'assistant'" class="avatar">🤖</div>

        <div class="bubble">
          <div v-if="msg.type === 'text'">
            {{ msg.content }}
          </div>

          <div v-else-if="msg.type === 'steps'" class="steps">
            <div v-for="(step, sIdx) in msg.steps" :key="sIdx" class="step">
              <span class="dot" :class="step.status"></span>
              <span>{{ step.text }}</span>
            </div>
          </div>

          <div v-else-if="msg.type === 'table'" class="table-wrap">
            <table class="result-table">
              <thead>
              <tr>
                <th v-for="col in msg.columns" :key="col">
                  {{ col }}
                </th>
              </tr>
              </thead>
              <tbody>
              <tr v-for="(row, rIdx) in msg.rows" :key="rIdx">
                <td v-for="col in msg.columns" :key="col">
                  {{ row[col] }}
                </td>
              </tr>
              </tbody>
            </table>
          </div>

          <div
              v-else-if="msg.type === 'markdown'"
              class="markdown-body"
              v-html="parseMarkdown(msg.content)"
          ></div>

          <div v-else-if="msg.type === 'error'" class="error-text">
            {{ msg.content }}
          </div>
        </div>

        <div v-if="msg.role === 'user'" class="avatar">🧑</div>
      </div>
      <div class="messages-bottom-spacer"></div>
    </div>

    <div class="input-wrapper">
      <div class="input-box">
        <input
            v-model="question"
            @keyup.enter="sendQuestion"
            placeholder="请输入你的问题..."
        />
        <button @click="sendQuestion" :disabled="loading">
          {{ loading ? "执行中..." : "发送" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import {nextTick, ref} from "vue";
import {marked} from "marked";

const API_URL = "/api/query";

const question = ref("");
const loading = ref(false);
const messages = ref([]);
const messagesEl = ref(null);

// 流式 markdown 累积索引用
let currentMdIndex = -1;

// 将 markdown 字符串转为 HTML
function parseMarkdown(text) {
  if (!text) return "";
  return marked.parse(text);
}

function scrollToBottom() {
  const el = messagesEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function sendQuestion() {
  if (!question.value || loading.value) return;

  const q = question.value;
  question.value = "";
  loading.value = true;
  currentMdIndex = -1;

  messages.value.push({role: "user", type: "text", content: q});

  const stepIndex =
      messages.value.push({
        role: "assistant",
        type: "steps",
        steps: [],
      }) - 1;

  await nextTick();
  scrollToBottom();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: q}),
    });

    if (!response.body) throw new Error("服务器未返回流");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const {value, done} = await reader.read();

      if (value) {
        buffer += decoder.decode(value, {stream: true});
      }

      if (done) {
        buffer += decoder.decode();
      }

      // 逐行解析，空行作为 SSE 事件分隔符（避免 JSON 内部 \n\n 导致截断）
      const lines = buffer.split(/\r?\n/);
      if (!done) {
        buffer = lines.pop() || "";
      } else {
        buffer = "";
      }

      let dataString = "";

      for (const line of lines) {
        // 空行 = SSE 事件结束，处理当前累积的 data
        if (line.trim() === "") {
          if (dataString) {
            processEvent(dataString, stepIndex);
            dataString = "";
          }
          continue;
        }

        if (line.startsWith("data:")) {
          dataString += line.replace(/^data:\s*/, "");
        }
      }

      // 流结束时处理最后一个事件（可能没有尾部空行）
      if (done && dataString) {
        processEvent(dataString, stepIndex);
      }

      if (done) break;
    }
  } catch (e) {
    messages.value.push({
      role: "assistant",
      type: "error",
      content: e?.message || "请求失败",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

function processEvent(dataString, stepIndex) {
  if (!dataString || dataString === "[DONE]") return;

  let data;
  try {
    data = JSON.parse(dataString);
  } catch (err) {
    console.error("❌ JSON 解析失败!", err);
    console.error("❌ 导致崩溃的原始数据:", dataString);

    const steps = messages.value[stepIndex].steps;
    const last = steps.at(-1);
    if (last && last.status === "running") {
      last.status = "error";
    }
    return;
  }

  // ✅ 打印语句要放在解析成功之后
  // console.log("解析出的完整 data 对象:", data);

  const steps = messages.value[stepIndex].steps;

  if (data.state) {
    const last = steps.at(-1);
    if (last && last.status === "running") last.status = "success";
    steps.push({text: data.state, status: "running"});

  } else if (data.error) {
    const last = steps.at(-1);
    if (last) last.status = "error";
    messages.value.push({
      role: "assistant",
      type: "error",
      content: data.error,
    });

  } else if (data.content !== undefined) {
    const last = steps.at(-1);
    if (last && last.status === "running") last.status = "success";

    if (currentMdIndex === -1) {
      currentMdIndex = messages.value.push({
        role: "assistant",
        type: "markdown",
        content: data.content,
      }) - 1;
    } else {
      messages.value[currentMdIndex].content += data.content;
    }

  } else if (data.result !== undefined) {
    // ✅ 修复了少了 .log 的问题
    console.log("成功触发 result 渲染:", data.result);

    const last = steps.at(-1);
    if (last && last.status === "running") last.status = "success";

    if (Array.isArray(data.result) && typeof data.result[0] !== 'string') {
      messages.value.push({
        role: "assistant",
        type: "table",
        columns: Object.keys(data.result[0] || {}),
        rows: data.result,
      });
    } else {
      let mdContent = Array.isArray(data.result) ? data.result.join('\n') : data.result;
      messages.value.push({
        role: "assistant",
        type: "markdown",
        content: typeof mdContent === 'string' ? mdContent : JSON.stringify(mdContent),
      });
    }
  }
}
</script>
<style scoped>
/* 覆盖 Vite 默认居中 */
:global(html),
:global(body) {
  height: 100%;
  margin: 0;
}

:global(body) {
  display: block !important;
  place-items: unset !important;
}

:global(#app) {
  height: 100%;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* 页面 */
.chat-page {
  height: 100%;
  overflow: hidden;
  background: #fff;
}

/* 消息区 */
.messages {
  height: 100%;
  overflow-y: auto;
  padding: 20px 20% 160px;
}

.message-row {
  display: flex;
  margin-bottom: 14px;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-row.user {
  justify-content: flex-end;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
}

.bubble {
  max-width: min(820px, 72%);
  padding: 12px 14px;
  border-radius: 12px;
  background: #f5f5f5;
  overflow: hidden;
}

.message-row.user .bubble {
  background: #e6f4ff;
}

/* 步骤 */
.steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.running {
  background: #f1c40f;
}

.dot.success {
  background: #2ecc71;
}

.dot.error {
  background: #e74c3c;
}

/* 表格 */
.table-wrap {
  max-width: 100%;
  overflow-x: auto;
}

.result-table {
  width: max-content;
  min-width: 100%;
  table-layout: auto;
  border-collapse: collapse;
}

.result-table th,
.result-table td {
  border: 1px solid #ddd;
  padding: 6px 12px;
  white-space: nowrap;
  font-size: 13px;
  text-align: left;
}

.result-table th {
  background: #fafafa;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}

/* Markdown 样式 */
.markdown-body {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  word-wrap: break-word;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.markdown-body :deep(h1) {
  font-size: 1.5em;
}

.markdown-body :deep(h2) {
  font-size: 1.3em;
}

.markdown-body :deep(h3) {
  font-size: 1.1em;
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin-bottom: 10px;
}

.markdown-body :deep(code) {
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  color: #d14;
}

.markdown-body :deep(pre) {
  background: #2d2d2d;
  color: #ccc;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 10px;
}

.markdown-body :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 10px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #ddd;
  padding: 6px 12px;
}

.markdown-body :deep(th) {
  background: #f0f0f0;
}

/* 错误 */
.error-text {
  color: #e74c3c;
  font-weight: 600;
}

/* 悬浮输入框 */
.input-wrapper {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 24px;
  display: flex;
  justify-content: center;
  padding: 0 16px;
  pointer-events: none;
}

.input-box {
  pointer-events: auto;
  width: 100%;
  max-width: 720px;
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
}

.input-box input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
}

.input-box button {
  padding: 8px 18px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  color: #fff;
  cursor: pointer;
}

.input-box button:disabled {
  opacity: 0.5;
}

.messages-bottom-spacer {
  height: 200px;
}
</style>
