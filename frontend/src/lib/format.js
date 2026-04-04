/**
 * Format a byte count into a human-readable file size string.
 * @param {number|null} bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
    if (bytes == null || bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    const k = 1024
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    const size = bytes / Math.pow(k, i)
    return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/**
 * Format an ISO date string into a localized short date/time.
 * @param {string|null} isoString
 * @returns {string}
 */
export function formatDate(isoString) {
    if (!isoString) return "—"
    try {
        return new Date(isoString).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    } catch {
        return "—"
    }
}
