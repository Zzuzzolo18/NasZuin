import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Activity, HardDrive, Cpu, Thermometer, Clock, Database, RefreshCw, Loader2, CheckCircle2, XCircle, Archive } from "lucide-react"
import { Button } from "@/components/ui/button"
import { apiRequest } from "@/lib/api"

export default function Dashboard() {
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [scanStatus, setScanStatus] = useState(null) // null | 'queued' | 'running' | 'completed' | 'failed'
    const [scanMessage, setScanMessage] = useState('')
    const [moveStatus, setMoveStatus] = useState(null)
    const [moveMessage, setMoveMessage] = useState('')
    const pollRef = useRef(null)
    const movePollRef = useRef(null)

    const fetchStats = async () => {
        try {
            const response = await fetch('/monitor/api/stats/')
            if (!response.ok) throw new Error('Failed to fetch stats')
            const data = await response.json()
            setStats(data)
            setError(null)
        } catch (err) {
            console.error(err)
            setError('Could not load system stats')
        } finally {
            setLoading(false)
        }
    }

    // Poll scan task status with timeout protection
    const pollTaskStatus = (scanTaskId) => {
        sessionStorage.setItem('activeScanTaskId', scanTaskId)
        const MAX_POLL_DURATION = 10 * 60 * 1000 // 10 minutes max
        const POLL_INTERVAL = 5000 // 5 seconds between polls
        const MAX_ERRORS = 5
        const startTime = Date.now()
        let errorCount = 0

        const checkStatus = async () => {
            // Safety: stop after max duration
            if (Date.now() - startTime > MAX_POLL_DURATION) {
                setScanStatus('failed')
                setScanMessage('⏰ Scan timed out (no response in 10 minutes). Check server logs.')
                sessionStorage.removeItem('activeScanTaskId')
                return
            }

            try {
                const scanRes = await apiRequest(`/api/files/scan/status/?task_id=${scanTaskId}`)
                errorCount = 0 // Reset on success
                
                if (scanRes.status === 'SUCCESS') {
                    setScanStatus('completed')
                    setScanMessage(`✅ ${scanRes.result}`)
                    fetchStats()
                    sessionStorage.removeItem('activeScanTaskId')
                    return // Stop polling
                } else if (scanRes.status === 'FAILURE') {
                    setScanStatus('failed')
                    setScanMessage(`❌ Scan failed: ${scanRes.error || 'Unknown error'}`)
                    sessionStorage.removeItem('activeScanTaskId')
                    return // Stop polling
                } else {
                    setScanStatus('running')
                    const elapsed = Math.round((Date.now() - startTime) / 1000)
                    setScanMessage(`Scanning files... (${scanRes.status}, ${elapsed}s elapsed)`)
                }
            } catch (e) {
                errorCount++
                console.error('Status poll error:', e)
                if (errorCount >= MAX_ERRORS) {
                    setScanStatus('failed')
                    setScanMessage(`❌ Lost connection to server after ${MAX_ERRORS} errors`)
                    sessionStorage.removeItem('activeScanTaskId')
                    return // Stop polling
                }
            }
            
            // Schedule next poll only after current one completes
            pollRef.current = setTimeout(checkStatus, POLL_INTERVAL)
        }
        
        // Start first check immediately
        checkStatus()
    }

    // Poll move task status (reuses same pattern as scan)
    const pollMoveStatus = (taskId) => {
        sessionStorage.setItem('activeMoveTaskId', taskId)
        const MAX_POLL_DURATION = 30 * 60 * 1000 // 30 minutes (archiving can take long)
        const POLL_INTERVAL = 5000
        const MAX_ERRORS = 5
        const startTime = Date.now()
        let errorCount = 0

        const checkStatus = async () => {
            if (Date.now() - startTime > MAX_POLL_DURATION) {
                setMoveStatus('failed')
                setMoveMessage('⏰ Archive timed out (30 minutes). Check server logs.')
                sessionStorage.removeItem('activeMoveTaskId')
                return
            }
            try {
                const res = await apiRequest(`/api/files/scan/status/?task_id=${taskId}`)
                errorCount = 0
                if (res.status === 'SUCCESS') {
                    setMoveStatus('completed')
                    setMoveMessage(`✅ ${res.result}`)
                    fetchStats()
                    sessionStorage.removeItem('activeMoveTaskId')
                    return
                } else if (res.status === 'FAILURE') {
                    setMoveStatus('failed')
                    setMoveMessage(`❌ Archive failed: ${res.error || 'Unknown error'}`)
                    sessionStorage.removeItem('activeMoveTaskId')
                    return
                } else {
                    setMoveStatus('running')
                    const elapsed = Math.round((Date.now() - startTime) / 1000)
                    setMoveMessage(`Archiving files... (${res.status}, ${elapsed}s elapsed)`)
                }
            } catch (e) {
                errorCount++
                if (errorCount >= MAX_ERRORS) {
                    setMoveStatus('failed')
                    setMoveMessage(`❌ Lost connection to server`)
                    sessionStorage.removeItem('activeMoveTaskId')
                    return
                }
            }
            movePollRef.current = setTimeout(checkStatus, POLL_INTERVAL)
        }
        checkStatus()
    }

    // Single useEffect for stats polling + resume active tasks
    useEffect(() => {
        fetchStats()

        // Resume polling if there were active tasks before page refresh
        const savedScanId = sessionStorage.getItem('activeScanTaskId')
        if (savedScanId) {
            setScanStatus('running')
            setScanMessage('Resuming scan status...')
            pollTaskStatus(savedScanId)
        }
        const savedMoveId = sessionStorage.getItem('activeMoveTaskId')
        if (savedMoveId) {
            setMoveStatus('running')
            setMoveMessage('Resuming archive status...')
            pollMoveStatus(savedMoveId)
        }

        const pollingInterval = import.meta.env.VITE_MONITOR_POLLING_INTERVAL
            ? parseInt(import.meta.env.VITE_MONITOR_POLLING_INTERVAL)
            : 15000

        const interval = setInterval(fetchStats, pollingInterval)
        return () => {
            clearInterval(interval)
            if (pollRef.current) clearTimeout(pollRef.current)
            if (movePollRef.current) clearTimeout(movePollRef.current)
        }
    }, [])

    if (loading && !stats) return <div className="p-8">Loading dashboard...</div>
    if (error && !stats) return <div className="p-8 text-red-500">{error}</div>

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
                <div className="flex items-center gap-2">
                    <div className="text-sm text-muted-foreground mr-2">
                        Last updated: {new Date().toLocaleTimeString()}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => fetchStats()}
                    >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh
                    </Button>
                    <Button
                        variant="default"
                        size="sm"
                        disabled={scanStatus === 'queued' || scanStatus === 'running'}
                        onClick={async () => {
                            try {
                                setScanStatus('queued')
                                setScanMessage('Queuing scan task...')
                                const data = await apiRequest('/api/files/scan/')
                                
                                if (data.status === 'queued' && data.scan_task_id) {
                                    // Async mode — start polling
                                    setScanMessage(data.message)
                                    pollTaskStatus(data.scan_task_id)
                                } else if (data.status === 'completed') {
                                    // Synchronous fallback completed
                                    setScanStatus('completed')
                                    setScanMessage(`✅ ${data.message}${data.warning ? ` (⚠️ ${data.warning})` : ''}`)
                                    fetchStats()
                                    setTimeout(() => { setScanStatus(null); setScanMessage('') }, 10000)
                                } else {
                                    setScanStatus('completed')
                                    setScanMessage(data.message || 'Done')
                                    setTimeout(() => { setScanStatus(null); setScanMessage('') }, 10000)
                                }
                            } catch (e) {
                                setScanStatus('failed')
                                setScanMessage(`❌ ${e.message || 'Error triggering scan'}`)
                            }
                        }}
                    >
                        {(scanStatus === 'queued' || scanStatus === 'running') ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Database className="h-4 w-4 mr-2" />
                        )}
                        {scanStatus === 'running' ? 'Scanning...' : 'Scan Files'}
                    </Button>
                    <Button
                        variant="secondary"
                        size="sm"
                        disabled={moveStatus === 'queued' || moveStatus === 'running' || scanStatus === 'running'}
                        onClick={async () => {
                            if (!confirm('This will encrypt and move ALL files to cold storage (HDD). Continue?')) return
                            try {
                                setMoveStatus('queued')
                                setMoveMessage('Queuing archive task...')
                                const data = await apiRequest('/api/files/move/')
                                
                                if (data.status === 'queued' && data.task_id) {
                                    setMoveMessage(data.message)
                                    pollMoveStatus(data.task_id)
                                } else if (data.status === 'completed') {
                                    setMoveStatus('completed')
                                    setMoveMessage(`✅ ${data.message}`)
                                    fetchStats()
                                    setTimeout(() => { setMoveStatus(null); setMoveMessage('') }, 10000)
                                }
                            } catch (e) {
                                setMoveStatus('failed')
                                setMoveMessage(`❌ ${e.message || 'Error triggering archive'}`)
                            }
                        }}
                    >
                        {(moveStatus === 'queued' || moveStatus === 'running') ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Archive className="h-4 w-4 mr-2" />
                        )}
                        {moveStatus === 'running' ? 'Archiving...' : 'Force Archive'}
                    </Button>
                </div>
            </div>

            {/* Scan Status Banner */}
            {scanMessage && (
                <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                    scanStatus === 'failed' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
                    scanStatus === 'completed' ? 'bg-green-500/10 text-green-500 border border-green-500/20' :
                    'bg-blue-500/10 text-blue-500 border border-blue-500/20'
                }`}>
                    {scanStatus === 'failed' && <XCircle className="h-4 w-4 flex-shrink-0" />}
                    {scanStatus === 'completed' && <CheckCircle2 className="h-4 w-4 flex-shrink-0" />}
                    {(scanStatus === 'queued' || scanStatus === 'running') && <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin" />}
                    <span className="flex-1">{scanMessage}</span>
                    {(scanStatus === 'failed' || scanStatus === 'completed') && (
                        <button 
                            onClick={() => { setScanStatus(null); setScanMessage('') }}
                            className="text-xs opacity-60 hover:opacity-100 transition-opacity"
                        >
                            Dismiss
                        </button>
                    )}
                </div>
            )}

            {/* Archive Status Banner */}
            {moveMessage && (
                <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                    moveStatus === 'failed' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
                    moveStatus === 'completed' ? 'bg-green-500/10 text-green-500 border border-green-500/20' :
                    'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                }`}>
                    {moveStatus === 'failed' && <XCircle className="h-4 w-4 flex-shrink-0" />}
                    {moveStatus === 'completed' && <CheckCircle2 className="h-4 w-4 flex-shrink-0" />}
                    {(moveStatus === 'queued' || moveStatus === 'running') && <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin" />}
                    <span className="flex-1">{moveMessage}</span>
                    {(moveStatus === 'failed' || moveStatus === 'completed') && (
                        <button 
                            onClick={() => { setMoveStatus(null); setMoveMessage('') }}
                            className="text-xs opacity-60 hover:opacity-100 transition-opacity"
                        >
                            Dismiss
                        </button>
                    )}
                </div>
            )}

            {/* Status Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
                        <Cpu className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.cpu}%</div>
                        <p className="text-xs text-muted-foreground">System Load</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Memory</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {stats?.memory ? Math.round(stats.memory.used / 1024 / 1024 / 1024 * 100) / 100 : 0} GB
                        </div>
                        <p className="text-xs text-muted-foreground">
                            of {stats?.memory ? Math.round(stats.memory.total / 1024 / 1024 / 1024 * 100) / 100 : 0} GB ({stats?.memory?.percent}%)
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Temperature</CardTitle>
                        <Thermometer className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {stats?.temperature ? `${Math.round(stats.temperature)}°C` : 'N/A'}
                        </div>
                        <p className="text-xs text-muted-foreground">CPU / System</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">System Info</CardTitle>
                        <HardDrive className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-xl font-bold truncate" title={stats?.system?.node}>
                            {stats?.system?.node || 'Unknown'}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {stats?.system?.system} {stats?.system?.release}
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Content Sections */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>System Details</CardTitle>
                        <CardDescription>Uptime and configuration.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="flex items-center">
                                <Clock className="mr-2 h-4 w-4 opacity-70" />
                                <span className="font-semibold mr-2">Uptime:</span>
                                <span>{stats?.system?.uptime}</span>
                            </div>
                            <div className="flex items-center">
                                <Cpu className="mr-2 h-4 w-4 opacity-70" />
                                <span className="font-semibold mr-2">Processor:</span>
                                <span className="truncate">{stats?.system?.processor}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Disk Details Table */}
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Storage Partitions</CardTitle>
                        <CardDescription>Hot (SSD) and Cold (HDD) tiers.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-6">
                            {/* Tiers Section */}
                            <div>
                                <h4 className="mb-2 text-sm font-semibold tracking-tight text-muted-foreground">Storage Tiers</h4>
                                <div className="space-y-4">
                                    {stats?.disk?.filter(d => d.tier_type !== 'OTHER').length > 0 ? (
                                        stats?.disk?.filter(d => d.tier_type !== 'OTHER').map((d, i) => (
                                            <div key={i} className="flex flex-col space-y-1 border-b pb-2 last:border-0 hover:bg-muted/50 p-2 rounded transition-colors">
                                                <div className="flex justify-between items-center">
                                                    <div className="flex items-center gap-2">
                                                        {d.tier_type === 'HOT' ? (
                                                            <Activity className="h-4 w-4 text-orange-500" />
                                                        ) : (
                                                            <HardDrive className="h-4 w-4 text-blue-500" />
                                                        )}
                                                        <span className="font-medium text-sm">
                                                            {d.tier_name}
                                                            {d.tier_type === 'HOT' && <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-500/10 text-orange-600">SSD</span>}
                                                            {d.tier_type === 'COLD' && <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600">HDD</span>}
                                                        </span>
                                                    </div>
                                                    <span className={`text-xs px-2 py-0.5 rounded-full ${d.percent > 90 ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'}`}>
                                                        {d.percent}%
                                                    </span>
                                                </div>
                                                <div className="flex justify-between text-xs text-muted-foreground pl-6">
                                                    <span>{d.mountpoint} ({d.device})</span>
                                                    <span>{Math.round(d.free / 1024 / 1024 / 1024)} GB free</span>
                                                </div>
                                                <div className="w-full bg-secondary h-1.5 rounded overflow-hidden mt-1">
                                                    <div
                                                        className={`h-full rounded ${d.percent > 90 ? 'bg-red-500' : (d.tier_type === 'HOT' ? 'bg-orange-500' : 'bg-blue-500')}`}
                                                        style={{ width: `${d.percent}%` }}
                                                    ></div>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-xs text-muted-foreground italic p-2">No configured storage tiers found.</div>
                                    )}
                                </div>
                            </div>

                            {/* Other Partitions Section */}
                            <div>
                                <h4 className="mb-2 text-sm font-semibold tracking-tight text-muted-foreground">System & Other</h4>
                                <div className="space-y-4">
                                    {stats?.disk?.filter(d => d.tier_type === 'OTHER').map((d, i) => (
                                        <div key={i} className="flex flex-col space-y-1 border-b pb-2 last:border-0 hover:bg-muted/50 p-2 rounded">
                                            <div className="flex justify-between items-center">
                                                <div className="flex items-center gap-2">
                                                    <Database className="h-3 w-3 text-muted-foreground" />
                                                    <span className="font-medium text-sm">{d.device}</span>
                                                </div>
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${d.percent > 90 ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'}`}>
                                                    {d.percent}%
                                                </span>
                                            </div>
                                            <div className="flex justify-between text-xs text-muted-foreground pl-5">
                                                <span>{d.mountpoint}</span>
                                                <span>{Math.round(d.free / 1024 / 1024 / 1024)} GB free</span>
                                            </div>
                                            <div className="w-full bg-secondary h-1.5 rounded overflow-hidden">
                                                <div
                                                    className={`h-full rounded ${d.percent > 90 ? 'bg-red-500' : 'bg-muted-foreground'}`}
                                                    style={{ width: `${d.percent}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
