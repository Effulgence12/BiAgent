const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const messages = document.querySelector("#messages");
const bootstrapButton = document.querySelector("#bootstrap");
const panels = {
  chart: document.querySelector("#chart"),
  sql: document.querySelector("#sql pre"),
  advice: document.querySelector("#advice"),
  raw: document.querySelector("#raw pre"),
};

function appendMessage(text, role) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function setLoading(text = "分析中，首次运行会自动下载/导入数据，请稍候...") {
  panels.chart.innerHTML = `<p>${text}</p>`;
  panels.sql.textContent = "";
  panels.advice.innerHTML = "";
  panels.raw.textContent = "";
}

function renderResponse(data) {
  panels.chart.innerHTML = data.chart_html;
  panels.sql.textContent = `${data.sql}\n\nroute=${data.route}\nmatched_views=${data.matched_views.join(", ") || "base tables"}\nelapsed_ms=${data.elapsed_ms}`;
  const forecast = data.forecast.length
    ? `<h3>预测</h3><pre>${JSON.stringify(data.forecast, null, 2)}</pre>`
    : "";
  panels.advice.innerHTML = `<h3>摘要</h3><p>${data.summary}</p><h3>建议</h3><ol>${data.recommendations.map((item) => `<li>${item}</li>`).join("")}</ol>${forecast}`;
  panels.raw.textContent = JSON.stringify(data, null, 2);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  appendMessage(question, "user");
  input.value = "";
  setLoading();

  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    panels.chart.textContent = `请求失败：${response.status}`;
    appendMessage("分析请求失败，请检查后端日志。", "assistant");
    return;
  }

  const data = await response.json();
  renderResponse(data);
  appendMessage(`已完成 ${data.analysis_type} 分析，命中：${data.matched_views.join(", ") || "基础表回退"}，耗时 ${data.elapsed_ms}ms`, "assistant");
});

bootstrapButton.addEventListener("click", async () => {
  setLoading("正在初始化/刷新本地数据...");
  const response = await fetch("/api/bootstrap?force=true", { method: "POST" });
  const data = await response.json();
  panels.raw.textContent = JSON.stringify(data, null, 2);
  panels.chart.innerHTML = "<p>数据初始化完成，请继续提问。</p>";
  appendMessage(`数据初始化完成：${data.source}`, "assistant");
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`#${button.dataset.target}`).classList.add("active");
  });
});
