import { BrowserRouter, Routes, Route, Link } from "react-router-dom"
import { Toaster } from "sonner"
import RootLayout from "./layouts/RootLayout"
import Dashboard from "./pages/Dashboard"
import FileManager from "./pages/FileManager"
import Settings from "./pages/Settings"
import Login from "./pages/Login"
import Register from "./pages/Register"

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
      <h2 className="text-6xl font-bold text-muted-foreground">404</h2>
      <p className="text-xl text-muted-foreground">Page not found</p>
      <Link to="/" className="text-primary hover:underline font-medium">
        ← Back to Dashboard
      </Link>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<RootLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="files" element={<FileManager />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  )
}

export default App
