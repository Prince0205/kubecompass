// Sidebar dropdown toggles
function toggleDropdown(name) {
  const el = document.getElementById('drop-' + name)
  if (!el) return
  el.classList.toggle('hidden')
}

// Initialize persisted open state if needed
document.addEventListener('DOMContentLoaded', ()=>{
  // no-op for now, leave dropdowns closed by default
})

