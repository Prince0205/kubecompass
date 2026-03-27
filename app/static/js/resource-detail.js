document.addEventListener('DOMContentLoaded', ()=>{
  const path = window.location.pathname.split('/')
  // expected /resource/{kind}/{name}
  const kind = path[2]
  const name = decodeURIComponent(path[3])

  const editor = document.getElementById('yaml-editor')
  const applyBtn = document.getElementById('apply-btn')
  const refreshBtn = document.getElementById('refresh-btn')

  async function loadYaml(){
    const res = await fetch(`/api/resources/${kind}/${name}/yaml`)
    if(!res.ok){
      editor.value = `Error loading YAML: ${res.status}`
      return
    }
    const j = await res.json()
    editor.value = j.yaml || ''
  }

  applyBtn.addEventListener('click', async ()=>{
    const yamlText = editor.value
    const res = await fetch(`/api/resources/${kind}/${name}/yaml`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({yaml: yamlText})
    })
    if(!res.ok){
      const err = await res.json().catch(()=>({detail:'Unknown error'}))
      alert('Apply failed: '+(err.detail||JSON.stringify(err)))
    } else {
      alert('Apply successful')
      loadYaml()
    }
  })

  refreshBtn.addEventListener('click', loadYaml)

  loadYaml()
})
