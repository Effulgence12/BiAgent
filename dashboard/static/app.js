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
  whatif: document.querySelector("#whatif-block"),
  forecast: document.querySelector("#forecast-json"),
};

const downloadJsonButton = document.querySelector("#download-json");
const pipelineEl = document.querySelector("#pipeline");

// 最近一次分析的原始事件流，供"下载事件JSON"按钮使用（不再实时渲染巨型 JSON，避免切标签卡顿）。
let latestEvents = [];

// 纯色描边图标（继承 currentColor，无 emoji）。
const SVG = {
  orchestrator:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polygon points="16 8 14 14 8 16 10 10"/></svg>',
  data_analyst:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>',
  forecast_model:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg>',
  visualizer:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="20" x2="6" y2="12"/><line x1="12" y1="20" x2="12" y2="5"/><line x1="18" y1="20" x2="18" y2="14"/></svg>',
  whatif_model:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6l-5 8.5A2 2 0 0 0 6.7 21h10.6a2 2 0 0 0 1.7-3.5L14 9V3"/><line x1="7.5" y1="15" x2="16.5" y2="15"/></svg>',
  decision_maker:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 18h5"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V18h6v-1.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></svg>',
  check:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  close:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>',
};

// 总览页流水线步进器：节点 key 与后端 agent 事件一一对应。
const PIPELINE = [
  { key: "orchestrator", label: "协调器" },
  { key: "data_analyst", label: "数据分析" },
  { key: "forecast_model", label: "预测" },
  { key: "visualizer", label: "可视化" },
  { key: "whatif_model", label: "反事实" },
  { key: "decision_maker", label: "决策" },
];

function buildPipeline() {
  const parts = [];
  PIPELINE.forEach((step, index) => {
    if (index > 0) parts.push(`<div class="pipeline-connector" data-index="${index}"></div>`);
    parts.push(
      `<div class="pipeline-node pending" data-key="${step.key}"><div class="pipeline-dot">${SVG[step.key]}</div><span class="pipeline-label">${step.label}</span></div>`,
    );
  });
  pipelineEl.innerHTML = parts.join("");
}

function resetPipeline() {
  pipelineEl.querySelectorAll(".pipeline-node").forEach((node) => {
    node.className = "pipeline-node pending";
    const dot = node.querySelector(".pipeline-dot");
    if (dot) dot.innerHTML = SVG[node.dataset.key] || "";
  });
  pipelineEl.querySelectorAll(".pipeline-connector").forEach((connector) => {
    connector.className = "pipeline-connector";
  });
}

function setPipelineNode(key, status) {
  const mapped = key === "orchestrator_refine" ? "orchestrator" : key;
  const node = pipelineEl.querySelector(`.pipeline-node[data-key="${mapped}"]`);
  if (!node) return;
  node.classList.remove("pending", "active", "done", "error", "skipped");
  node.classList.add(status);
  const dot = node.querySelector(".pipeline-dot");
  if (dot) dot.innerHTML = status === "done" ? SVG.check : SVG[mapped] || "";
  const index = PIPELINE.findIndex((step) => step.key === mapped);
  if (index > 0 && (status === "active" || status === "done")) {
    const connector = pipelineEl.querySelector(`.pipeline-connector[data-index="${index}"]`);
    if (connector) connector.classList.add("filled");
  }
}

function markPipelineError() {
  pipelineEl.querySelectorAll(".pipeline-node.active").forEach((node) => {
    node.classList.remove("active");
    node.classList.add("error");
  });
}

function finalizePipeline() {
  pipelineEl.querySelectorAll(".pipeline-node").forEach((node) => {
    if (node.classList.contains("active")) setPipelineNode(node.dataset.key, "done");
    else if (node.classList.contains("pending")) node.classList.replace("pending", "skipped");
  });
}

// 各 Agent 启动时的进度文案：让"等待大模型"阶段显式"在动"，而不是停在静态提示上像卡死。
const AGENT_PROGRESS = {
  orchestrator: "协调器规划中…",
  data_analyst: "数据分析 Agent 查询中…",
  forecast_model: "预测 Agent 计算中…",
  whatif_model: "What-if 反事实模拟中…",
  visualizer: "可视化 Agent 生成图表中…",
  decision_maker: "决策 Agent 生成建议中…",
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
  panels.whatif.innerHTML = "";
  panels.forecast.innerHTML = "";
  resetPipeline();
  activeChart = null;
  downloadChartButton.disabled = true;
  downloadImageButton.disabled = true;
  downloadJsonButton.disabled = true;
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
  if (event.event === "plan" && event.chart_requirements !== undefined) {
    return {
      intent: event.intent || "-",
      analysis_type: event.analysis_type || "-",
      metrics: event.metrics || [],
      dimensions: event.dimensions || [],
      filters: event.filters || {},
      chart_requirements: event.chart_requirements || [],
      required_agents: event.required_agents || [],
      required_views: event.required_views || [],
      followup_reference: event.followup_reference || "-",
      confidence: event.confidence ?? "-",
      reasoning_summary: event.reasoning_summary || "-",
      refined: Boolean(event.refined),
    };
  }
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
    whatif: "完成 What-if 反事实模拟",
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

function renderWhatif(whatif) {
  if (!whatif) {
    panels.whatif.innerHTML = "";
    return;
  }
  if (whatif.error) {
    panels.whatif.innerHTML = `<h3>What-if 反事实模拟</h3><p class="muted">模拟未生成：${escapeHtml(whatif.error)}</p>`;
    return;
  }
  const unit = whatif.unit || "";
  const share = Number.isFinite(whatif.affected_share) ? `${(whatif.affected_share * 100).toFixed(1)}%` : "-";
  const rows = [
    ["场景", whatif.scenario_label],
    ["指标", whatif.metric_label],
    ["干预前", `${whatif.baseline} ${unit}`],
    ["干预后", `${whatif.scenario} ${unit}`],
    ["变化", `${whatif.delta > 0 ? "+" : ""}${whatif.delta} ${unit}（${whatif.direction}）`],
    ["影响范围", `${whatif.affected_count} 条 / ${share}`],
  ];
  const table = rows.map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`).join("");
  panels.whatif.innerHTML = `<h3>What-if 反事实模拟</h3><p>${escapeHtml(whatif.narrative)}</p><table class="data-table"><tbody>${table}</tbody></table>`;
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
  let watchdogTimer = null;
  let slowTicks = 0;
  const WATCHDOG_MS = 45000;
  // 让"下载事件JSON"始终指向本次运行的事件流（数组原地追加，引用保持有效）。
  latestEvents = state.events;

  function clearWatchdog() {
    if (watchdogTimer) {
      window.clearTimeout(watchdogTimer);
      watchdogTimer = null;
    }
  }

  function slowResendControls(currentQuestion) {
    const wrapper = document.createElement("div");
    wrapper.className = "retry-actions";
    const resend = document.createElement("button");
    resend.type = "button";
    resend.className = "secondary compact";
    resend.textContent = "重发当前问题";
    resend.addEventListener("click", () => {
      appendMessage(`重发：${currentQuestion}`, "user");
      resetResult("正在重新发起分析…");
      startStreamingAnalysis(currentQuestion);
    });
    wrapper.appendChild(resend);
    return wrapper;
  }

  // 看门狗：距上一条事件超过 WATCHDOG_MS 仍无新进展时给出非致命提示，避免"静默假死"。
  function armWatchdog() {
    clearWatchdog();
    if (state.finished || state.failed) return;
    watchdogTimer = window.setTimeout(() => {
      if (socket !== activeSocket || state.finished || state.failed) return;
      slowTicks += 1;
      const waited = Math.round((WATCHDOG_MS / 1000) * slowTicks);
      const stronger = slowTicks >= 2;
      setPill(connectionState, "响应较慢", "running");
      const hint = stronger
        ? `大模型已等待约 ${waited} 秒仍无响应，通常是网络/接口延迟而非系统故障。可点击下方重发当前问题，或改用命令行 python cli.py 兜底演示。`
        : `大模型响应较慢（已等待约 ${waited} 秒），通常是网络/接口延迟，可再稍候。`;
      panels.summary.innerHTML = "";
      panels.summary.append(document.createTextNode(hint), slowResendControls(question));
      armWatchdog();
    }, WATCHDOG_MS);
  }

  const socket = new WebSocket(wsUrl("/ws/analyze"));
  activeSocket = socket;

  socket.addEventListener("open", () => {
    setPill(connectionState, "流式连接", "running");
    socket.send(JSON.stringify({
      session_id: sessionId,
      question,
      retry_of: options.retryOf || "",
      error_context: options.errorContext || "",
    }));
    armWatchdog();
  });

  socket.addEventListener("message", (message) => {
    const event = JSON.parse(message.data);
    state.events.push(event);
    if (event.event !== "llm_delta") downloadJsonButton.disabled = false;
    if (event.event === "agent_start") setPipelineNode(event.agent, "active");
    else if (event.event === "agent_done") setPipelineNode(event.agent, "done");
    else if (event.event === "data_error" || event.event === "llm_error" || event.event === "sql_error") markPipelineError();
    renderAgentEvent(event);
    armWatchdog();

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

    if (event.event === "agent_start") {
      const label = AGENT_PROGRESS[event.agent] || `${event.agent} 处理中…`;
      setStage(label, "running");
      // 仅在还没有真实直答时用进度文案占位，避免覆盖后续生成的结论。
      if (!state.directAnswer) panels.directAnswer.textContent = label;
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

    if (event.event === "whatif") {
      state.whatif = event.whatif;
      renderWhatif(event.whatif);
      return;
    }

    if (event.event === "llm_delta") {
      appendAdviceDelta(state, event.content);
      return;
    }

    if (event.event === "data_error" || event.event === "llm_error" || event.event === "sql_error") {
      state.failed = true;
      clearWatchdog();
      rememberFailure(event, question);
      const label = event.event === "data_error" ? "数据错误" : event.event === "llm_error" ? "大模型错误" : "SQL规划/执行错误";
      setError(`${label}：${event.error}`);
      appendMessage(`${label}：${event.error}`, "assistant", retryControls());
      refreshConversations();
      return;
    }

    if (event.event === "final" || event.event === "done") {
      state.finished = true;
      clearWatchdog();
      state.forecast = event.forecast || [];
      state.forecastDiagnostics = event.forecast_diagnostics || {};
      if (event.whatif) {
        state.whatif = event.whatif;
        renderWhatif(event.whatif);
      }
      renderForecast(state.forecast, state.forecastDiagnostics);
      finalizePipeline();
      downloadJsonButton.disabled = false;
      setStage("完成", "done");
      setPill(connectionState, "就绪", "idle");
      stripPriorMeta();
      const answerText = state.directAnswer || state.summary || `已完成 ${state.analysisType || "BI"} 分析。`;
      appendMessage(
        answerText,
        "assistant",
        buildMetaNode({ analysisType: state.analysisType, matchedViews: state.matchedViews, elapsedMs: state.elapsedMs }),
      );
      refreshConversations();
    }
  });

  socket.addEventListener("error", () => {
    state.failed = true;
    clearWatchdog();
    rememberFailure({ event: "socket_error", error: "WebSocket 连接失败" }, question);
    setError("WebSocket 连接失败，请检查后端是否启动。");
    appendMessage("WebSocket 连接失败，请检查后端是否启动。", "assistant", retryControls());
  });

  socket.addEventListener("close", () => {
    clearWatchdog();
    if (!state.finished && !state.failed) {
      rememberFailure({ event: "socket_closed", error: "流式连接提前关闭" }, question);
      setError("流式连接提前关闭，请检查后端日志。");
      appendMessage("流式连接提前关闭，请检查后端日志。", "assistant", retryControls());
    }
  });
}

// ---------- 会话边栏：多对话新建/切换/删除 + 刷新后从后端回灌对话记录 ----------
const conversationList = document.querySelector("#conversation-list");
const newConversationButton = document.querySelector("#new-conversation");
const PLACEHOLDER_TEXT =
  "请输入一个 Olist 运营问题，例如：2017年各月GMV趋势？哪些州配送延迟严重？预测未来6期GMV。";

function renderPlaceholder() {
  messages.innerHTML = "";
  const node = document.createElement("article");
  node.className = "message assistant";
  node.textContent = PLACEHOLDER_TEXT;
  messages.appendChild(node);
}

function setMemoryCount(turns) {
  memoryCount.textContent = `记忆 ${turns} 轮`;
}

// 回答下方的数据元信息（命中表/类型/耗时），以药丸样式与正文区分；仅挂在最新一条回答上。
function buildMetaNode({ analysisType, matchedViews, elapsedMs }) {
  const items = [];
  if (analysisType) items.push(`类型 ${analysisType}`);
  items.push(`命中 ${matchedViews && matchedViews.length ? matchedViews.join("、") : "基础表"}`);
  if (elapsedMs !== "" && elapsedMs != null) items.push(`耗时 ${elapsedMs}ms`);
  const node = document.createElement("div");
  node.className = "message-meta";
  node.innerHTML = items.map((text) => `<span class="meta-chip">${escapeHtml(text)}</span>`).join("");
  return node;
}

// 新回答到来前，移除上一条回答的元信息 chip，保证"仅最新一条带数据"。
function stripPriorMeta() {
  messages.querySelectorAll(".message-meta").forEach((node) => node.remove());
}

function renderTranscript(turns) {
  messages.innerHTML = "";
  if (!turns || !turns.length) {
    renderPlaceholder();
    return;
  }
  let lastAnswerIndex = -1;
  turns.forEach((turn, index) => {
    if (!turn.failed && (turn.answer || turn.summary)) lastAnswerIndex = index;
  });
  turns.forEach((turn, index) => {
    if (turn.question) appendMessage(turn.question, "user");
    if (turn.failed) {
      appendMessage(`该问题上次执行失败：${turn.error || "未知错误"}`, "assistant");
    } else if (turn.answer || turn.summary) {
      const meta =
        index === lastAnswerIndex
          ? buildMetaNode({ analysisType: turn.analysis_type, matchedViews: turn.matched_views, elapsedMs: turn.elapsed_ms })
          : null;
      appendMessage(turn.answer || turn.summary, "assistant", meta);
    }
  });
}

function resetIdleResult() {
  panels.kpis.innerHTML = renderKpis({});
  panels.directAnswer.textContent = "等待分析请求...";
  panels.summary.textContent = "真实 SQL 查询完成后会展示数据摘要。";
  panels.chartList.innerHTML = "";
  panels.chartStage.textContent = "等待分析请求...";
  panels.chartTitle.textContent = "图表工作区";
  panels.chartSource.textContent = "等待可视化 Agent 输出。";
  panels.sql.textContent = "等待 SQL 规划...";
  panels.agent.innerHTML = "";
  panels.advice.textContent = "等待真实大模型流式输出...";
  panels.whatif.innerHTML = "";
  panels.forecast.innerHTML = "";
  resetPipeline();
  activeChart = null;
  latestEvents = [];
  downloadChartButton.disabled = true;
  downloadImageButton.disabled = true;
  downloadJsonButton.disabled = true;
  setStage("等待问题", "idle");
  activateTab("overview");
}

function renderConversationList(sessions) {
  const list = Array.isArray(sessions) ? sessions : [];
  const hasActive = list.some((item) => item.session_id === sessionId);
  // 当前会话若还没有任何落库轮次（刚新建），用占位草稿置顶展示。
  const items = hasActive ? list : [{ session_id: sessionId, title: "新对话", turn_count: 0 }, ...list];
  if (!items.length) {
    conversationList.innerHTML = `<p class="conversation-empty">暂无会话，发送问题即可开始。</p>`;
    return;
  }
  conversationList.innerHTML = "";
  items.forEach((item) => {
    const node = document.createElement("div");
    node.className = `conversation-item${item.session_id === sessionId ? " active" : ""}`;
    node.innerHTML = `<div class="conv-main"><span class="conv-title">${escapeHtml(item.title || "新对话")}</span><span class="conv-meta">${item.turn_count || 0} 轮 · ${escapeHtml(shortSession(item.session_id))}</span></div><button class="conv-delete" type="button" title="删除会话" aria-label="删除会话">${SVG.close}</button>`;
    node.querySelector(".conv-main").addEventListener("click", () => switchConversation(item.session_id));
    node.querySelector(".conv-delete").addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(item.session_id);
    });
    conversationList.appendChild(node);
  });
}

async function fetchSessions() {
  try {
    const response = await fetch("/api/sessions");
    if (response.ok) return (await response.json()).sessions || [];
  } catch (error) {
    /* 后端不可用时静默降级，仅展示当前草稿会话 */
  }
  return [];
}

async function refreshConversations() {
  renderConversationList(await fetchSessions());
}

async function loadActiveTranscript() {
  let turns = [];
  try {
    const response = await fetch(`/api/sessions/${sessionId}`);
    if (response.ok) turns = (await response.json()).turns || [];
  } catch (error) {
    /* ignore */
  }
  renderTranscript(turns);
  setMemoryCount(turns.length);
  resetIdleResult();
}

async function switchConversation(id) {
  if (id === sessionId) return;
  if (activeSocket && activeSocket.readyState === WebSocket.OPEN) activeSocket.close();
  sessionId = id;
  localStorage.setItem("olistAgenticBiSession", sessionId);
  sessionLabel.textContent = shortSession(sessionId);
  await loadActiveTranscript();
  await refreshConversations();
}

function newConversation() {
  if (activeSocket && activeSocket.readyState === WebSocket.OPEN) activeSocket.close();
  sessionId = crypto.randomUUID();
  localStorage.setItem("olistAgenticBiSession", sessionId);
  sessionLabel.textContent = shortSession(sessionId);
  renderPlaceholder();
  setMemoryCount(0);
  resetIdleResult();
  refreshConversations();
  input.focus();
}

async function deleteConversation(id) {
  try {
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
  } catch (error) {
    /* ignore */
  }
  if (id === sessionId) {
    const remaining = (await fetchSessions()).filter((item) => item.session_id !== id);
    if (remaining.length) {
      await switchConversation(remaining[0].session_id);
      return;
    }
    newConversation();
    return;
  }
  refreshConversations();
}

newConversationButton.addEventListener("click", newConversation);

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

downloadJsonButton.addEventListener("click", () => {
  if (!latestEvents.length) return;
  const blob = new Blob([JSON.stringify(latestEvents, null, 2)], { type: "application/json;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `olist-analysis-events-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.target));
});

buildPipeline();
panels.kpis.innerHTML = renderKpis({});

// 初始化：刷新后从后端回灌当前会话的对话记录，并加载会话列表，保证界面与后端记忆一致。
loadActiveTranscript();
refreshConversations();
