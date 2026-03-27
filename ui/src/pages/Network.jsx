import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function Network({ namespace }){
  const [data, setData] = useState(null)
  useEffect(()=>{
    const url = namespace ? `/v1/network?namespace=${encodeURIComponent(namespace)}` : '/v1/network'
    axios.get(url)
      .then(r=>setData(r.data))
      .catch(()=>setData({services:[],ingresses:[],networkpolicies:[]}))
  },[namespace])

  if(data===null) return <div>Loading network resources…</div>

  return (
    <div>
      <h3>Network</h3>
      <div style={{display:'flex',gap:12}}>
        <div style={{flex:1}}>
          <h4>Services</h4>
          <ul>{data.services.map(s=> <li key={s.metadata?.name}>{s.metadata?.name} ({s.spec?.type})</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>Ingresses</h4>
          <ul>{data.ingresses.map(i=> <li key={i.metadata?.name}>{i.metadata?.name}</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>NetworkPolicies</h4>
          <ul>{data.networkpolicies.map(n=> <li key={n.metadata?.name}>{n.metadata?.name}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}
