import { useState, useEffect } from "react"
import { useNavigate, Link } from "react-router-dom"
import { apiRequest } from "../lib/api"
import { cn } from "../lib/utils"

export default function Login() {
    const [step, setStep] = useState("credentials") // credentials | 2fa
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")
    const [otp, setOtp] = useState("")
    const [error, setError] = useState("")
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()

    useEffect(() => {
        // Ensure CSRF cookie is set
        apiRequest('/api/auth/csrf/').catch(() => { });
    }, []);

    const handleLogin = async (e) => {
        e.preventDefault()
        setError("")
        setLoading(true)

        try {
            const data = await apiRequest("/api/auth/login/", {
                method: "POST",
                body: JSON.stringify({ username, password }),
            })

            if (data.require_2fa) {
                setStep("2fa")
            } else if (data.success) {
                navigate("/");
            }

        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const handle2FA = async (e) => {
        e.preventDefault()
        setError("")
        setLoading(true)

        try {
            const data = await apiRequest("/api/auth/verify-2fa/", {
                method: "POST",
                body: JSON.stringify({ token: otp }),
            })

            if (data.success) {
                navigate("/")
            }
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex h-screen w-full items-center justify-center bg-gray-100 dark:bg-gray-900">
            <div className="w-full max-w-md space-y-8 rounded-lg bg-white p-8 shadow-lg dark:bg-gray-800">
                <div className="text-center">
                    <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white">
                        {step === "credentials" ? "Sign in to your account" : "Two-Factor Authentication"}
                    </h2>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        {step === "credentials"
                            ? "Enter your details below"
                            : "Enter the code from your authenticator app"}
                    </p>
                </div>

                {error && (
                    <div className="rounded-md bg-red-50 p-4 text-sm text-red-700 dark:bg-red-900/50 dark:text-red-200">
                        {error}
                    </div>
                )}

                {step === "credentials" ? (
                    <form className="mt-8 space-y-6" onSubmit={handleLogin}>
                        <div className="-space-y-px rounded-md shadow-sm">
                            <div>
                                <label htmlFor="username" className="sr-only">Username</label>
                                <input
                                    id="username"
                                    name="username"
                                    type="text"
                                    required
                                    className="relative block w-full rounded-t-md border-0 py-1.5 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 dark:bg-gray-700 dark:text-white dark:ring-gray-600"
                                    placeholder="Username"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                />
                            </div>
                            <div>
                                <label htmlFor="password" className="sr-only">Password</label>
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    required
                                    className="relative block w-full rounded-b-md border-0 py-1.5 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 dark:bg-gray-700 dark:text-white dark:ring-gray-600"
                                    placeholder="Password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                />
                            </div>
                        </div>

                        <div>
                            <button
                                type="submit"
                                disabled={loading}
                                className="group relative flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
                            >
                                {loading ? "Signing in..." : "Sign in"}
                            </button>
                        </div>

                        <div className="text-center text-sm">
                            <span className="text-gray-600 dark:text-gray-400">Don't have an account? </span>
                            <Link to="/register" className="font-semibold text-indigo-600 hover:text-indigo-500">
                                Register
                            </Link>
                        </div>
                    </form>
                ) : (
                    <form className="mt-8 space-y-6" onSubmit={handle2FA}>
                        <div>
                            <label htmlFor="otp" className="sr-only">One-Time Password</label>
                            <input
                                id="otp"
                                name="otp"
                                type="text"
                                required
                                className="block w-full rounded-md border-0 py-1.5 text-center text-2xl tracking-widest text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:leading-6 dark:bg-gray-700 dark:text-white dark:ring-gray-600"
                                placeholder="000000"
                                value={otp}
                                onChange={(e) => setOtp(e.target.value)}
                                maxLength={6}
                            />
                        </div>

                        <div>
                            <button
                                type="submit"
                                disabled={loading}
                                className="group relative flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
                            >
                                {loading ? "Verifying..." : "Verify"}
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    )
}
