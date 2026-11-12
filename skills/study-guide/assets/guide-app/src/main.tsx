import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// 深浅色由顶栏按钮切 <html data-theme>（index.html 里的脚本），这里不用管
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
