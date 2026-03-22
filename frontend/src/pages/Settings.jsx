import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { AlertCircle, CheckCircle2 } from "lucide-react"
import { apiRequest, fetchApi } from "@/lib/api"

export default function Settings() {
    const [is2FAEnabled, setIs2FAEnabled] = useState(false)
    const [loading, setLoading] = useState(true)
    const [setupStep, setSetupStep] = useState('idle') // idle, scanning, verifying
    const [qrCode, setQrCode] = useState(null)
    const [otpToken, setOtpToken] = useState("")
    const [error, setError] = useState("")
    const [successMsg, setSuccessMsg] = useState("")

    useEffect(() => {
        // Ensure CSRF cookie is set
        fetchApi('/api/auth/csrf/')
        fetchStatus()
    }, [])

    const fetchStatus = async () => {
        try {
            const data = await apiRequest('/api/auth/2fa/status/')
            setIs2FAEnabled(data.enabled)
        } catch (err) {
            console.error("Failed to fetch 2FA status", err)
        } finally {
            setLoading(false)
        }
    }

    const startSetup = async () => {
        setLoading(true)
        setError("")
        try {
            const res = await fetchApi('/api/auth/2fa/setup/', {
                method: 'POST',
            })
            if (res.ok) {
                const data = await res.json()
                setQrCode(data.qr_code_base64)
                setSetupStep('scanning')
            } else {
                const text = await res.text()
                setError(`Failed to start setup (${res.status}): ${text}`)
            }
        } catch (err) {
            setError(`Network error: ${err.message}`)
        } finally {
            setLoading(false)
        }
    }

    const verifySetup = async () => {
        setLoading(true)
        setError("")
        try {
            const data = await apiRequest('/api/auth/2fa/confirm/', {
                method: 'POST',
                body: JSON.stringify({ token: otpToken })
            })

            setIs2FAEnabled(true)
            setSetupStep('idle')
            setQrCode(null)
            setOtpToken("")
            setSuccessMsg("Two-Factor Authentication enabled successfully!")
            setTimeout(() => setSuccessMsg(""), 3000)
        } catch (err) {
            setError(err.message || "Verification failed")
        } finally {
            setLoading(false)
        }
    }

    const disable2FA = async () => {
        if (!confirm("Are you sure you want to disable 2FA? This will reduce your account security.")) return

        setLoading(true)
        try {
            const res = await fetchApi('/api/auth/2fa/disable/', {
                method: 'POST',
            })

            if (res.ok) {
                setIs2FAEnabled(false)
                setSetupStep('idle')
                setSuccessMsg("Two-Factor Authentication disabled.")
                setTimeout(() => setSuccessMsg(""), 3000)
            }
        } catch (err) {
            setError("Failed to disable 2FA")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
                <p className="text-muted-foreground">Manage system configurations and security.</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Security</CardTitle>
                    <CardDescription>Manage Two-Factor Authentication (2FA)</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">

                    {successMsg && (
                        <div className="flex items-center gap-2 p-3 text-sm text-green-500 bg-green-50 rounded-md">
                            <CheckCircle2 className="h-4 w-4" />
                            {successMsg}
                        </div>
                    )}

                    {error && (
                        <div className="flex items-center gap-2 p-3 text-sm text-red-500 bg-red-50 rounded-md">
                            <AlertCircle className="h-4 w-4" />
                            {error}
                        </div>
                    )}

                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-base">Two-Factor Authentication</Label>
                            <p className="text-sm text-muted-foreground">
                                {is2FAEnabled
                                    ? "Your account is secured with 2FA."
                                    : "Add an extra layer of security to your account."}
                            </p>
                        </div>
                        <div>
                            {loading && setupStep === 'idle' ? (
                                <Button disabled>Loading...</Button>
                            ) : is2FAEnabled ? (
                                <Button variant="destructive" onClick={disable2FA}>Disable 2FA</Button>
                            ) : setupStep === 'idle' ? (
                                <Button onClick={startSetup}>Enable 2FA</Button>
                            ) : (
                                <Button variant="ghost" onClick={() => setSetupStep('idle')}>Cancel</Button>
                            )}
                        </div>
                    </div>

                    {setupStep === 'scanning' && qrCode && (
                        <>
                            <Separator className="my-4" />
                            <div className="space-y-4">
                                <div className="text-center space-y-2">
                                    <Label>1. Scan QR Code</Label>
                                    <div className="flex justify-center">
                                        <img src={qrCode} alt="2FA QR Code" className="border rounded-lg" />
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Use Google Authenticator or any TOTP app.
                                    </p>
                                </div>

                                <div className="space-y-2 max-w-sm mx-auto">
                                    <Label htmlFor="otp">2. Enter Code</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            id="otp"
                                            placeholder="123456"
                                            value={otpToken}
                                            onChange={(e) => setOtpToken(e.target.value)}
                                            maxLength={6}
                                        />
                                        <Button onClick={verifySetup} disabled={loading || otpToken.length !== 6}>
                                            Verify
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
