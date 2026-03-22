import { useState, useCallback, useRef } from "react"
import { toast } from "sonner"
import { apiRequest, fetchApi } from "@/lib/api"

/**
 * Hook for all file CRUD operations: fetch, upload, create folder, download, delete.
 * Also handles drag-and-drop and file input uploads.
 */
export function useFileOperations(currentPathString, fetchFiles) {
    const [isCreatingFolder, setIsCreatingFolder] = useState(false)
    const [newFolderName, setNewFolderName] = useState("")
    const [isDragging, setIsDragging] = useState(false)
    const fileInputRef = useRef(null)

    // --- Upload ---

    const uploadFile = useCallback(async (file) => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('relative_path', currentPathString)

        try {
            const promise = fetchApi('/api/files/upload/', {
                method: 'POST',
                body: formData
            })

            toast.promise(promise, {
                loading: `Uploading ${file.name}...`,
                success: async (response) => {
                    if (!response.ok) {
                        const errorData = await response.json()
                        throw new Error(errorData.error || 'Unknown error')
                    }
                    return `${file.name} uploaded successfully`
                },
                error: (err) => `Upload failed: ${err.message}`
            })

            await promise
        } catch (error) {
            console.error("Upload error:", error)
        }
    }, [currentPathString])

    const handleDrop = useCallback(async (e) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)

        const droppedFiles = Array.from(e.dataTransfer.files)
        if (droppedFiles.length === 0) return

        // Upload all files in parallel
        await Promise.all(droppedFiles.map(file => uploadFile(file)))
        fetchFiles()
    }, [uploadFile, fetchFiles])

    const handleFileInputChange = useCallback(async (e) => {
        const selectedFiles = Array.from(e.target.files)
        if (selectedFiles.length === 0) return

        // Upload all files in parallel
        await Promise.all(selectedFiles.map(file => uploadFile(file)))

        // Reset input so same file can be re-selected
        e.target.value = null
        fetchFiles()
    }, [uploadFile, fetchFiles])

    const handleDragOver = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)
    }, [])

    // --- Create Folder ---

    const handleCreateFolder = useCallback(async (e) => {
        e.preventDefault()
        if (!newFolderName.trim()) return

        try {
            const promise = fetchApi('/api/files/create-folder/', {
                method: 'POST',
                body: JSON.stringify({
                    name: newFolderName,
                    path: currentPathString
                })
            })

            toast.promise(promise, {
                loading: 'Creating folder...',
                success: async (response) => {
                    if (!response.ok) {
                        const data = await response.json()
                        throw new Error(data.error || 'Failed to create folder')
                    }
                    setIsCreatingFolder(false)
                    setNewFolderName("")
                    fetchFiles()
                    return 'Folder created'
                },
                error: (err) => err.message
            })
        } catch (error) {
            console.error(error)
            toast.error('Error creating folder')
        }
    }, [newFolderName, currentPathString, fetchFiles])

    // --- Download ---

    const handleDownload = useCallback(async (file) => {
        if (file.type === "folder") {
            const folderPath = file.relative_path
            const downloadUrl = `/api/files/download-folder/?path=${encodeURIComponent(folderPath)}`
            toast.info(`Preparing download for folder: ${file.name}`, { duration: 3000 })

            setTimeout(() => {
                const link = document.createElement('a')
                link.href = downloadUrl
                link.download = `${file.name}.zip`
                document.body.appendChild(link)
                link.click()
                document.body.removeChild(link)
            }, 500)
            return
        }

        const downloadUrl = `/api/files/download/${file.id}/`
        const link = document.createElement('a')
        link.href = downloadUrl
        link.download = file.name
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }, [])

    // --- Delete ---

    const handleDelete = useCallback(async (file, selectedFile, setSelectedFile) => {
        if (file.type === "folder") {
            if (!confirm(`WARNING: You are about to delete the folder "${file.name}" and ALL its content.\n\nThis action cannot be undone.\n\nAre you sure you want to proceed?`)) return

            try {
                const promise = fetchApi(`/api/files/delete-folder/?path=${encodeURIComponent(file.relative_path)}`, {
                    method: 'DELETE',
                })

                toast.promise(promise, {
                    loading: 'Deleting folder...',
                    success: async (response) => {
                        if (response.ok) {
                            fetchFiles()
                            return 'Folder deleted'
                        } else {
                            const data = await response.json()
                            throw new Error(data.error || 'Failed to delete folder')
                        }
                    },
                    error: (err) => err.message
                })
            } catch (error) {
                console.error(error)
                toast.error('Error deleting folder')
            }
            return
        }

        if (!confirm(`Are you sure you want to delete ${file.name}?`)) return

        try {
            const promise = fetchApi(`/api/files/delete/${file.id}/`, {
                method: 'DELETE',
            })

            toast.promise(promise, {
                loading: 'Deleting file...',
                success: async (response) => {
                    if (response.ok) {
                        fetchFiles()
                        if (selectedFile?.id === file.id) setSelectedFile(null)
                        return 'File deleted'
                    } else {
                        const data = await response.json()
                        throw new Error(data.error || 'Failed to delete file')
                    }
                },
                error: (err) => err.message
            })
        } catch (error) {
            console.error(error)
            toast.error('Error deleting file')
        }
    }, [fetchFiles])

    // --- Bulk Operations ---

    const handleBulkDownload = useCallback(async (getSelectedItems, exitSelectionMode) => {
        const selectedItems = getSelectedItems()
        const fileIds = selectedItems.filter(f => f.type !== 'folder').map(f => f.id)
        const folderPaths = selectedItems.filter(f => f.type === 'folder').map(f => f.relative_path)

        if (fileIds.length === 0 && folderPaths.length === 0) {
            toast.info("No files or folders selected for download.")
            return
        }

        try {
            const promise = fetchApi('/api/files/bulk-download/', {
                method: 'POST',
                body: JSON.stringify({ file_ids: fileIds, folder_paths: folderPaths })
            })

            toast.promise(promise, {
                loading: 'Preparing bulk download...',
                success: async (response) => {
                    if (!response.ok) {
                        const errorData = await response.json()
                        throw new Error(errorData.error || "Bulk download failed")
                    }
                    const blob = await response.blob()
                    const url = window.URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = "download.zip"
                    document.body.appendChild(a)
                    a.click()
                    window.URL.revokeObjectURL(url)
                    a.remove()
                    exitSelectionMode()
                    return 'Download started'
                },
                error: (err) => `Failed to download files: ${err.message}`
            })
        } catch (error) {
            console.error("Bulk download error:", error)
            toast.error("Bulk download error")
        }
    }, [])

    const handleBulkDelete = useCallback(async (getSelectedItems, exitSelectionMode) => {
        const selectedItems = getSelectedItems()
        if (selectedItems.length === 0) return
        if (!confirm(`Are you sure you want to delete ${selectedItems.length} items? This action cannot be undone.`)) return

        const fileIds = selectedItems.filter(f => f.type !== 'folder').map(f => f.id)
        const folderPaths = selectedItems.filter(f => f.type === 'folder').map(f => f.relative_path)

        try {
            const promise = fetchApi('/api/files/bulk-delete/', {
                method: 'POST',
                body: JSON.stringify({ file_ids: fileIds, folder_paths: folderPaths })
            })

            toast.promise(promise, {
                loading: 'Deleting selected items...',
                success: async (response) => {
                    if (!response.ok) {
                        const errorData = await response.json()
                        throw new Error(errorData.error || "Failed to delete selected items.")
                    }
                    fetchFiles()
                    exitSelectionMode()
                    return 'Selected items deleted'
                },
                error: (err) => `Failed to delete items: ${err.message}`
            })
        } catch (error) {
            console.error("Bulk delete error:", error)
            toast.error("Bulk delete error")
        }
    }, [fetchFiles])

    return {
        // Upload
        uploadFile,
        handleDrop,
        handleFileInputChange,
        handleDragOver,
        handleDragLeave,
        isDragging,
        fileInputRef,
        // Folder
        isCreatingFolder,
        setIsCreatingFolder,
        newFolderName,
        setNewFolderName,
        handleCreateFolder,
        // CRUD
        handleDownload,
        handleDelete,
        handleBulkDownload,
        handleBulkDelete,
    }
}
