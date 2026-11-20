let authToken = localStorage.getItem("pulserank_token") || "";
let currentAuditId = null;

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function showPortal(user) {
  document.getElementById("authSection").classList.add("hidden");
  document.getElementById("portalSection").classList.remove("hidden");
  document.getElementById("logoutBtn").classList.remove("hidden");
  document.getElementById("userLabel").textContent = `${user.full_name} (${user.plan_tier.toUpperCase()})`;
  loadPricingAndRoi();
  loadMonitors();
  loadSMO();
}

async function login() {
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("loginEmail").value,
        password: document.getElementById("loginPassword").value,
      }),
    });
    authToken = data.access_token;
    localStorage.setItem("pulserank_token", authToken);
    showPortal(data.user);
  } catch (e) {
    document.getElementById("authError").textContent = e.message;
  }
}

async function register() {
  try {
    const data = await api("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: document.getElementById("regName").value,
        email: document.getElementById("regEmail").value,
        password: document.getElementById("regPassword").value,
        gstin: document.getElementById("regGstin").value,
      }),
    });
    authToken = data.access_token;
    localStorage.setItem("pulserank_token", authToken);
    showPortal(data.user);
  } catch (e) {
    document.getElementById("authError").textContent = e.message;
  }
}

function logout() {
  authToken = "";
  localStorage.removeItem("pulserank_token");
  location.reload();
}

async function sendOnboarding() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;
  const box = document.getElementById("chatBox");
  box.innerHTML += `<div class="chat-msg user"><strong>You:</strong> ${msg}</div>`;
  input.value = "";
  const data = await api("/api/v1/onboarding/chat", {
    method: "POST",
    body: JSON.stringify({ message: msg }),
  });
  box.innerHTML += `<div class="chat-msg"><strong>Guide:</strong> ${data.reply}</div>`;
  box.scrollTop = box.scrollHeight;
}

async function submitAudit() {
  const url = document.getElementById("auditUrlInput").value.trim();
  if (!url) return;
  document.getElementById("auditStatusText").textContent = "Audit queued (202 Accepted)...";
  const res = await api("/api/v1/audits", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  currentAuditId = res.audit_id;
  pollAudit(currentAuditId);
}

async function pollAudit(id) {
  const data = await api(`/api/v1/audits/${id}`);
  if (data.status === "queued" || data.status === "running") {
    setTimeout(() => pollAudit(id), 700);
    return;
  }
  document.getElementById("auditStatusText").textContent = `Audit #${id} ${data.status}.`;
  renderAudit(data);
}

function renderAudit(data) {
  document.getElementById("scoreSummaryCard").classList.remove("hidden");
  document.getElementById("activeAuditUrl").textContent = data.url;
  document.getElementById("activeAuditMeta").textContent = `Audit #${data.id} • Status: ${data.status}`;
  document.getElementById("overallScoreVal").textContent = data.overall_score;
  document.getElementById("seoScoreVal").textContent = data.seo_score;
  document.getElementById("aeoScoreVal").textContent = data.aeo_score;

  const errs = data.critical_errors || [];
  document.getElementById("errorCountBadge").textContent = `${errs.length} issues`;
  document.getElementById("errorLogsBody").innerHTML = errs.length
    ? errs.map(e => `<p><span class="badge ${e.severity}">${e.severity.toUpperCase()}</span> <strong>${e.category}:</strong> ${e.message}</p>`).join("")
    : "<p>No critical errors found.</p>";

  if (data.optimizations && data.optimizations.length > 0) {
    const latest = data.optimizations[0];
    if (latest.status === "completed") {
      const onp = latest.onpage_output;
      const offp = latest.offpage_output;
      document.getElementById("onpageBody").innerHTML = `
        <p><strong>Optimized Title:</strong> ${onp.optimized_title}</p>
        <p><strong>Meta Description:</strong> ${onp.optimized_meta_description}</p>
        <p><strong>AEO Direct Answer:</strong> ${onp.aeo_direct_answer_block}</p>
        <pre>${JSON.stringify(onp.recommended_json_ld, null, 2)}</pre>
      `;
      document.getElementById("offpageBody").innerHTML = `
        <p><strong>Backlink Gap:</strong> ${offp.backlink_gap_summary}</p>
        <p><strong>Target Domains:</strong> ${(offp.target_referring_domains || []).join(", ")}</p>
        <pre>${offp.digital_pr_pitch_draft}</pre>
      `;
    }
  }
}

async function triggerOptimization() {
  if (!currentAuditId) return;
  await api(`/api/v1/audits/${currentAuditId}/optimize`, { method: "POST" });
  const check = async () => {
    const data = await api(`/api/v1/audits/${currentAuditId}`);
    if (data.optimizations?.[0]?.status === "completed") {
      renderAudit(data);
    } else {
      setTimeout(check, 600);
    }
  };
  setTimeout(check, 600);
}

async function addMonitor() {
  const url = document.getElementById("monitorUrl").value.trim();
  const monitor_type = document.getElementById("monitorType").value;
  if (!url) return;
  await api("/api/v1/monitors", { method: "POST", body: JSON.stringify({ url, monitor_type }) });
  loadMonitors();
}

async function loadMonitors() {
  const list = await api("/api/v1/monitors");
  document.getElementById("monitorsBody").innerHTML = list.length
    ? list.map(m => `<p><strong>[${m.monitor_type}]</strong> ${m.url} — Latest: <code>${JSON.stringify(m.latest)}</code></p>`).join("")
    : "No monitors configured yet.";
}

async function launchSMO() {
  const source_url = document.getElementById("smoUrl").value.trim();
  const topic = document.getElementById("smoTopic").value.trim();
  if (!source_url) return;
  await api("/api/v1/smo/campaigns", { method: "POST", body: JSON.stringify({ source_url, topic }) });
  setTimeout(loadSMO, 700);
}

async function loadSMO() {
  const list = await api("/api/v1/smo/campaigns");
  document.getElementById("smoBody").innerHTML = list.length
    ? list.map(c => `<p><strong>Campaign #${c.id}</strong> (${c.status}) — ${c.source_url} | Assets: ${c.platform_assets.length} | Community: ${c.community_engagements.length}</p>`).join("")
    : "No SMO campaigns yet.";
}

async function loadPricingAndRoi() {
  const plans = await api("/api/v1/billing/plans");
  document.getElementById("pricingGrid").innerHTML = plans.map(p => `
    <div class="card" style="margin:0;">
      <h4 style="margin:0 0 6px;">${p.name}</h4>
      <p style="margin:0; font-size:1.1rem; font-weight:700;">₹${p.base_inr.toLocaleString("en-IN")}/mo <span class="muted">+ 18% GST</span></p>
      <p class="muted">Total: ₹${p.total_inr.toLocaleString("en-IN")}/mo</p>
      <p class="muted">${p.outcome_rule}</p>
    </div>
  `).join("");
  const roi = await api("/api/v1/billing/roi-report");
  document.getElementById("roiBody").innerHTML = `<pre>${JSON.stringify(roi, null, 2)}</pre>`;
}

if (authToken) {
  api("/api/v1/auth/me").then(showPortal).catch(() => localStorage.removeItem("pulserank_token"));
}
