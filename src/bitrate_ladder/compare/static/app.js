const state = {
  session: null,
  prepared: null,
  videos: [],
  syncTimer: null,
  overlay: null,
};

const elements = {
  sessionStatus: document.getElementById("session-status"),
  repairPanel: document.getElementById("repair-panel"),
  repairFields: document.getElementById("repair-fields"),
  applyRepairs: document.getElementById("apply-repairs"),
  modeInputs: Array.from(document.querySelectorAll("input[name='mode']")),
  selectors: [1, 2, 3, 4].map((idx) => document.getElementById(`asset-${idx}`)),
  prepare: document.getElementById("prepare"),
  clearCache: document.getElementById("clear-cache"),
  playPause: document.getElementById("play-pause"),
  stepBack: document.getElementById("step-back"),
  stepForward: document.getElementById("step-forward"),
  speed: document.getElementById("speed"),
  seek: document.getElementById("seek"),
  wipeWrap: document.getElementById("wipe-wrap"),
  wipeBase: document.getElementById("wipe-base"),
  wipeOverlay: document.getElementById("wipe-overlay"),
  wipeSlider: document.getElementById("wipe-slider"),
  tileWrap: document.getElementById("tile-wrap"),
  vmafChart: document.getElementById("vmaf-chart"),
  vmafCaption: document.getElementById("vmaf-caption"),
};

init().catch((error) => {
  elements.sessionStatus.innerHTML = `<p class="warning">${escapeHtml(error.message)}</p>`;
});

async function init() {
  bindEvents();
  await refreshSession();
  updateModeUI();
}

function bindEvents() {
  elements.modeInputs.forEach((input) => {
    input.addEventListener("change", () => updateModeUI());
  });
  elements.prepare.addEventListener("click", () => prepareComparison());
  elements.applyRepairs.addEventListener("click", () => applyRepairs());
  elements.clearCache.addEventListener("click", () => clearCache());
  elements.playPause.addEventListener("click", () => togglePlayPause());
  elements.stepBack.addEventListener("click", () => stepFrame(-1));
  elements.stepForward.addEventListener("click", () => stepFrame(1));
  elements.speed.addEventListener("change", () => {
    const rate = Number(elements.speed.value);
    state.videos.forEach((video) => {
      video.playbackRate = rate;
    });
  });
  elements.seek.addEventListener("input", () => {
    const master = getMasterVideo();
    if (!master || !Number.isFinite(master.duration) || master.duration <= 0) {
      return;
    }
    const targetSeconds = (Number(elements.seek.value) / 1000) * master.duration;
    state.videos.forEach((video) => {
      video.currentTime = Math.min(Math.max(targetSeconds, 0), video.duration || targetSeconds);
    });
    drawOverlay();
  });

  elements.wipeSlider.addEventListener("input", () => {
    const value = Number(elements.wipeSlider.value);
    elements.wipeOverlay.style.clipPath = `inset(0 ${100 - value}% 0 0)`;
  });

  document.addEventListener("keydown", (event) => {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
    if (tag === "input" || tag === "select" || tag === "textarea") {
      return;
    }
    if (event.code === "Space") {
      event.preventDefault();
      togglePlayPause();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      seekBySeconds(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      seekBySeconds(1);
    } else if (event.key === ",") {
      event.preventDefault();
      stepFrame(-1);
    } else if (event.key === ".") {
      event.preventDefault();
      stepFrame(1);
    } else if (event.key === "1") {
      setMode("wipe");
    } else if (event.key === "2") {
      setMode("tile");
    }
  });
}

async function refreshSession() {
  const response = await fetch("/api/session");
  if (!response.ok) {
    throw new Error(`Failed to load session (${response.status})`);
  }
  state.session = await response.json();
  renderSessionStatus();
  renderRepairPanel();
  populateSelectors();
}

function renderSessionStatus() {
  const issueCount = state.session.issues.length;
  const issueText = issueCount
    ? `<span class="warning">${issueCount} issue(s) must be repaired before compare.</span>`
    : "Session ready.";
  elements.sessionStatus.innerHTML = `
    <h2>Session</h2>
    <p>${issueText}</p>
    <p><strong>Report:</strong> ${escapeHtml(state.session.report_path)}</p>
    <p><strong>Source:</strong> ${escapeHtml(state.session.source_path || "(missing)")}</p>
  `;
}

function renderRepairPanel() {
  const issues = state.session.issues;
  if (!issues.length) {
    elements.repairPanel.classList.add("hidden");
    elements.repairFields.innerHTML = "";
    return;
  }
  elements.repairPanel.classList.remove("hidden");

  const rows = [];
  const seen = new Set();
  issues.forEach((issue) => {
    const key = `${issue.code}:${issue.point_id || "source"}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);

    if (issue.code === "missing_source") {
      rows.push(renderRepairField("source_path", "Source path"));
      return;
    }

    if (!issue.point_id) {
      return;
    }
    if (issue.code === "missing_encode") {
      rows.push(
        renderRepairField(
          `encode:${issue.point_id}`,
          `Encode path (${issue.point_id})`,
        ),
      );
    } else if (issue.code === "missing_vmaf") {
      rows.push(
        renderRepairField(
          `vmaf:${issue.point_id}`,
          `VMAF log path (${issue.point_id})`,
        ),
      );
    }
  });

  elements.repairFields.innerHTML = rows.join("");
}

function renderRepairField(id, label) {
  return `
    <div class="repair-field">
      <label for="repair-${id}">${escapeHtml(label)}</label>
      <input id="repair-${id}" data-repair-id="${escapeHtml(id)}" type="text" />
    </div>
  `;
}

async function applyRepairs() {
  const payload = {
    source_path: null,
    encode_paths: {},
    vmaf_paths: {},
  };

  const inputs = Array.from(elements.repairFields.querySelectorAll("input[data-repair-id]"));
  inputs.forEach((input) => {
    const key = input.dataset.repairId;
    const value = input.value.trim();
    if (!key || !value) {
      return;
    }
    if (key === "source_path") {
      payload.source_path = value;
      return;
    }
    const [kind, pointId] = key.split(":");
    if (kind === "encode") {
      payload.encode_paths[pointId] = value;
    } else if (kind === "vmaf") {
      payload.vmaf_paths[pointId] = value;
    }
  });

  const response = await fetch("/api/session/repair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Repair failed: ${detail}`);
  }
  state.session = await response.json();
  renderSessionStatus();
  renderRepairPanel();
  populateSelectors();
}

async function clearCache() {
  const response = await fetch("/api/cache/clear", { method: "POST" });
  if (!response.ok) {
    throw new Error("Unable to clear cache");
  }
}

function populateSelectors() {
  const options = [{ label: "Source", value: "source" }].concat(
    state.session.points.map((point) => ({
      label: `${point.id} - ${point.codec} ${point.width}x${point.height} @ ${point.bitrate_kbps}kbps`,
      value: `point:${point.id}`,
    })),
  );

  elements.selectors.forEach((select, idx) => {
    select.innerHTML = "";
    options.forEach((option) => {
      const node = document.createElement("option");
      node.value = option.value;
      node.textContent = option.label;
      select.appendChild(node);
    });
    if (idx >= 2) {
      const emptyNode = document.createElement("option");
      emptyNode.value = "";
      emptyNode.textContent = "(unused)";
      select.insertBefore(emptyNode, select.firstChild);
      select.value = "";
    }
  });
}

function updateModeUI() {
  const mode = getMode();
  const isWipe = mode === "wipe";
  elements.selectors[2].disabled = isWipe;
  elements.selectors[3].disabled = isWipe;
}

function getMode() {
  return elements.modeInputs.find((input) => input.checked)?.value || "wipe";
}

function setMode(mode) {
  elements.modeInputs.forEach((input) => {
    input.checked = input.value === mode;
  });
  updateModeUI();
}

async function prepareComparison() {
  if (state.session.issues.length) {
    throw new Error("Resolve session issues before preparing compare assets.");
  }

  const mode = getMode();
  const assets = collectAssetRefs(mode);
  if (mode === "wipe" && assets.length !== 2) {
    throw new Error("Wipe mode requires exactly two assets.");
  }
  if (mode === "tile" && (assets.length < 2 || assets.length > 4)) {
    throw new Error("Tile mode requires 2 to 4 assets.");
  }

  const response = await fetch("/api/compare/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assets }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Prepare failed: ${body}`);
  }

  state.prepared = await response.json();
  await renderPrepared(mode);
  await loadOverlay();
}

function collectAssetRefs(mode) {
  const refs = [];
  const limit = mode === "wipe" ? 2 : 4;
  for (let index = 0; index < limit; index += 1) {
    const value = elements.selectors[index].value;
    if (!value) {
      continue;
    }
    refs.push(parseAssetValue(value));
  }

  const unique = [];
  const seen = new Set();
  refs.forEach((ref) => {
    const key = `${ref.kind}:${ref.point_id || "source"}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(ref);
    }
  });
  return unique;
}

function parseAssetValue(value) {
  if (value === "source") {
    return { kind: "source" };
  }
  const [kind, pointId] = value.split(":");
  if (kind !== "point" || !pointId) {
    return { kind: "source" };
  }
  return { kind: "point", point_id: pointId };
}

async function renderPrepared(mode) {
  teardownPlayers();
  if (mode === "wipe") {
    elements.wipeWrap.classList.remove("hidden");
    elements.tileWrap.classList.add("hidden");

    const first = state.prepared.assets[0];
    const second = state.prepared.assets[1];
    await attachVideo(elements.wipeBase, first.media_url);
    await attachVideo(elements.wipeOverlay, second.media_url);
    state.videos = [elements.wipeBase, elements.wipeOverlay];
  } else {
    elements.tileWrap.classList.remove("hidden");
    elements.wipeWrap.classList.add("hidden");
    elements.tileWrap.innerHTML = "";

    state.videos = [];
    for (const item of state.prepared.assets) {
      const container = document.createElement("div");
      container.className = "tile-item";
      const video = document.createElement("video");
      video.playsInline = true;
      video.muted = true;
      await attachVideo(video, item.media_url);

      const label = document.createElement("p");
      label.textContent = formatAssetLabel(item.source);
      container.appendChild(video);
      container.appendChild(label);
      elements.tileWrap.appendChild(container);
      state.videos.push(video);
    }
  }

  state.videos.forEach((video) => {
    video.playbackRate = Number(elements.speed.value);
    video.addEventListener("timeupdate", updateSeekFromMaster);
    video.addEventListener("play", startSyncLoop);
    video.addEventListener("pause", stopSyncLoopIfPaused);
  });
  updateSeekFromMaster();
}

function teardownPlayers() {
  stopSyncLoop();
  state.videos.forEach((video) => {
    video.pause();
    video.removeAttribute("src");
    video.load();
  });
  state.videos = [];
  elements.tileWrap.innerHTML = "";
}

function attachVideo(video, src) {
  return new Promise((resolve, reject) => {
    const onLoaded = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("Failed to load prepared video"));
    };
    const cleanup = () => {
      video.removeEventListener("loadedmetadata", onLoaded);
      video.removeEventListener("error", onError);
    };
    video.addEventListener("loadedmetadata", onLoaded);
    video.addEventListener("error", onError);
    video.src = src;
    video.load();
  });
}

function togglePlayPause() {
  if (!state.videos.length) {
    return;
  }
  const anyPaused = state.videos.some((video) => video.paused);
  if (anyPaused) {
    state.videos.forEach((video) => {
      video.play();
    });
    elements.playPause.textContent = "Pause";
    startSyncLoop();
  } else {
    state.videos.forEach((video) => {
      video.pause();
    });
    elements.playPause.textContent = "Play";
    stopSyncLoop();
  }
}

function seekBySeconds(delta) {
  const master = getMasterVideo();
  if (!master || !Number.isFinite(master.duration)) {
    return;
  }
  const target = Math.max(0, Math.min(master.currentTime + delta, master.duration));
  state.videos.forEach((video) => {
    video.currentTime = target;
  });
  updateSeekFromMaster();
}

function stepFrame(direction) {
  if (!state.videos.length) {
    return;
  }
  const fps = parseFps(state.prepared?.evaluation_fps || state.session?.evaluation_fps || "30");
  const delta = direction * (1 / fps);
  seekBySeconds(delta);
}

function getMasterVideo() {
  return state.videos[0] || null;
}

function updateSeekFromMaster() {
  const master = getMasterVideo();
  if (!master || !Number.isFinite(master.duration) || master.duration <= 0) {
    elements.seek.value = "0";
    drawOverlay();
    return;
  }
  const ratio = master.currentTime / master.duration;
  elements.seek.value = String(Math.max(0, Math.min(1000, Math.round(ratio * 1000))));
  drawOverlay();
}

function startSyncLoop() {
  if (state.syncTimer || state.videos.length < 2) {
    return;
  }
  state.syncTimer = window.setInterval(() => {
    const master = getMasterVideo();
    if (!master || master.paused) {
      return;
    }
    state.videos.slice(1).forEach((video) => {
      const drift = Math.abs(video.currentTime - master.currentTime);
      if (drift > 0.04) {
        video.currentTime = master.currentTime;
      }
    });
    drawOverlay();
  }, 120);
}

function stopSyncLoopIfPaused() {
  if (state.videos.every((video) => video.paused)) {
    stopSyncLoop();
    elements.playPause.textContent = "Play";
  }
}

function stopSyncLoop() {
  if (state.syncTimer) {
    window.clearInterval(state.syncTimer);
    state.syncTimer = null;
  }
}

async function loadOverlay() {
  const sources = state.prepared.assets.slice(0, 2).map((asset) => asset.source);
  const pointIds = sources
    .map((source) => (source.kind === "point" ? source.point_id : null))
    .filter(Boolean);

  if (!pointIds.length) {
    state.overlay = null;
    elements.vmafCaption.textContent = "No report-point VMAF series available for selected assets.";
    drawOverlay();
    return;
  }

  const results = [];
  for (const pointId of pointIds) {
    const response = await fetch(`/api/vmaf/${pointId}`);
    if (!response.ok) {
      continue;
    }
    results.push(await response.json());
  }

  if (!results.length) {
    state.overlay = null;
    elements.vmafCaption.textContent = "Could not load frame-level VMAF logs for selected points.";
    drawOverlay();
    return;
  }

  state.overlay = {
    left: results[0] || null,
    right: results[1] || null,
  };

  if (state.overlay.left && state.overlay.right) {
    elements.vmafCaption.textContent =
      "Showing VMAF A/B curves and delta (A - B) for current comparison.";
  } else {
    elements.vmafCaption.textContent =
      "Showing VMAF curve for the selected report-point asset; delta unavailable.";
  }
  drawOverlay();
}

function drawOverlay() {
  const canvas = elements.vmafChart;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  const width = canvas.width;
  const height = canvas.height;
  const padding = 24;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#d0d8df";
  ctx.strokeRect(padding, padding, width - padding * 2, height - padding * 2);

  if (!state.overlay || !state.overlay.left) {
    ctx.fillStyle = "#7a8794";
    ctx.fillText("No overlay data", padding + 8, padding + 20);
    return;
  }

  const leftSeries = state.overlay.left.series || [];
  const rightSeries = state.overlay.right?.series || [];
  const maxTime = Math.max(
    leftSeries[leftSeries.length - 1]?.time_seconds || 0,
    rightSeries[rightSeries.length - 1]?.time_seconds || 0,
    1,
  );

  drawSeries(ctx, leftSeries, "#d13c5a", maxTime, width, height, padding, (point) => point.vmaf);

  if (rightSeries.length) {
    drawSeries(ctx, rightSeries, "#1e77c8", maxTime, width, height, padding, (point) => point.vmaf);
    const deltaLen = Math.min(leftSeries.length, rightSeries.length);
    const deltaSeries = Array.from({ length: deltaLen }, (_, idx) => ({
      time_seconds: leftSeries[idx].time_seconds,
      vmaf: leftSeries[idx].vmaf - rightSeries[idx].vmaf + 50,
    }));
    drawSeries(ctx, deltaSeries, "#0a7f51", maxTime, width, height, padding, (point) => point.vmaf);
  }

  const master = getMasterVideo();
  if (master && Number.isFinite(master.currentTime) && Number.isFinite(master.duration) && master.duration > 0) {
    const t = master.currentTime;
    const x = padding + (t / maxTime) * (width - padding * 2);
    ctx.strokeStyle = "#202a33";
    ctx.beginPath();
    ctx.moveTo(x, padding);
    ctx.lineTo(x, height - padding);
    ctx.stroke();
  }
}

function drawSeries(ctx, series, color, maxTime, width, height, padding, valueFn) {
  if (!series.length) {
    return;
  }
  const spanX = width - padding * 2;
  const spanY = height - padding * 2;

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  series.forEach((point, index) => {
    const time = point.time_seconds || 0;
    const value = Math.max(0, Math.min(100, valueFn(point)));
    const x = padding + (time / maxTime) * spanX;
    const y = padding + (1 - value / 100) * spanY;
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
}

function formatAssetLabel(source) {
  if (source.kind === "source") {
    return "Source";
  }
  return `Point ${source.point_id}`;
}

function parseFps(value) {
  if (!value.includes("/")) {
    return Math.max(Number(value) || 30, 1);
  }
  const [numRaw, denRaw] = value.split("/");
  const num = Number(numRaw);
  const den = Number(denRaw);
  if (!num || !den) {
    return 30;
  }
  return Math.max(num / den, 1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
