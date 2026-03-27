import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function RBAC({ namespace }){
  const [data, setData] = useState(null)
  useEffect(()=>{
    const url = namespace ? `/v1/rbac?namespace=${encodeURIComponent(namespace)}` : '/v1/rbac'
    axios.get(url)
      .then(r=>setData(r.data))
      .catch(()=>setData({roles:[],clusterroles:[],bindings:[]}))
  },[namespace])

  if(data===null) return <div>Loading RBAC resources…</div>

  return (
    <div>
      <h3>RBAC</h3>
      <div style={{display:'flex',gap:12}}>
        <div style={{flex:1}}>
          <h4>Roles</h4>
          <ul>{data.roles.map(r=> <li key={r.metadata?.name}>{r.metadata?.name} ({r.metadata?.namespace})</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>ClusterRoles</h4>
          <ul>{data.clusterroles.map(r=> <li key={r.metadata?.name}>{r.metadata?.name}</li>)}</ul>
        </div>
        <div style={{flex:1}}>
          <h4>RoleBindings</h4>
          <ul>{data.bindings.map(b=> <li key={b.metadata?.name}>{b.metadata?.name}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}
