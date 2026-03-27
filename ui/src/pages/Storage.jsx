import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function Storage({ namespace }){
  const [data, setData] = useState(null)
  useEffect(()=>{
    const url = namespace ? `/v1/storage?namespace=${encodeURIComponent(namespace)}` : '/v1/storage'
    axios.get(url)
      .then(r=>setData(r.data))
      .catch(()=>setData({pv:[],pvc:[],sc:[]}))
  },[namespace])

  if(data===null) return <div>Loading storage resources…</div>

  return (
    <div>
      <h3>Storage</h3>
      <div style={{display:'flex',gap:12}}>
        <div style={{flex:1}}>
          <h4>PersistentVolumes</h4>
          <ul>{data.pv.map(p=> <li key={p.metadata?.name}>{p.metadata?.name}</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>PersistentVolumeClaims</h4>
          <ul>{data.pvc.map(p=> <li key={p.metadata?.name}>{p.metadata?.name} ({p.metadata?.namespace})</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>StorageClasses</h4>
          <ul>{data.sc.map(s=> <li key={s.metadata?.name}>{s.metadata?.name}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}
