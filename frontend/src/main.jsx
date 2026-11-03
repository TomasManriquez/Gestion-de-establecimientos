import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { registerSW } from 'virtual:pwa-register'
import { toast } from 'sonner'
import './index.css'

const updateSW = registerSW({
  onNeedRefresh() {
    toast('Hay una versión nueva de la aplicación', {
      duration: Infinity,
      action: { label: 'Actualizar', onClick: () => updateSW(true) },
    })
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
