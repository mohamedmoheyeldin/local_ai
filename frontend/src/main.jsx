import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BaseStyles, ThemeProvider } from '@primer/react'
import '@primer/primitives/dist/css/primitives.css'
import '@primer/primitives/dist/css/functional/themes/light.css'
import '@primer/primitives/dist/css/functional/themes/dark.css'
import '@primer/css/dist/markdown.css'
import App from './App.jsx'
import './app.css'

function Root() {
  const [colorMode, setColorModeState] = useState(() => localStorage.getItem('local-ai-color-mode') || 'auto')
  const setColorMode = mode => {
    localStorage.setItem('local-ai-color-mode', mode)
    setColorModeState(mode)
  }
  return <ThemeProvider colorMode={colorMode} dayScheme="light" nightScheme="dark">
    <BaseStyles><App colorMode={colorMode} setColorMode={setColorMode} /></BaseStyles>
  </ThemeProvider>
}

createRoot(document.getElementById('root')).render(
  <StrictMode><Root /></StrictMode>,
)
