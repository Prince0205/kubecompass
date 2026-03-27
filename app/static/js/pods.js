async function loadPods() {
  const tbody = document.getElementById("pods-body")
  const res = await fetch("/api/resources/pods")

  if (!res.ok) {
    tbody.innerHTML = `<tr><td colspan="4">Select namespace</td></tr>`
    return
  }

  const pods = await res.json()
  tbody.innerHTML = ""

  pods.forEach(p => {
    tbody.innerHTML += `
      <tr class="clickable-row" onclick="openPodDetails('${p.name}')">
        <td class="pod-name">${p.name}</td>
        <td>${p.status}</td>
        <td>${p.node}</td>
        <td>${p.restarts}</td>
      </tr>
    `
  })
}

document.addEventListener("DOMContentLoaded", loadPods)

async function openPodDetails(podName) {
  const res = await fetch(`/api/resources/pods/${podName}`)
  const pod = await res.json()

  let html = `
    <div class="overlay-section">
      <h3>${pod.name}</h3>
      <p><strong>Status:</strong> ${pod.status}</p>
      <p><strong>Node:</strong> ${pod.node}</p>
      <p><strong>Restarts:</strong> ${pod.restarts}</p>
    </div>

    <div class="overlay-tabs">
      <button onclick="loadPodEvents('${podName}')">Events</button>
      <button onclick="loadPodLogs('${podName}')">Logs</button>
      <button onclick="openYamlEditor('pods','${pod.name}')">
        View YAML
      </button>

    </div>

    <div id="pod-tab-content"></div>
  `

  if (window.USER_ROLE !== "view") {
    html += `
      <div class="overlay-section overlay-actions">
        <button class="btn-danger"
          onclick="deletePod('${podName}')">
          Restart Pod
        </button>
      </div>
    `
  }

  openOverlay(`Pod: ${pod.name}`, html)
}


async function loadPodEvents(podName) {
  const res = await fetch(`/api/resources/pods/${podName}/events`)
  const events = await res.json()

  document.getElementById("pod-tab-content").innerHTML = `
    <div class="overlay-section">
      <ul>
        ${events.map(e => `
          <li>
            <strong>${e.type}</strong>
            <span>${e.reason}</span><br>
            ${e.message}
          </li>
        `).join("")}
      </ul>
    </div>
  `
}

async function loadPodLogs(podName) {
  const res = await fetch(`/api/resources/pods/${podName}`)
  const pod = await res.json()

  document.getElementById("pod-tab-content").innerHTML = `
    <div class="overlay-section">
      <label>Container</label>
      <select id="logContainer">
        ${pod.containers.map(c => `<option>${c}</option>`)}
      </select>

      <button onclick="fetchLogs('${podName}')">
        Load Logs
      </button>

      <pre id="log-output" class="log-box">
Select a container to view logs
      </pre>
    </div>
  `
}

async function fetchLogs(podName) {
  const container = document.getElementById("logContainer").value
  const res = await fetch(
    `/api/resources/pods/${podName}/logs?container=${container}&tail=200`
  )
  const data = await res.json()

  document.getElementById("log-output").innerText = data.logs
}

async function deletePod(podName) {
  if (!confirm("Restart this pod?")) return

  await fetch(`/api/resources/pods/${podName}`, {
    method: "DELETE"
  })

  closeOverlay()
  loadPods() // 🔥 refresh list
}