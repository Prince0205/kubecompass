import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function Editor(){
  const [yaml, setYaml] = useState('')
  const [cluster, setCluster] = useState(null)
  const [namespace, setNamespace] = useState('default')
  const [dryRun, setDryRun] = useState(true)
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    // subscribe to context changes (simple polling)
    const t = setInterval(async () => {
      try{
        const r = await axios.get('/v1/context')
        setCluster(r.data.cluster)
        setNamespace(r.data.namespace || 'default')
      }catch(e){/*ignore*/}
    }, 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if(!cluster) return
    axios.get(`/api/resources/deployments/harbor-core/yaml?cluster=${cluster._id}&namespace=${namespace}`)
      .then(r => setYaml(r.data))
      .catch(e => setYaml(`# error: ${e.message}`))
  }, [cluster, namespace])

  async function apply(){
    if(!cluster) return alert('Select cluster first')
    try{
      const r = await axios.put('/api/resources/deployments/apply', { yaml, cluster: cluster._id, namespace, dry_run: dryRun })
      setPreview(r.data)
      alert('Apply request sent')
    }catch(e){
      alert('Apply failed: '+(e.response?.data?.detail||e.message))
    }
  }

  return (
    <div>
      <h3>YAML Editor</h3>
      <div>
        <label>Namespace: <input value={namespace} onChange={e=>setNamespace(e.target.value)} /></label>
        <label style={{marginLeft:12}}><input type="checkbox" checked={dryRun} onChange={e=>setDryRun(e.target.checked)} /> Dry-run</label>
        <button onClick={apply} disabled={!cluster}>Apply</button>
      </div>
      <textarea value={yaml} onChange={e=>setYaml(e.target.value)} style={{width:'100%',height:400}} />
      {preview && <pre style={{background:'#eee',padding:8}}>{JSON.stringify(preview,null,2)}</pre>}
    </div>
  )
}
