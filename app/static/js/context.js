async function loadContext() {
  const res = await fetch("/api/context");
  const ctx = await res.json();

  // --- Cluster Dropdown ---
  const clusterSelect = document.getElementById("clusterSelect");
  clusterSelect.innerHTML = `<option value="">Select Cluster</option>`;

  ctx.clusters.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    if (c.id === ctx.active_cluster) opt.selected = true;
    clusterSelect.appendChild(opt);
  });

  clusterSelect.onchange = async () => {
    await fetch("/api/context/cluster", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ cluster_id: clusterSelect.value })
    });
    location.reload();
  };

  // --- Namespace Dropdown ---
  const nsSelect = document.getElementById("namespaceSelect");
  nsSelect.innerHTML = `<option value="">Select Namespace</option>`;

  ctx.namespaces.forEach(ns => {
    const opt = document.createElement("option");
    opt.value = ns;
    opt.textContent = ns;
    if (ns === ctx.active_namespace) opt.selected = true;
    nsSelect.appendChild(opt);
  });

  nsSelect.onchange = async () => {
    await fetch("/api/context/namespace", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ namespace: nsSelect.value })
    });
    location.reload();
  };
}

document.addEventListener("DOMContentLoaded", loadContext);
