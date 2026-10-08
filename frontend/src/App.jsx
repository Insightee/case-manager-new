import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Analytics } from '@vercel/analytics/react'
import { PathnameSanitizer } from './components/PathnameSanitizer.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { AppRoutes } from './routes/AppRoutes.jsx'
import { queryClient } from './lib/queryClient.js'
import { PwaStaleRecoveryListener } from './components/shared/PwaStaleRecoveryListener.jsx'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <PathnameSanitizer>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <PwaStaleRecoveryListener />
            <AppRoutes />
            <Analytics />
          </AuthProvider>
        </QueryClientProvider>
      </PathnameSanitizer>
    </BrowserRouter>
  )
}

export default App
