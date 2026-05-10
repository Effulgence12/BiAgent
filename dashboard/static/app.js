const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const messages = document.querySelector("#messages");
const result = document.querySelector("#result");

function appendMessage(text, role) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  appendMessage(question, "user");
  input.value = "";
  result.textContent = "分析中...";

  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    result.textContent = `请求失败：${response.status}`;
    appendMessage("分析请求失败，请检查后端日志。", "assistant");
    return;
  }

  const data = await response.json();
  result.textContent = JSON.stringify(data, null, 2);
  appendMessage(`已生成 ${data.analysis_type} 分析计划，并命中：${data.matched_views.join(", ") || "基础表回退"}`, "assistant");
});
