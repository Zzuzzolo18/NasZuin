import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog"
import {
    Plus,
    Plug,
    Cpu,
    Router,
    Pencil,
    Check,
    X,
    Loader2,
    Power,
    PowerOff,
    RefreshCw,
    Trash2,
    ArrowLeft,
    ChevronRight,
} from "lucide-react"
import { apiRequest } from "@/lib/api"
import { toast } from "sonner"

// ─── Icon resolver ──────────────────────────────────────────────────────────────
const ICON_MAP = {
    plug: Plug,
    cpu: Cpu,
    router: Router,
}

function DeviceIcon({ icon, className }) {
    const Icon = ICON_MAP[icon] || Cpu
    return <Icon className={className} />
}

// ─── Inline style for fade-in keyframes (avoids tailwind config changes) ───────
const fadeInKeyframes = `
@keyframes deviceCardFadeIn {
    from {
        opacity: 0;
        transform: translateY(12px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
.device-card-fadein {
    animation: deviceCardFadeIn 0.5s ease-out both;
}
`

// ─── Main Component ─────────────────────────────────────────────────────────────
export default function Devices() {
    const [devices, setDevices] = useState([])
    const [deviceTypes, setDeviceTypes] = useState([])
    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState({}) // { [deviceId]: 'on'|'off'|'status' }
    const [editingId, setEditingId] = useState(null)
    const [editName, setEditName] = useState("")
    const [dialogOpen, setDialogOpen] = useState(false)
    const [dialogStep, setDialogStep] = useState(1)
    const [selectedType, setSelectedType] = useState(null)
    const [formData, setFormData] = useState({})
    const [saving, setSaving] = useState(false)

    const editInputRef = useRef(null)

    // ── Fetch devices and types ──────────────────────────────────────────────
    useEffect(() => {
        fetchDevices()
        fetchDeviceTypes()
    }, [])

    // Auto-focus the inline edit input when editing starts
    useEffect(() => {
        if (editingId !== null && editInputRef.current) {
            editInputRef.current.focus()
            editInputRef.current.select()
        }
    }, [editingId])

    const fetchDevices = async () => {
        try {
            const data = await apiRequest("/api/devices/")
            setDevices(data.devices || [])
        } catch (err) {
            toast.error("Errore nel caricamento dei dispositivi: " + err.message)
        } finally {
            setLoading(false)
        }
    }

    const fetchDeviceTypes = async () => {
        try {
            const data = await apiRequest("/api/devices/types/")
            setDeviceTypes(data.types || [])
        } catch (err) {
            console.error("Failed to fetch device types", err)
        }
    }

    // ── Device actions ───────────────────────────────────────────────────────
    const handleAction = async (deviceId, action) => {
        setActionLoading((prev) => ({ ...prev, [deviceId]: action }))
        try {
            const data = await apiRequest(`/api/devices/${deviceId}/action/`, {
                method: "POST",
                body: JSON.stringify({ action }),
            })
            // Update the device's online state based on the action performed
            if (action === "on") {
                setDevices((prev) =>
                    prev.map((d) =>
                        d.id === deviceId ? { ...d, is_online: true } : d
                    )
                )
            } else if (action === "off") {
                setDevices((prev) =>
                    prev.map((d) =>
                        d.id === deviceId ? { ...d, is_online: false } : d
                    )
                )
            } else if (action === "status") {
                // Re-fetch to get the updated is_online from the server
                const refreshed = await apiRequest("/api/devices/")
                setDevices(refreshed.devices || [])
            }
            const labels = { on: "acceso", off: "spento", status: "aggiornato" }
            toast.success(`Dispositivo ${labels[action] || action}`)
        } catch (err) {
            toast.error(`Azione fallita: ${err.message}`)
        } finally {
            setActionLoading((prev) => {
                const next = { ...prev }
                delete next[deviceId]
                return next
            })
        }
    }

    // ── Inline rename ────────────────────────────────────────────────────────
    const startEditing = (device) => {
        setEditingId(device.id)
        setEditName(device.name)
    }

    const cancelEditing = () => {
        setEditingId(null)
        setEditName("")
    }

    const saveEditing = async (deviceId) => {
        const trimmed = editName.trim()
        if (!trimmed) {
            cancelEditing()
            return
        }
        try {
            await apiRequest(`/api/devices/${deviceId}/`, {
                method: "PATCH",
                body: JSON.stringify({ name: trimmed }),
            })
            setDevices((prev) =>
                prev.map((d) => (d.id === deviceId ? { ...d, name: trimmed } : d))
            )
            toast.success("Nome aggiornato")
        } catch (err) {
            toast.error("Errore nel salvataggio: " + err.message)
        } finally {
            cancelEditing()
        }
    }

    // ── Delete device ────────────────────────────────────────────────────────
    const handleDelete = async (device) => {
        if (!confirm(`Eliminare "${device.name}"? Questa azione è irreversibile.`))
            return
        try {
            await apiRequest(`/api/devices/${device.id}/`, { method: "DELETE" })
            setDevices((prev) => prev.filter((d) => d.id !== device.id))
            toast.success("Dispositivo eliminato")
        } catch (err) {
            toast.error("Errore nell'eliminazione: " + err.message)
        }
    }

    // ── Add dialog ───────────────────────────────────────────────────────────
    const openDialog = () => {
        setDialogOpen(true)
        setDialogStep(1)
        setSelectedType(null)
        setFormData({})
    }

    const selectType = (type) => {
        setSelectedType(type)
        setDialogStep(2)
        // Pre-populate form with empty values for config_fields
        const initial = { name: "", ip_address: "" }
        ;(type.config_fields || []).forEach((f) => {
            initial[f.name] = ""
        })
        setFormData(initial)
    }

    const updateFormField = (key, value) => {
        setFormData((prev) => ({ ...prev, [key]: value }))
    }

    const handleSave = async () => {
        if (!formData.name?.trim()) {
            toast.error("Il nome del dispositivo è obbligatorio")
            return
        }
        if (!formData.ip_address?.trim()) {
            toast.error("L'indirizzo IP è obbligatorio")
            return
        }

        // Build config from config_fields
        const config = {}
        for (const field of selectedType.config_fields || []) {
            if (field.required && !formData[field.name]?.trim()) {
                toast.error(`Il campo "${field.label}" è obbligatorio`)
                return
            }
            config[field.name] = formData[field.name] || ""
        }

        setSaving(true)
        try {
            await apiRequest("/api/devices/", {
                method: "POST",
                body: JSON.stringify({
                    name: formData.name.trim(),
                    device_type: selectedType.id,
                    ip_address: formData.ip_address.trim(),
                    config,
                }),
            })
            toast.success("Dispositivo aggiunto con successo!")
            setDialogOpen(false)
            setLoading(true)
            await fetchDevices()
        } catch (err) {
            toast.error("Errore nel salvataggio: " + err.message)
        } finally {
            setSaving(false)
        }
    }

    // ── Render helpers ───────────────────────────────────────────────────────
    const renderStatusDot = (isOnline) => (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium">
            <span
                className={`h-2 w-2 rounded-full ${
                    isOnline
                        ? "bg-emerald-500 animate-pulse"
                        : "bg-red-500"
                }`}
            />
            <span className={isOnline ? "text-emerald-500" : "text-red-500"}>
                {isOnline ? "Online" : "Offline"}
            </span>
        </span>
    )

    const renderDeviceCard = (device, index) => {
        const isEditing = editingId === device.id
        const currentAction = actionLoading[device.id]

        return (
            <Card
                key={device.id}
                className="device-card-fadein group relative overflow-hidden border-border/50 bg-card/80 backdrop-blur transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 hover:border-primary/20"
                style={{ animationDelay: `${index * 100}ms` }}
            >
                {/* Subtle gradient accent line */}
                <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

                <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2.5">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                <DeviceIcon icon={device.icon} className="h-4.5 w-4.5" />
                            </div>
                            <div>
                                <span className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-[11px] font-medium text-secondary-foreground">
                                    {device.device_type_label}
                                </span>
                            </div>
                        </div>
                        {renderStatusDot(device.is_online)}
                    </div>
                </CardHeader>

                <CardContent className="space-y-4">
                    {/* Device name with inline edit */}
                    <div className="space-y-1">
                        {isEditing ? (
                            <div className="flex items-center gap-1.5">
                                <Input
                                    ref={editInputRef}
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") saveEditing(device.id)
                                        if (e.key === "Escape") cancelEditing()
                                    }}
                                    onBlur={() => saveEditing(device.id)}
                                    className="h-8 text-sm font-semibold"
                                />
                            </div>
                        ) : (
                            <div className="flex items-center gap-1.5 group/name">
                                <h3 className="text-base font-semibold tracking-tight">
                                    {device.name}
                                </h3>
                                <button
                                    onClick={() => startEditing(device)}
                                    className="opacity-0 group-hover/name:opacity-100 transition-opacity duration-200 text-muted-foreground hover:text-foreground"
                                    title="Rinomina"
                                >
                                    <Pencil className="h-3 w-3" />
                                </button>
                            </div>
                        )}
                        <p className="text-xs text-muted-foreground font-mono">
                            {device.ip_address}
                        </p>
                    </div>

                    <Separator />

                    {/* Action buttons */}
                    {device.capabilities && device.capabilities.length > 0 && (
                        <div className="flex items-center gap-2">
                            {device.capabilities.includes("on") && (
                                <Button
                                    size="sm"
                                    variant={device.is_online ? "default" : "outline"}
                                    className={`flex-1 text-xs transition-all duration-200 ${
                                        device.is_online
                                            ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600"
                                            : "border-emerald-600/50 text-emerald-600 hover:bg-emerald-600/10"
                                    }`}
                                    disabled={!!currentAction}
                                    onClick={() => handleAction(device.id, "on")}
                                >
                                    {currentAction === "on" ? (
                                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                    ) : (
                                        <Power className="h-3 w-3 mr-1" />
                                    )}
                                    ON
                                </Button>
                            )}
                            {device.capabilities.includes("off") && (
                                <Button
                                    size="sm"
                                    variant={!device.is_online ? "default" : "outline"}
                                    className={`flex-1 text-xs transition-all duration-200 ${
                                        !device.is_online
                                            ? "bg-red-600 hover:bg-red-700 text-white border-red-600"
                                            : "border-red-600/50 text-red-600 hover:bg-red-600/10"
                                    }`}
                                    disabled={!!currentAction}
                                    onClick={() => handleAction(device.id, "off")}
                                >
                                    {currentAction === "off" ? (
                                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                    ) : (
                                        <PowerOff className="h-3 w-3 mr-1" />
                                    )}
                                    OFF
                                </Button>
                            )}
                            {device.capabilities.includes("status") && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="flex-1 text-xs transition-all duration-200"
                                    disabled={!!currentAction}
                                    onClick={() => handleAction(device.id, "status")}
                                >
                                    {currentAction === "status" ? (
                                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                    ) : (
                                        <RefreshCw className="h-3 w-3 mr-1" />
                                    )}
                                    Status
                                </Button>
                            )}
                        </div>
                    )}

                    {/* Delete */}
                    <div className="pt-1">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="w-full text-xs text-destructive hover:text-destructive hover:bg-destructive/10 transition-colors duration-200"
                            onClick={() => handleDelete(device)}
                        >
                            <Trash2 className="h-3 w-3 mr-1.5" />
                            Elimina
                        </Button>
                    </div>
                </CardContent>
            </Card>
        )
    }

    // ── Loading state ────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="space-y-6">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Dispositivi</h2>
                    <p className="text-muted-foreground">
                        Gestisci i dispositivi smart nella tua rete locale.
                    </p>
                </div>
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            </div>
        )
    }

    // ── Main render ──────────────────────────────────────────────────────────
    return (
        <>
            {/* Inject keyframe animation */}
            <style>{fadeInKeyframes}</style>

            <div className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-3xl font-bold tracking-tight">
                            Dispositivi
                        </h2>
                        <p className="text-muted-foreground">
                            Gestisci i dispositivi smart nella tua rete locale.
                        </p>
                    </div>
                    <Button
                        size="icon"
                        className="h-10 w-10 rounded-full shadow-lg shadow-primary/25 transition-transform duration-200 hover:scale-105"
                        onClick={openDialog}
                    >
                        <Plus className="h-5 w-5" />
                    </Button>
                </div>

                {/* Device grid or empty state */}
                {devices.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-24 text-center space-y-4">
                        <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-muted/50">
                            <Router className="h-10 w-10 text-muted-foreground/60" />
                        </div>
                        <div className="space-y-1.5">
                            <p className="text-lg font-medium text-muted-foreground">
                                Nessun dispositivo configurato
                            </p>
                            <p className="text-sm text-muted-foreground/70">
                                Premi{" "}
                                <kbd className="inline-flex h-5 items-center rounded border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
                                    +
                                </kbd>{" "}
                                per aggiungere il primo dispositivo
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                        {devices.map((device, index) =>
                            renderDeviceCard(device, index)
                        )}
                    </div>
                )}
            </div>

            {/* ── Add Device Dialog ──────────────────────────────────────────── */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-[500px]">
                    {dialogStep === 1 ? (
                        <>
                            <DialogHeader>
                                <DialogTitle>Aggiungi dispositivo</DialogTitle>
                                <DialogDescription>
                                    Seleziona il tipo di dispositivo da aggiungere.
                                </DialogDescription>
                            </DialogHeader>

                            <div className="grid gap-3 py-4">
                                {deviceTypes.length === 0 ? (
                                    <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                        Caricamento tipi...
                                    </div>
                                ) : (
                                    deviceTypes.map((type) => (
                                        <button
                                            key={type.id}
                                            onClick={() => selectType(type)}
                                            className="flex items-center gap-3 rounded-lg border border-border/50 p-4 text-left transition-all duration-200 hover:bg-accent hover:border-primary/30 hover:shadow-sm group/type"
                                        >
                                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors duration-200 group-hover/type:bg-primary/20">
                                                <DeviceIcon
                                                    icon={type.icon}
                                                    className="h-5 w-5"
                                                />
                                            </div>
                                            <div className="flex-1">
                                                <p className="text-sm font-medium">
                                                    {type.label}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {(type.capabilities || []).join(", ")}
                                                </p>
                                            </div>
                                            <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover/type:translate-x-0.5" />
                                        </button>
                                    ))
                                )}
                            </div>
                        </>
                    ) : (
                        <>
                            <DialogHeader>
                                <DialogTitle>Configura dispositivo</DialogTitle>
                                <DialogDescription>
                                    Inserisci i dati per{" "}
                                    <span className="font-medium text-foreground">
                                        {selectedType?.label}
                                    </span>
                                </DialogDescription>
                            </DialogHeader>

                            <div className="space-y-4 py-4">
                                {/* Device name */}
                                <div className="space-y-2">
                                    <Label htmlFor="device-name">
                                        Nome dispositivo{" "}
                                        <span className="text-destructive">*</span>
                                    </Label>
                                    <Input
                                        id="device-name"
                                        placeholder="es. Stampante 3D"
                                        value={formData.name || ""}
                                        onChange={(e) =>
                                            updateFormField("name", e.target.value)
                                        }
                                    />
                                </div>

                                {/* IP address */}
                                <div className="space-y-2">
                                    <Label htmlFor="device-ip">
                                        Indirizzo IP{" "}
                                        <span className="text-destructive">*</span>
                                    </Label>
                                    <Input
                                        id="device-ip"
                                        type="text"
                                        placeholder="192.168.1.X"
                                        value={formData.ip_address || ""}
                                        onChange={(e) =>
                                            updateFormField("ip_address", e.target.value)
                                        }
                                    />
                                </div>

                                {/* Dynamic config fields */}
                                {(selectedType?.config_fields || []).length > 0 && (
                                    <>
                                        <Separator />
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Configurazione
                                        </p>
                                        {selectedType.config_fields.map((field) => (
                                            <div
                                                key={field.name}
                                                className="space-y-2"
                                            >
                                                <Label htmlFor={`field-${field.name}`}>
                                                    {field.label}
                                                    {field.required && (
                                                        <span className="text-destructive ml-1">
                                                            *
                                                        </span>
                                                    )}
                                                </Label>
                                                <Input
                                                    id={`field-${field.name}`}
                                                    type={field.type || "text"}
                                                    placeholder={field.label}
                                                    required={field.required}
                                                    value={
                                                        formData[field.name] || ""
                                                    }
                                                    onChange={(e) =>
                                                        updateFormField(
                                                            field.name,
                                                            e.target.value
                                                        )
                                                    }
                                                />
                                            </div>
                                        ))}
                                    </>
                                )}
                            </div>

                            <DialogFooter className="gap-2 sm:gap-0">
                                <Button
                                    variant="ghost"
                                    onClick={() => setDialogStep(1)}
                                    disabled={saving}
                                >
                                    <ArrowLeft className="h-4 w-4 mr-1.5" />
                                    Indietro
                                </Button>
                                <Button onClick={handleSave} disabled={saving}>
                                    {saving && (
                                        <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                                    )}
                                    Salva
                                </Button>
                            </DialogFooter>
                        </>
                    )}
                </DialogContent>
            </Dialog>
        </>
    )
}
