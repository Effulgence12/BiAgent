const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const messages = document.querySelector("#messages");
const bootstrapButton = document.querySelector("#bootstrap");
const sessionLabel = document.querySelector("#session-id");
const connectionState = document.querySelector("#connection-state");
const stageLabel = document.querySelector("#stage-label");
const downloadChartButton = document.querySelector("#download-chart");
const downloadImageButton = document.querySelector("#download-image");

const panels = {
  kpis: document.querySelector("#kpis"),
  directAnswer: document.querySelector("#direct-answer"),
  summary: document.querySelector("#summary-text"),
  chartList: document.querySelector("#chart-list"),
  chartStage: document.querySelector("#chart-stage"),
  chartTitle: document.querySelector("#chart-title"),
  chartSource: document.querySelector("#chart-source"),
  sql: document.querySelector("#sql-output"),
  agent: document.querySelector("#agent-events"),
  advice: document.querySelector("#advice-stream"),
  forecast: document.querySelector("#forecast-json"),
  raw: document.querySelector("#raw-output"),
};

let activeSocket = null;
let activeChart = null;
let sessionId = localStorage.getItem("olistAgenticBiSession");

if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem("olistAgenticBiSession", sessionId);
}
sessionLabel.textContent = shortSession(sessionId);

function shortSession(value) {
  return value ? value.slice(0, 8) : "未分配";
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function appendMessage(text, role) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function setPill(node, text, mode = "idle") {
  node.textContent = text;
  node.className = `state-pill ${mode}`;
}

function setStage(text, mode = "idle") {
  setPill(stageLabel, text, mode);
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((node) => {
    node.classList.toggle("active", node.dataset.target === name);
  });
  document.querySelectorAll(".tab-panel").forEach((node) => {
    node.classList.toggle("active", node.id === name);
  });
}

function resetResult(text = "正在建立 WebSocket 流式分析，请稍候...") {
  panels.kpis.innerHTML = renderKpis({});
  panels.directAnswer.textContent = text;
  panels.summary.textContent = "等待真实 SQL 查询结果。";
  panels.chartList.innerHTML = "";
  panels.chartStage.textContent = text;
  panels.chartTitle.textContent = "图表工作区";
  panels.chartSource.textContent = "等待可视化 Agent 输出。";
  panels.sql.textContent = "等待 SQL 规划...";
  panels.agent.innerHTML = "";
  panels.advice.textContent = "等待真实大模型流式输出...";
  panels.forecast.innerHTML = "";
  panels.raw.textContent = "[]";
  activeChart = null;
  downloadChartButton.disabled = true;
  downloadImageButton.disabled = true;
  setStage("分析中", "running");
  activateTab("overview");
}

function setError(text) {
  setStage("失败", "error");
  setPill(connectionState, "错误", "error");
  panels.directAnswer.textContent = text;
  panels.summary.textContent = "本系统不使用本地模板伪装成功，请根据错误修复后重试。";
  panels.chartStage.textContent = text;
  panels.advice.textContent = text;
}

function renderKpis(state) {
  const items = [
    ["分析类型", state.analysisType || "-"],
    ["命中视图", state.matchedViews?.length ? state.matchedViews.join(", ") : "-"],
    ["查询耗时", state.elapsedMs ? `${state.elapsedMs} ms` : "-"],
    ["图表数量", state.charts?.length ? `${state.charts.length}` : "-"],
  ];
  return items
    .map(([label, value]) => `<article class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join("");
}

function renderAgentEvent(event) {
  const node = document.createElement("li");
  const map = {
    agent_start: `启动 ${event.agent}`,
    agent_done: `完成 ${event.agent}`,
    plan: `规划 ${event.analysis_type}`,
    sql_planned: "生成 SQL 任务",
    sql: "生成 SQL 任务",
    query_done: `完成真实数据查询 ${event.elapsed_ms ?? ""}ms`,
    summary: `完成真实数据查询 ${event.elapsed_ms ?? ""}ms`,
    chart_done: "生成可视化图表",
    chart: "生成可视化图表",
    llm_usage: `大模型 token: ${event.total_tokens}`,
    final: "流程完成",
    done: "流程完成",
  };
  node.innerHTML = `<span>${escapeHtml(map[event.event] || event.event)}</span>`;
  panels.agent.appendChild(node);
}

function setHtmlWithScripts(container, html) {
  container.innerHTML = "";
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.childNodes.forEach((node) => {
    if (node.nodeName.toLowerCase() !== "script") {
      container.appendChild(node.cloneNode(true));
      return;
    }
    const script = document.createElement("script");
    [...node.attributes].forEach((attr) => script.setAttribute(attr.name, attr.value));
    script.textContent = node.textContent;
    script.async = false;
    container.appendChild(script);
  });
}

function renderSql(event) {
  const tasks = event.sql_tasks?.length
    ? event.sql_tasks.map((task, index) => `#${index + 1} ${task.name} - ${task.purpose}\n${task.sql}`).join("\n\n")
    : event.sql || "";
  const matchedViews = event.matched_views?.join(", ") || "base tables";
  panels.sql.textContent = `${tasks}\n\nroute=${event.route || "-"}\nmatched_views=${matchedViews}`;
}

function renderSummary(state) {
  panels.kpis.innerHTML = renderKpis(state);
  panels.directAnswer.textContent = state.directAnswer || "已完成查询，等待直答。";
  panels.summary.textContent = state.summary || "等待数据摘要...";
}

function selectChart(chart, index) {
  activeChart = chart;
  panels.chartTitle.textContent = chart.title || `图表 ${index + 1}`;
  panels.chartSource.textContent = `${chart.type || "chart"} · ${chart.source_view || "query_result"} · ${chart.summary || ""}`;
  setHtmlWithScripts(panels.chartStage, chart.html || "<p>该图表没有 HTML 内容。</p>");
  downloadChartButton.disabled = !chart.html;
  downloadImageButton.disabled = !(chart.type || "").startsWith("plotly");
  document.querySelectorAll(".chart-button").forEach((button, buttonIndex) => {
    button.classList.toggle("active", buttonIndex === index);
  });
}

function renderCharts(charts, fallbackHtml = "") {
  const usableCharts = Array.isArray(charts) ? charts : [];
  if (!usableCharts.length && fallbackHtml) {
    panels.chartList.innerHTML = "";
    panels.chartTitle.textContent = "图表工作区";
    panels.chartSource.textContent = "兼容旧图表输出。";
    setHtmlWithScripts(panels.chartStage, fallbackHtml);
    downloadChartButton.disabled = true;
    downloadImageButton.disabled = true;
    return;
  }
  if (!usableCharts.length) {
    panels.chartList.innerHTML = "";
    panels.chartStage.textContent = "当前问题没有可视化图表。";
    downloadChartButton.disabled = true;
    downloadImageButton.disabled = true;
    return;
  }
  panels.chartList.innerHTML = usableCharts
    .map((chart, index) => `<button class="chart-button" type="button" data-index="${index}">${escapeHtml(chart.title || `图表 ${index + 1}`)}</button>`)
    .join("");
  panels.chartList.querySelectorAll(".chart-button").forEach((button) => {
    button.addEventListener("click", () => selectChart(usableCharts[Number(button.dataset.index)], Number(button.dataset.index)));
  });
  selectChart(usableCharts[0], 0);
}

function appendAdviceDelta(state, content) {
  if (!content) return;
  if (!state.adviceText) {
    panels.advice.textContent = "";
  }
  state.adviceText += content;
  panels.advice.textContent += content;
}

function renderForecast(forecast) {
  if (!forecast?.length) {
    panels.forecast.innerHTML = "";
    return;
  }
  panels.forecast.innerHTML = `<h3>预测区间</h3><pre>${escapeHtml(JSON.stringify(forecast, null, 2))}</pre>`;
}

function wsUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function startStreamingAnalysis(question) {
  if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
    activeSocket.close();
  }

  const state = {
    question,
    analysisType: "",
    matchedViews: [],
    elapsedMs: "",
    directAnswer: "",
    summary: "",
    charts: [],
    forecast: [],
    adviceText: "",
    events: [],
    finished: false,
    failed: false,
  };
  let rawRenderTimer = null;
  const socket = new WebSocket(wsUrl("/ws/analyze"));
  activeSocket = socket;

  function scheduleRawRender(force = false) {
    if (force) {
      panels.raw.textContent = JSON.stringify(state.events, null, 2);
      return;
    }
    if (rawRenderTimer) return;
    rawRenderTimer = window.setTimeout(() => {
      panels.raw.textContent = JSON.stringify(state.events, null, 2);
      rawRenderTimer = null;
    }, 250);
  }

  socket.addEventListener("open", () => {
    setPill(connectionState, "流式连接", "running");
    socket.send(JSON.stringify({ session_id: sessionId, question }));
  });

  socket.addEventListener("message", (message) => {
    const event = JSON.parse(message.data);
    state.events.push(event);
    scheduleRawRender(event.event !== "llm_delta");
    renderAgentEvent(event);

    if (event.event === "session") {
      sessionId = event.session_id;
      localStorage.setItem("olistAgenticBiSession", sessionId);
      sessionLabel.textContent = shortSession(sessionId);
      return;
    }

    if (event.event === "plan") {
      state.analysisType = event.analysis_type;
      panels.kpis.innerHTML = renderKpis(state);
      panels.directAnswer.textContent = `已生成 ${event.analysis_type} 分析计划，正在查询真实数据。`;
      setStage("SQL 规划", "running");
      return;
    }

    if (event.event === "sql_planned" || event.event === "sql") {
      state.matchedViews = event.matched_views || [];
      renderSql(event);
      setStage("查询完成", "running");
      return;
    }

    if (event.event === "query_done" || event.event === "summary") {
      state.summary = event.summary || "";
      state.directAnswer = event.direct_answer || "";
      state.elapsedMs = event.elapsed_ms || "";
      renderSummary(state);
      setStage("生成图表", "running");
      return;
    }

    if (event.event === "chart_done" || event.event === "chart") {
      state.charts = event.charts || [];
      renderCharts(state.charts, event.chart_html || "");
      panels.kpis.innerHTML = renderKpis(state);
      setStage("等待建议", "running");
      return;
    }

    if (event.event === "llm_delta") {
      appendAdviceDelta(state, event.content);
      return;
    }

    if (event.event === "data_error" || event.event === "llm_error" || event.event === "sql_error") {
      state.failed = true;
      const label = event.event === "data_error" ? "数据错误" : event.event === "llm_error" ? "大模型错误" : "SQL规划错误";
      setError(`${label}：${event.error}`);
      appendMessage(`${label}：${event.error}`, "assistant");
      return;
    }

    if (event.event === "final" || event.event === "done") {
      state.finished = true;
      state.forecast = event.forecast || [];
      renderForecast(state.forecast);
      scheduleRawRender(true);
      setStage("完成", "done");
      setPill(connectionState, "就绪", "idle");
      appendMessage(
        `已完成 ${state.analysisType || "BI"} 分析，命中：${state.matchedViews.join(", ") || "基础表"}，查询耗时 ${state.elapsedMs || "-"}ms。`,
        "assistant",
      );
    }
  });

  socket.addEventListener("error", () => {
    state.failed = true;
    setError("WebSocket 连接失败，请检查后端是否启动。");
    appendMessage("WebSocket 连接失败，请检查后端是否启动。", "assistant");
  });

  socket.addEventListener("close", () => {
    if (!state.finished && !state.failed) {
      setError("流式连接提前关闭，请检查后端日志。");
      appendMessage("流式连接提前关闭，请检查后端日志。", "assistant");
    }
  });
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  appendMessage(question, "user");
  input.value = "";
  resetResult();
  startStreamingAnalysis(question);
});

bootstrapButton.addEventListener("click", async () => {
  resetResult("正在初始化/刷新本地真实数据...");
  const response = await fetch("/api/bootstrap?force=true", { method: "POST" });
  const data = await response.json();
  panels.raw.textContent = JSON.stringify(data, null, 2);
  if (!response.ok) {
    const detail = data.detail || `请求失败：${response.status}`;
    setError(detail);
    appendMessage(`数据初始化失败：${detail}`, "assistant");
    return;
  }
  setStage("数据就绪", "done");
  panels.directAnswer.textContent = "数据初始化完成，请继续提问。";
  panels.summary.textContent = `数据来源：${data.source}`;
  appendMessage(`数据初始化完成：${data.source}`, "assistant");
});

downloadChartButton.addEventListener("click", () => {
  if (!activeChart?.html) return;
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(activeChart.title || "Olist 图表")}</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script></head><body>${activeChart.html}</body></html>`;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${activeChart.id || "olist-chart"}.html`;
  link.click();
  URL.revokeObjectURL(link.href);
});

downloadImageButton.addEventListener("click", () => {
  if (!activeChart || !(activeChart.type || "").startsWith("plotly")) return;
  const plot = panels.chartStage.querySelector(".plotly-graph-div");
  if (!plot || !window.Plotly) return;
  window.Plotly.downloadImage(plot, {
    format: "png",
    filename: activeChart.id || "olist-chart",
    height: 720,
    width: 1180,
    scale: 2,
  });
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.target));
});

panels.kpis.innerHTML = renderKpis({});
