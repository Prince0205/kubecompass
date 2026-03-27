async function loadReplicaSets() {
  const tbody = document.getElementById("replicasets-body")

  const res = await fetch("/api/resources/replicasets")
  if (!res.ok) {
    tbody.innerHTML = `<tr><td colspan="5">Select cluster & namespace</td></tr>`
    return
  }

  const sets = await res.json()
  tbody.innerHTML = ""

  sets.forEach(rs => {
    tbody.innerHTML += `
      <tr class="clickable-row"
          onclick="openReplicaSet('${rs.name}')">
        <td class="link">${rs.name}</td>
        <td>${rs.desired}</td>
        <td>${rs.ready}</td>
        <td>${rs.available}</td>
        <td>${rs.owner || "-"}</td>
      </tr>
    `
  })
}

document.addEventListener("DOMContentLoaded", loadReplicaSets)


// ---------- Overlay ----------
async function openReplicaSet(name) {
  const res = await fetch(`/api/resources/replicasets/${name}`)
  if (!res.ok) {
    alert("Failed to load ReplicaSet")
    return
  }

  const rs = await res.json()
  window._replicaSetData = rs

  const percent = rs.replicas.desired
    ? Math.round((rs.replicas.ready / rs.replicas.desired) * 100)
    : 0

  const html = `
    <div class="overlay-card">
      <h3>${rs.name}</h3>

      <div class="overlay-kv">
        <div><strong>Desired</strong></div><div>${rs.replicas.desired}</div>
        <div><strong>Ready</strong></div><div>${rs.replicas.ready}</div>
        <div><strong>Available</strong></div><div>${rs.replicas.available}</div>
      </div>

      <div class="progress-bar">
        <div class="progress-fill" style="width:${percent}%">
          ${percent}%
        </div>
      </div>
    </div>

    <div class="overlay-card">
      <h4>Images</h4>
      ${rs.images.map(img => `
        <div class="mono">${img}</div>
      `).join("")}
    </div>

    <div class="overlay-card">
      <h4>Selector</h4>
      <pre class="mono">${JSON.stringify(rs.selector, null, 2)}</pre>
    </div>

    <div class="overlay-tabs">
      <button onclick="showReplicaSetPods()">Pods</button>
    </div>

    <div id="rs-tab-content"></div>
  `

  openOverlay(`ReplicaSet: ${rs.name}`, html)
  showReplicaSetPods()
}

function showReplicaSetPods() {
  const pods = window._replicaSetData.pods

  document.getElementById("rs-tab-content").innerHTML = `
    <div class="overlay-card">
      <table class="k8s-table">
        <thead>
          <tr>
            <th>NAME</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          ${pods.map(p => `
            <tr class="clickable-row"
                onclick="openPodDetails('${p.name}')">
              <td class="link">${p.name}</td>
              <td>${p.status}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `
}