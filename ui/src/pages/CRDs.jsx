import React, { useEffect, useState } from 'react'
import { crdAPI } from '../api'

export default function CRDs({ namespace }){
  const [crds, setCrds] = useState(null)
  useEffect(()=>{
    crdAPI.listCRDs()
      .then(r=>setCrds(r.data?.crds || []))
      .catch(()=>setCrds([]))
  },[namespace])

  if(crds===null) return <div>Loading CRDs…</div>
  if(!crds.length) return <div>No CRDs found or cluster not connected.</div>

  return (
    <div>
      <h3>Custom Resource Definitions</h3>
      <ul>
        {crds.map(c=> (
          <li key={c.name}>{c.name} — {c.group}</li>
        ))}
      </ul>
    </div>
  )
}
