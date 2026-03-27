async function loadResource(kind) {
  const query = getContextQuery();
  const res = await fetch(`/api/resources/${kind}${query}`);

  if (!res.ok) {
    const msg = kind === "nodes"
      ? "Select a cluster to view nodes."
      : "Select cluster and namespace first.";

    document.querySelector(".content").innerHTML =
      `<p style="color:#b91c1c">${msg}</p>`;
    return;
  }

  const data = await res.json();

  if (!data.length) {
    document.querySelector(".content").innerHTML =
      `<p>No ${kind} found.</p>`;
    return;
  }

  renderTable(kind, data);
}

function renderTable(kind, data) {
  // simple search/filter box
  let html = `<div class="resource-header"><h2 class="resource-title">${kind.toUpperCase()}</h2>
              <input id="res-search" placeholder="Filter..." />
              </div>
              <table class="k8s-table">
              <thead><tr>`;

  const keys = Object.keys(data[0]);
  keys.forEach(k => {
    html += `<th>${k.toUpperCase()}</th>`;
  });
  html += `<th>ACTIONS</th>`;

  html += "</tr></thead><tbody>";

  const overlayKinds = new Set(['pv','pvc','storageclasses','roles','rolebindings','clusterroles','clusterrolebindings','serviceaccounts'])
  data.forEach(row => {
    html += "<tr>";
    keys.forEach(k => {
      let v = row[k];
      // Make the `name` cell clickable only for overlayKinds
      if ((k === 'name' || k === 'metadata') && (row.name || row.metadata?.name)) {
        const rn = row.name || row.metadata?.name
        if (overlayKinds.has(kind)) {
          v = `<span class="link" onclick="openResourceOverlay('${kind}','${rn}')">${rn}</span>`
        } else {
          v = rn
        }
        html += `<td>${v}</td>`
        return
      }
      html += `<td>${v === undefined || v === null ? '' : String(v)}</td>`;
    });
    // actions
    const name = row.name || row.metadata?.name || '';
    html += `<td><button class="btn-view" onclick="viewYaml('${kind}','${name}')">View YAML</button></td>`;
    html += "</tr>";
  });

  html += "</tbody></table>";

  document.querySelector(".content").innerHTML = html;

  // wire up search
  const input = document.getElementById('res-search')
  input.addEventListener('input', (e)=>{
    const q = e.target.value.toLowerCase()
    const rows = document.querySelectorAll('.k8s-table tbody tr')
    rows.forEach(r => {
      const text = r.innerText.toLowerCase()
      r.style.display = text.includes(q) ? '' : 'none'
    })
  })
}

function loadDetail(kind, name) {
  const query = getContextQuery();
  fetch(`/api/resources/${kind}/${name}/yaml${query}`)
    .then(r => r.json())
    .then(d => {
      const yamlText = d.yaml || ''
      const html = `<div><h3>${name}</h3>
        <textarea id="yaml-editor" style="width:100%;height:400px">${yamlText}</textarea>
        <div style="margin-top:8px">
          <button onclick="applyYaml('${kind}','${name}')">Apply</button>
        </div>
      </div>`
      openOverlay(`Edit ${kind} - ${name}`, html)
    })
}

// Open overlay for individual resources (storage & rbac types)
function openResourceOverlay(kind, name) {
  // reuse the YAML editor overlay helper (handles fetching and editor setup)
  if (typeof openYamlEditor === 'function') {
    openYamlEditor(kind, name)
    return
  }

  // Fallback: fetch raw YAML and open a simple overlay
  const clusterQuery = getContextQuery();
  fetch(`/api/resources/${kind}/${encodeURIComponent(name)}/yaml${clusterQuery}`)
    .then(r => r.json())
    .then(d => {
      const yamlText = d.yaml || ''
      const html = `<div style="padding:12px">
        <h3 class="mono">${name}</h3>
        <pre class="mono">${escapeHtml(yamlText)}</pre>
      </div>`
      openOverlay(`${kind} - ${name}`, html)
    }).catch(e=> {
      openOverlay('Error', `<div style="color:#b91c1c">${e.message}</div>`)
    })
}

function refreshOverlay(kind,name){
  openResourceOverlay(kind,name)
}

function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

function saveCM(name) {
  const data = JSON.parse(document.getElementById("editor").value)
  const clusterSelect = document.getElementById("clusterSelect")
  const nsSelect = document.getElementById("namespaceSelect")

  const payload = {
    data,
    cluster: clusterSelect ? clusterSelect.value : undefined,
    namespace: nsSelect ? nsSelect.value : undefined
  }

  fetch(`/api/resources/configmaps/${name}`, {
    method: "PATCH",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  })
}

function viewYaml(kind, name) {
  // Navigate to dedicated resource detail page
  const urlName = encodeURIComponent(name)
  window.location.href = `/resource/${kind}/${urlName}`
}

function applyYaml(kind, name) {
  const yamlText = document.getElementById('yaml-editor').value
  const query = getContextQuery()
  fetch(`/api/resources/${kind}/${name}/yaml${query}`, {
    method: 'PUT',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({yaml: yamlText})
  }).then(r => {
    if (!r.ok) return r.json().then(j => { alert('Apply failed: '+(j.detail||j)); })
    alert('Apply successful')
    closeOverlay()
  }).catch(e=> alert('Apply error: '+e.message))
}

function getContextQuery() {
  const clusterSelect = document.getElementById("clusterSelect")
  const nsSelect = document.getElementById("namespaceSelect")
  const params = new URLSearchParams()
  if (clusterSelect && clusterSelect.value) params.set("cluster", clusterSelect.value)
  if (nsSelect && nsSelect.value) params.set("namespace", nsSelect.value)
  const s = params.toString()
  return s ? `?${s}` : ""
}

async function loadContext() {
  const res = await fetch("/api/context")
  const ctx = await res.json()

  const clusterSelect = document.getElementById("clusterSelect")
  clusterSelect.innerHTML = "<option>Select Cluster</option>"

  ctx.clusters.forEach(c => {
    const opt = document.createElement("option")
    opt.value = c.id
    opt.textContent = c.name
    if (c.id === ctx.active_cluster) opt.selected = true
    clusterSelect.appendChild(opt)
  })

  clusterSelect.onchange = async () => {
    await fetch("/api/context/cluster", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({cluster_id: clusterSelect.value})
    })
    location.reload()
  }

  const nsSelect = document.getElementById("namespaceSelect")
  nsSelect.innerHTML = "<option>Select Namespace</option>"

  ctx.namespaces.forEach(ns => {
    const opt = document.createElement("option")
    opt.value = ns
    opt.textContent = ns
    if (ns === ctx.active_namespace) opt.selected = true
    nsSelect.appendChild(opt)
  })

  nsSelect.onchange = async () => {
    await fetch("/api/context/namespace", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({namespace: nsSelect.value})
    })
    location.reload()
  }
}

document.addEventListener("DOMContentLoaded", loadContext)