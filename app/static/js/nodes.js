async function loadNodes() {
  const tbody = document.getElementById("nodes-body")

  const res = await fetch("/api/resources/nodes")
  if (!res.ok) {
    tbody.innerHTML = `
      <tr><td colspan="5">Select a cluster</td></tr>
    `
    return
  }

  const nodes = await res.json()
  tbody.innerHTML = ""

  nodes.forEach(n => {
    tbody.innerHTML += `
      <tr class="clickable-row" onclick="openNodeDetails('${n.name}')">
        <td class="node-name">${n.name}</td>
        <td style="color:${n.status === "Ready" ? "green" : "red"}">
          ${n.status}
        </td>
        <td>${n.role}</td>
        <td>${n.age}</td>
        <td>${n.version}</td>
      </tr>
    `
  })
}

document.addEventListener("DOMContentLoaded", loadNodes)

async function openNodeDetails(nodeName) {
  const res = await fetch(`/api/resources/nodes/${nodeName}`)
  const data = await res.json()

  let html = `
    <div class="overlay-section">
      <h3>${data.name}</h3>
      <p>
        <strong>Schedulable:</strong>
        <span class="badge ${data.unschedulable ? "badge-red" : "badge-green"}">
          ${data.unschedulable ? "No" : "Yes"}
        </span>
      </p>
    </div>

    <div class="overlay-section">
      <h4>Conditions</h4>
      <ul>
        ${data.conditions.map(c =>
          `<li>${c.type}: 
            <span class="badge ${c.status === "True" ? "badge-green" : "badge-red"}">
              ${c.status}
            </span>
          </li>`
        ).join("")}
      </ul>
    </div>

    <div class="overlay-section">
      <h4>Capacity</h4>
      <ul>
        ${Object.entries(data.capacity)
          .map(([k,v]) => `<li>${k}: ${v}</li>`)
          .join("")}
      </ul>
    </div>

    <div class="overlay-section">
      <h4>Allocatable</h4>
      <ul>
        ${Object.entries(data.allocatable)
          .map(([k,v]) => `<li>${k}: ${v}</li>`)
          .join("")}
      </ul>
    </div>

    <div class="overlay-section">
      <h4>Taints</h4>
      <p>${data.taints.length ? data.taints.join("<br>") : "None"}</p>
    </div>
  `

  if (window.USER_ROLE === "admin") {
    html += `
      <div class="overlay-section overlay-actions">
        <button class="btn-warning" onclick="cordonNode('${nodeName}')">
          Cordon
        </button>
        <button class="btn-warning" onclick="uncordonNode('${nodeName}')">
          Uncordon
        </button>
        <button class="btn-danger" onclick="drainNode('${nodeName}')">
          Drain
        </button>
      </div>
    `
  }

  openOverlay(`Node: ${nodeName}`, html)
}

async function cordonNode(node) {
  await fetch(`/api/resources/nodes/${node}/cordon`, { method: "POST" })
  alert("Node cordoned")
  await loadNodes()      // 🔥 refresh table
  closeOverlay()         // 🔥 close details
}

async function uncordonNode(node) {
  await fetch(`/api/resources/nodes/${node}/uncordon`, { method: "POST" })
  alert("Node uncordoned")
  await loadNodes()
  closeOverlay()
}

async function drainNode(node) {
  if (!confirm("Drain node? This will evict pods.")) return
  await fetch(`/api/resources/nodes/${node}/drain`, { method: "POST" })
  alert("Drain initiated")
  await loadNodes()
  closeOverlay()
}