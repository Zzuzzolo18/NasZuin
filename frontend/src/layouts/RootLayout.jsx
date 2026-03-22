import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import { LayoutDashboard, FolderOpen, Settings as SettingsIcon, HardDrive, Menu, LogOut, Shield, Moon, Sun, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useState, useEffect } from "react"
import { apiRequest } from "@/lib/api"

function useDarkMode() {
    const [isDark, setIsDark] = useState(() => {
        const saved = localStorage.getItem('theme')
        if (saved) return saved === 'dark'
        return window.matchMedia('(prefers-color-scheme: dark)').matches
    })

    useEffect(() => {
        document.documentElement.classList.toggle('dark', isDark)
        localStorage.setItem('theme', isDark ? 'dark' : 'light')
    }, [isDark])

    return [isDark, () => setIsDark(prev => !prev)]
}

export default function RootLayout() {
    const location = useLocation()
    const navigate = useNavigate()
    const [isSidebarOpen, setIsSidebarOpen] = useState(false)
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)
    const [isDark, toggleDark] = useDarkMode()

    useEffect(() => {
        checkAuth()
    }, [])

    // Close sidebar on navigation (mobile)
    useEffect(() => {
        setIsSidebarOpen(false)
    }, [location.pathname])

    const checkAuth = async () => {
        try {
            const data = await apiRequest('/api/auth/check/')
            setUser(data)
            if (!data.is_staff && location.pathname === '/') {
                navigate('/files')
            }
        } catch (error) {
            navigate('/login')
        } finally {
            setLoading(false)
        }
    }

    const handleLogout = async () => {
        try {
            await apiRequest('/api/auth/logout/', { method: 'POST' })
            navigate('/login')
        } catch (error) {
            console.error("Logout failed", error)
        }
    }

    const navItems = [
        ...(user?.is_staff ? [{ href: "/", icon: LayoutDashboard, label: "Dashboard" }] : []),
        { href: "/files", icon: FolderOpen, label: "File Manager" },
        { href: "/settings", icon: SettingsIcon, label: "Impostazioni" },
    ]

    if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>

    return (
        <div className="min-h-screen bg-background flex">
            {/* Mobile sidebar backdrop */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 lg:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={cn(
                    "fixed inset-y-0 left-0 z-50 w-64 bg-card border-r transition-transform duration-300 ease-in-out text-card-foreground flex flex-col",
                    "lg:translate-x-0 lg:static lg:inset-auto",
                    isSidebarOpen ? "translate-x-0" : "-translate-x-full"
                )}
            >
                <div className="h-14 flex items-center justify-between px-4 border-b shrink-0">
                    <div className="flex items-center gap-2 font-bold text-xl">
                        <HardDrive className="h-6 w-6 text-primary" />
                        <span>HomeNAS</span>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(false)} className="lg:hidden">
                        <X className="h-5 w-5" />
                    </Button>
                </div>

                <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
                    {navItems.map((item) => {
                        const isActive = location.pathname === item.href
                        const Icon = item.icon
                        return (
                            <Link
                                key={item.href}
                                to={item.href}
                                className={cn(
                                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-primary text-primary-foreground"
                                        : "hover:bg-accent hover:text-accent-foreground"
                                )}
                            >
                                <Icon className="h-5 w-5" />
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}

                    {user?.is_staff && (
                        <a
                            href="/admin/"
                            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground text-amber-600"
                        >
                            <Shield className="h-5 w-5" />
                            <span>Admin Panel</span>
                        </a>
                    )}
                </nav>

                <div className="p-2 border-t mt-auto">
                    <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/20"
                    >
                        <LogOut className="h-5 w-5" />
                        <span>Logout</span>
                    </button>
                    {user && (
                        <div className="mt-2 px-3 text-xs text-muted-foreground">
                            Logged in as {user.username}
                        </div>
                    )}
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <header className="h-14 border-b bg-card/50 backdrop-blur px-6 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
                            <Menu className="h-5 w-5" />
                        </Button>
                        <h1 className="font-semibold text-lg">
                            {navItems.find(i => i.href === location.pathname)?.label || "HomeNAS"}
                        </h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="icon" onClick={toggleDark} title={isDark ? "Light mode" : "Dark mode"}>
                            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </Button>
                        <div className="h-2 w-2 rounded-full bg-green-500"></div>
                        <span className="text-sm text-muted-foreground hidden sm:inline">Online</span>
                    </div>
                </header>
                <div className="flex-1 overflow-hidden p-6 flex flex-col">
                    <Outlet />
                </div>
            </main>
        </div>
    )
}
