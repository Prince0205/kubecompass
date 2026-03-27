async function loadDeployments() {
  const tbody = document.getElementById("deployments-body")
  const res = await fetch("/api/resources/deployments")

  if (!res.ok) {
    tbody.innerHTML = `<tr><td colspan="3">Select namespace</td></tr>`
    return
  }

  const deployments = await res.json()
  tbody.innerHTML = ""

  deployments.forEach(d => {
    tbody.innerHTML += `
      <tr class="clickable-row" onclick="openDeployment('${d.name}')">
        <td class="link">${d.name}</td>
        <td>${d.replicas}</td>
        <td>${d.ready}</td>
      </tr>
    `
  })
}

document.addEventListener("DOMContentLoaded", loadDeployments)

async function openDeployment(name) {
  const res = await fetch(`/api/resources/deployments/${name}`)
  const d = await res.json()

  const percent = d.replicas
    ? Math.round((d.ready / d.replicas) * 100)
    : 0

  let html = `
    <!-- Summary -->
    <div class="overlay-card">
      <h3>${d.name}</h3>

      <span class="badge ${d.rollout_status.toLowerCase()}">
        ${d.rollout_status}
      </span>

      <div class="overlay-kv">
        <div><strong>Desired</strong></div><div>${d.replicas}</div>
        <div><strong>Ready</strong></div><div>${d.ready}</div>
        <div><strong>Updated</strong></div><div>${d.updated}</div>
      </div>

      <div class="progress-bar">
        <div class="progress-fill" style="width:${percent}%">
          ${percent}%
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="overlay-tabs">
      <button onclick="showDeploymentDetails()">Details</button>
      <button onclick="showDeploymentPods()">Pods</button>
      <button onclick="showDeploymentYaml()">YAML</button>
    </div>

    <div id="deployment-tab-content"></div>
  `

  openOverlay(`Deployment: ${name}`, html)

  window._deploymentData = d
  showDeploymentDetails()
}

function showDeploymentDetails() {
  const d = window._deploymentData

  document.getElementById("deployment-tab-content").innerHTML = `
    <div class="overlay-card">
    <h4>Containers</h4>

    <table class="k8s-table compact">
        <thead>
            <tr>
                <th>NAME</th>
                <th>IMAGE</th>
            </tr>
        </thead>
        <tbody>
            ${d.containers.map(c => `
            <tr>
                <td>${c.name}</td>
                <td class="mono">${c.image}</td>
            </tr>
            `).join("")}
        </tbody>
    </table>
    </div>


    ${window.USER_ROLE !== "view" ? `
      <div class="overlay-card overlay-actions">
        <div class="overlay-form-row">
          <label>Scale Replicas</label>
          <div class="overlay-action-row">
            <input id="scaleInput" type="number" min="0" value="${d.replicas}">
            <button onclick="scaleDeployment('${d.name}')">Scale</button>
            <button class="danger" onclick="restartDeployment('${d.name}')">
              Restart
            </button>
          </div>
        </div>
      </div>
    ` : ""}
  `
}

function showDeploymentPods() {
  const pods = window._deploymentData.pods

  document.getElementById("deployment-tab-content").innerHTML = `
    <div class="overlay-card">
      <table class="k8s-table">
        <thead>
          <tr>
            <th>NAME</th>
            <th>STATUS</th>
            <th>NODE</th>
          </tr>
        </thead>
        <tbody>
          ${pods.map(p => `
            <tr class="clickable-row"
                onclick="openPodDetails('${p.name}')">
              <td class="link">${p.name}</td>
              <td>${p.status}</td>
              <td>${p.node || "-"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `
}

async function applyDeploymentYaml(name) {
  const yaml = document.getElementById("yamlEditor").value

  const res = await fetch(`/api/resources/deployments/${name}/yaml`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yaml })
  })

  if (!res.ok) {
    alert("Failed to apply YAML")
    return
  }

  alert("Deployment updated")
  closeOverlay()
  loadDeployments()
}

async function showDeploymentYaml() {
  const d = window._deploymentData

  const res = await fetch(`/api/resources/deployments/${d.name}/yaml`)
  if (!res.ok) {
    alert("Failed to load YAML")
    return
  }

  const data = await res.json()

  document.getElementById("deployment-tab-content").innerHTML = `
    <div class="overlay-card">
      <h4>Deployment YAML</h4>

      <textarea
        id="yamlEditor"
        class="yaml-editor"
        spellcheck="false"
      >${data.yaml}</textarea>

      ${window.USER_ROLE !== "view" ? `
        <div class="overlay-actions">
          <button onclick="applyDeploymentYaml('${d.name}')">
            Apply
          </button>
        </div>
      ` : ""}
    </div>
  `
}

async function scaleDeployment(name) {
  const replicas = parseInt(document.getElementById("scaleInput").value)
  await fetch(`/api/resources/deployments/${name}/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ replicas })
  })
  closeOverlay()
  loadDeployments()
}

async function restartDeployment(name) {
  if (!confirm("Restart deployment?")) return
  await fetch(`/api/resources/deployments/${name}/restart`, {
    method: "POST"
  })
  closeOverlay()
}