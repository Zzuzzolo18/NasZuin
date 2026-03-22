import { useState, useCallback } from "react"
import { toast } from "sonner"

/**
 * Hook for multi-file selection logic.
 * Returns selection state and handlers.
 */
export function useFileSelection(files) {
    const [isSelectionMode, setIsSelectionMode] = useState(false)
    const [selectedFileIds, setSelectedFileIds] = useState(new Set())

    const toggleSelectionMode = useCallback(() => {
        setIsSelectionMode(prev => !prev)
        setSelectedFileIds(new Set())
    }, [])

    const exitSelectionMode = useCallback(() => {
        setIsSelectionMode(false)
        setSelectedFileIds(new Set())
    }, [])

    const toggleFileSelection = useCallback((fileId) => {
        setSelectedFileIds(prev => {
            const next = new Set(prev)
            if (next.has(fileId)) {
                next.delete(fileId)
            } else {
                next.add(fileId)
            }
            return next
        })
    }, [])

    const selectAll = useCallback(() => {
        setSelectedFileIds(new Set(files.map(f => f.id)))
    }, [files])

    const deselectAll = useCallback(() => {
        setSelectedFileIds(new Set())
    }, [])

    const getSelectedItems = useCallback(() => {
        return files.filter(f => selectedFileIds.has(f.id))
    }, [files, selectedFileIds])

    return {
        isSelectionMode,
        selectedFileIds,
        toggleSelectionMode,
        exitSelectionMode,
        toggleFileSelection,
        selectAll,
        deselectAll,
        getSelectedItems,
    }
}
