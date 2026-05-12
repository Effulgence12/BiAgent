const form = document.querySelector("#question-form");
const input = document.querySelector("#question");
const messages = document.querySelector("#messages");
const bootstrapButton = document.querySelector("#bootstrap");
const sessionLabel = document.querySelector("#session-id");
const memoryCount = document.querySelector("#memory-count");
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
let lastFailedRequest = null;
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

function appendMessage(text, role, extraNode = null) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  const textNode = document.createElement("div");
  textNode.textContent = text;
  node.appendChild(textNode);
  if (extraNode) node.appendChild(extraNode);
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
  if (name === "chart") resizeActivePlot();
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

function retryControls() {
  const wrapper = document.createElement("div");
  wrapper.className = "retry-actions";

  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "secondary compact";
  retry.textContent = "重试原问题";
  retry.disabled = !lastFailedRequest;
  retry.addEventListener("click", () => {
    if (!lastFailedRequest) return;
    const original = lastFailedRequest.question;
    appendMessage(`重试原问题：${original}`, "user");
    resetResult("正在携带上次错误上下文重试原问题...");
    startStreamingAnalysis(original, {
      retryOf: lastFailedRequest.requestId,
      errorContext: lastFailedRequest.error,
    });
  });

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "secondary compact";
  copy.textContent = "复制错误";
  copy.disabled = !lastFailedRequest?.error;
  copy.addEventListener("click", async () => {
    if (!lastFailedRequest?.error) return;
    await navigator.clipboard.writeText(lastFailedRequest.error);
  });

  wrapper.append(retry, copy);
  return wrapper;
}

function rememberFailure(event, fallbackQuestion) {
  lastFailedRequest = {
    requestId: event.request_id || crypto.randomUUID(),
    question: event.question || fallbackQuestion,
    error: event.error || "未知错误",
    event: event.event,
  };
}

function setError(text) {
  setStage("失败", "error");
  setPill(connectionState, "错误", "error");
  panels.directAnswer.textContent = text;
  panels.summary.textContent = "本系统不使用本地模板伪装成功；请根据真实错误修复或重试原问题。";
  panels.chartStage.innerHTML = "";
  panels.chartStage.append(document.createTextNode(text), retryControls());
  panels.advice.innerHTML = "";
  panels.advice.append(document.createTextNode(text), retryControls());
}

function renderKpis(state) {
  const items = [
    ["分析类型", state.analysisType || "-"],
    ["命中视图", state.matchedViews?.length ? state.matchedViews.join(", ") : "-"],
    ["查询耗时", state.elapsedMs ? `${state.elapsedMs} ms` : "-"],
    ["图表数量", state.charts?.length ? `${state.charts.length}` : "-"],
    ["会话记忆", Number.isInteger(state.memoryTurns) ? `${state.memoryTurns} 轮` : "-"],
  ];
  return items
    .map(([label, value]) => `<article class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join("");
}

function agentDetail(event) {
  if (event.event === "plan") {
    return {
      意图: event.intent || "-",
      分析类型: event.analysis_type || "-",
      需要Agent: event.required_agents || [],
      需要视图: event.required_views || [],
      追问引用: event.followup_reference || "-",
      是否二次规划: Boolean(event.refined),
    };
  }
  if (event.event === "sql_planned" || event.event === "sql") {
    return {
      SQL任务数: event.task_count ?? event.sql_tasks?.length ?? 0,
      命中视图: event.matched_views || [],
      路由: event.route || "-",
      SQL任务: (event.sql_tasks || []).map((task) => ({ name: task.name, purpose: task.purpose })),
    };
  }
  if (event.event === "agent_done" && event.agent === "forecast_model") {
    return {
      预测点数: event.forecast_count || 0,
      模型诊断: event.forecast_diagnostics || {},
    };
  }
  if (event.event === "data_error" || event.event === "llm_error" || event.event === "sql_error") {
    return {
      错误类型: event.event,
      原问题: event.question || "-",
      请求ID: event.request_id || "-",
      错误: event.error || "-",
    };
  }
  return null;
}

function renderAgentEvent(event) {
  if (event.event === "llm_delta") return;
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
    memory: `载入会话记忆 ${event.turn_count || 0} 轮`,
    memory_updated: `写入会话记忆 ${event.turn_count || 0} 轮`,
    llm_usage: `大模型 token: ${event.total_tokens}`,
    data_error: "数据错误",
    llm_error: "大模型错误",
    sql_error: "SQL规划/执行错误",
    final: "流程完成",
    done: "流程完成",
  };
  node.innerHTML = `<span>${escapeHtml(map[event.event] || event.event)}</span>`;
  const detail = agentDetail(event);
  if (detail) {
    const details = document.createElement("details");
    details.className = "agent-detail";
    if (event.event === "plan" || event.event === "sql_planned" || event.event.endsWith("_error")) details.open = true;
    details.innerHTML = `<summary>查看输入/输出摘要</summary><pre>${escapeHtml(JSON.stringify(detail, null, 2))}</pre>`;
    node.appendChild(details);
  }
  panels.agent.appendChild(node);
}

function setHtmlWithScripts(container, html) {
  container.innerHTML = html;
  container.querySelectorAll("details.chart-data").forEach((node) => {
    node.open = true;
  });
  container.querySelectorAll("script").forEach((node) => {
    const script = document.createElement("script");
    [...node.attributes].forEach((attr) => script.setAttribute(attr.name, attr.value));
    script.textContent = node.textContent;
    script.async = false;
    node.replaceWith(script);
  });
  window.setTimeout(resizeActivePlot, 80);
}

function resizeActivePlot() {
  if (!window.Plotly || !panels.chartStage) return;
  panels.chartStage.querySelectorAll(".plotly-graph-div").forEach((plot) => {
    window.Plotly.Plots.resize(plot);
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
  if (!state.adviceText) panels.advice.textContent = "";
  state.adviceText += content;
  panels.advice.textContent += content;
}

function renderForecast(forecast, diagnostics = {}) {
  if (!forecast?.length && !Object.keys(diagnostics || {}).length) {
    panels.forecast.innerHTML = "";
    return;
  }
  const diagRows = Object.entries(diagnostics || {})
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(Array.isArray(value) ? value.join("; ") : JSON.stringify(value))}</td></tr>`)
    .join("");
  panels.forecast.innerHTML = `
    <h3>预测区间与模型诊断</h3>
    ${diagRows ? `<table class="data-table forecast-diagnostics"><tbody>${diagRows}</tbody></table>` : ""}
    ${forecast?.length ? `<pre>${escapeHtml(JSON.stringify(forecast, null, 2))}</pre>` : ""}
  `;
}

function wsUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function startStreamingAnalysis(question, options = {}) {
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
    forecastDiagnostics: {},
    adviceText: "",
    memoryTurns: 0,
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
    socket.send(JSON.stringify({
      session_id: sessionId,
      question,
      retry_of: options.retryOf || "",
      error_context: options.errorContext || "",
    }));
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

    if (event.event === "memory" || event.event === "memory_updated") {
      state.memoryTurns = event.turn_count || 0;
      memoryCount.textContent = `记忆 ${state.memoryTurns} 轮`;
      panels.kpis.innerHTML = renderKpis(state);
      if (event.last_question) panels.summary.textContent = `已载入上一轮上下文：${event.last_question}`;
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
      rememberFailure(event, question);
      const label = event.event === "data_error" ? "数据错误" : event.event === "llm_error" ? "大模型错误" : "SQL规划/执行错误";
      setError(`${label}：${event.error}`);
      appendMessage(`${label}：${event.error}`, "assistant", retryControls());
      return;
    }

    if (event.event === "final" || event.event === "done") {
      state.finished = true;
      state.forecast = event.forecast || [];
      state.forecastDiagnostics = event.forecast_diagnostics || {};
      renderForecast(state.forecast, state.forecastDiagnostics);
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
    rememberFailure({ event: "socket_error", error: "WebSocket 连接失败" }, question);
    setError("WebSocket 连接失败，请检查后端是否启动。");
    appendMessage("WebSocket 连接失败，请检查后端是否启动。", "assistant", retryControls());
  });

  socket.addEventListener("close", () => {
    if (!state.finished && !state.failed) {
      rememberFailure({ event: "socket_closed", error: "流式连接提前关闭" }, question);
      setError("流式连接提前关闭，请检查后端日志。");
      appendMessage("流式连接提前关闭，请检查后端日志。", "assistant", retryControls());
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
    appendMessage(`数据初始化失败：${detail}`, "assistant", retryControls());
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
