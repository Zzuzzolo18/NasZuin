import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { useSearchParams } from "react-router-dom"
import { FileGrid } from "@/components/file-manager/FileGrid"
import { FileList } from "@/components/file-manager/FileList"
import { FileBreadcrumb } from "@/components/file-manager/FileBreadcrumb"
import { FileDetails } from "@/components/file-manager/FileDetails"
import { ShareModal } from "@/components/file-manager/ShareModal"
import { Button } from "@/components/ui/button"
import { LayoutGrid, List as ListIcon, Search, Filter, Plus, CheckSquare, Trash2, Download, Share2, X, Upload, FolderOpen, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { apiRequest } from "@/lib/api"
import { formatFileSize } from "@/lib/format"
import { useFileSearch } from "@/hooks/useFileSearch"
import { useFileSelection } from "@/hooks/useFileSelection"
import { useFileOperations } from "@/hooks/useFileOperations"

export default function FileManager() {
    const [searchParams, setSearchParams] = useSearchParams()
    const [viewMode, setViewMode] = useState("grid")

    // Derive path from URL param
    const currentPathString = searchParams.get('path') || ""

    const currentPath = (() => {
        if (!currentPathString) return []
        const parts = currentPathString.split('/').filter(Boolean)
        let accumulatedPath = ""
        return parts.map(part => {
            accumulatedPath = accumulatedPath ? `${accumulatedPath}/${part}` : part
            return { name: part, path: accumulatedPath }
        })
    })()

    const [selectedFile, setSelectedFile] = useState(null)
    const [files, setFiles] = useState([])
    const [loading, setLoading] = useState(true)

    // Share Modal State
    const [shareFile, setShareFile] = useState(null)
    const [isShareModalOpen, setIsShareModalOpen] = useState(false)

    const fetchFiles = useCallback(async () => {
        try {
            setLoading(true)
            const url = `/api/files/list/?path=${encodeURIComponent(currentPathString)}`
            const data = await apiRequest(url)
            setFiles(data.files)
        } catch (error) {
            console.error('Error fetching files:', error)
        } finally {
            setLoading(false)
        }
    }, [currentPathString])

    useEffect(() => {
        fetchFiles()
    }, [fetchFiles])

    // --- Hooks ---
    const search = useFileSearch(setSearchParams)
    const selection = useFileSelection(files)
    const ops = useFileOperations(currentPathString, fetchFiles)

    // --- Navigation ---
    const handleNavigate = (breadcrumbItem) => {
        if (!breadcrumbItem || breadcrumbItem.path === "") {
            setSearchParams({})
        } else {
            setSearchParams({ path: breadcrumbItem.path })
        }
        setSelectedFile(null)
        selection.exitSelectionMode()
    }

    const handleFileClick = (file) => {
        if (selection.isSelectionMode) {
            selection.toggleFileSelection(file.id)
        } else if (file.type === "folder") {
            setSearchParams({ path: file.relative_path })
            setSelectedFile(null)
        } else {
            setSelectedFile(file)
        }
    }

    // --- Share ---
    const handleShare = (file) => {
        setShareFile(file)
        setIsShareModalOpen(true)
    }

    const handleBulkShare = () => {
        if (selection.selectedFileIds.size !== 1) {
            toast.error("Please select exactly one file to share")
            return
        }
        const fileId = Array.from(selection.selectedFileIds)[0]
        const file = files.find(f => f.id === fileId)
        if (file) handleShare(file)
    }

    // --- Wrappers for hooks that need component state ---
    const handleDelete = (file) => ops.handleDelete(file, selectedFile, setSelectedFile)
    const handleBulkDownload = () => ops.handleBulkDownload(selection.getSelectedItems, selection.exitSelectionMode)
    const handleBulkDelete = () => ops.handleBulkDelete(selection.getSelectedItems, selection.exitSelectionMode)

    return (
        <div
            className="h-full flex flex-col space-y-4 relative min-h-0 overflow-hidden"
            onDrop={ops.handleDrop}
            onDragOver={ops.handleDragOver}
            onDragLeave={ops.handleDragLeave}
        >
            <ShareModal
                file={shareFile}
                isOpen={isShareModalOpen}
                onClose={() => setIsShareModalOpen(false)}
            />

            {/* Hidden file input for mobile upload */}
            <input
                type="file"
                multiple
                ref={ops.fileInputRef}
                onChange={ops.handleFileInputChange}
                className="hidden"
            />

            {ops.isDragging && (
                <div className="absolute inset-0 z-50 bg-primary/20 border-2 border-primary border-dashed rounded-lg flex items-center justify-center backdrop-blur-sm pointer-events-none">
                    <div className="text-primary font-bold text-xl">Drop files to upload</div>
                </div>
            )}

            {/* Create Folder Modal */}
            {ops.isCreatingFolder && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                    <div className="bg-card border p-6 rounded-lg shadow-lg w-full max-w-sm space-y-4">
                        <h3 className="text-lg font-semibold">Create New Folder</h3>
                        <form onSubmit={ops.handleCreateFolder} className="space-y-4">
                            <Input
                                placeholder="Folder Name"
                                value={ops.newFolderName}
                                onChange={(e) => ops.setNewFolderName(e.target.value)}
                                autoFocus
                            />
                            <div className="flex justify-end gap-2">
                                <Button type="button" variant="ghost" onClick={() => ops.setIsCreatingFolder(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit">
                                    Create
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Toolbar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b pb-4">
                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <h2 className="text-2xl font-bold tracking-tight hidden sm:block">Files</h2>
                    <div className="sm:hidden w-full">
                        <FileBreadcrumb path={currentPath} onNavigate={(item) => handleNavigate(item || { path: "" })} />
                    </div>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto flex-wrap sm:flex-nowrap">
                    {/* Normal Mode Tools */}
                    {!selection.isSelectionMode && (
                        <>
                            <div className="relative w-full sm:w-64 order-2 sm:order-1">
                                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    type="search"
                                    placeholder="Search all files..."
                                    className="pl-8 h-9"
                                    value={search.searchQuery}
                                    onChange={(e) => search.setSearchQuery(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Escape' && search.clearSearch()}
                                />
                                {search.searchQuery && (
                                    <button
                                        onClick={search.clearSearch}
                                        className="absolute right-2 top-2.5 h-4 w-4 text-muted-foreground hover:text-foreground"
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                )}
                            </div>
                            <div className="flex items-center border rounded-md order-1 sm:order-2">
                                <Button
                                    variant={viewMode === "grid" ? "secondary" : "ghost"}
                                    size="icon"
                                    className="h-9 w-9 rounded-r-none"
                                    onClick={() => setViewMode("grid")}
                                >
                                    <LayoutGrid className="h-4 w-4" />
                                </Button>
                                <Button
                                    variant={viewMode === "list" ? "secondary" : "ghost"}
                                    size="icon"
                                    className="h-9 w-9 rounded-l-none"
                                    onClick={() => setViewMode("list")}
                                >
                                    <ListIcon className="h-4 w-4" />
                                </Button>
                            </div>
                            <Button
                                size="icon"
                                variant={selectedFile ? "secondary" : "outline"}
                                className={cn("h-9 w-9 order-1 sm:order-3", selectedFile && "text-primary")}
                                onClick={() => setSelectedFile(selectedFile ? null : files[0])}
                            >
                                <Filter className="h-4 w-4" />
                            </Button>

                            <Button
                                size="sm"
                                variant="outline"
                                className="h-9 gap-1 order-1 sm:order-4"
                                onClick={selection.toggleSelectionMode}
                            >
                                <CheckSquare className="h-4 w-4" />
                                <span className="hidden sm:inline">Select</span>
                            </Button>

                            <Button
                                size="sm"
                                variant="outline"
                                className="h-9 gap-1 order-1 sm:order-5"
                                onClick={() => ops.fileInputRef.current?.click()}
                            >
                                <Upload className="h-4 w-4" />
                                <span className="hidden sm:inline">Upload</span>
                            </Button>

                            <Button
                                size="sm"
                                className="h-9 gap-1 order-1 sm:order-6"
                                onClick={() => ops.setIsCreatingFolder(true)}
                            >
                                <Plus className="h-4 w-4" />
                                <span className="hidden sm:inline">New</span>
                            </Button>
                        </>
                    )}

                    {/* Selection Mode Tools */}
                    {selection.isSelectionMode && (
                        <div className="flex items-center gap-2 w-full animate-in fade-in slide-in-from-top-2 duration-200">
                            <Button size="sm" variant="ghost" onClick={selection.toggleSelectionMode} className="mr-2">
                                <X className="h-4 w-4 mr-1" /> Cancel
                            </Button>

                            <div className="flex items-center text-sm text-muted-foreground mr-auto">
                                <span className="font-medium text-foreground">{selection.selectedFileIds.size}</span>
                                <span className="ml-1">selected</span>
                            </div>

                            <Button size="sm" variant="outline" onClick={selection.selectedFileIds.size === files.length ? selection.deselectAll : selection.selectAll}>
                                {selection.selectedFileIds.size === files.length ? "Deselect All" : "Select All"}
                            </Button>

                            <div className="h-6 w-px bg-border mx-1" />

                            <Button size="sm" variant="outline" onClick={handleBulkShare} disabled={selection.selectedFileIds.size === 0}>
                                <Share2 className="h-4 w-4 sm:mr-1" />
                                <span className="hidden sm:inline">Share</span>
                            </Button>
                            <Button size="sm" variant="outline" onClick={handleBulkDownload} disabled={selection.selectedFileIds.size === 0}>
                                <Download className="h-4 w-4 sm:mr-1" />
                                <span className="hidden sm:inline">Download</span>
                            </Button>
                            <Button size="sm" variant="destructive" onClick={handleBulkDelete} disabled={selection.selectedFileIds.size === 0}>
                                <Trash2 className="h-4 w-4 sm:mr-1" />
                                <span className="hidden sm:inline">Delete</span>
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            {/* Breadcrumb - Desktop */}
            <div className="hidden sm:block">
                <FileBreadcrumb path={currentPath} onNavigate={(item) => handleNavigate(item || { path: "" })} />
            </div>

            <div className="flex-1 flex min-h-0 gap-4 overflow-hidden">
                {/* File Area */}
                <div className="flex-1 overflow-auto rounded-lg border bg-card/50 p-4">
                    {/* Search Results View */}
                    {search.searchResults !== null ? (
                        search.isSearching ? (
                            <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-3">
                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                <p className="text-sm">Searching...</p>
                            </div>
                        ) : search.searchResults.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                                <Search className="h-12 w-12 mb-3 opacity-30" />
                                <p className="text-lg font-medium">No results found</p>
                                <p className="text-sm">No files matching "{search.searchQuery}"</p>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                <p className="text-sm text-muted-foreground mb-3">
                                    {search.searchResults.length} result{search.searchResults.length !== 1 ? 's' : ''} for "{search.searchQuery}"
                                </p>
                                {search.searchResults.map((file) => (
                                    <div
                                        key={file.id}
                                        className="flex items-center gap-3 p-3 rounded-lg hover:bg-accent/50 cursor-pointer transition-colors"
                                        onClick={() => search.handleSearchResultClick(file)}
                                    >
                                        <div className="flex-1 min-w-0">
                                            <p className="font-medium truncate">{file.name}</p>
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                                                <FolderOpen className="h-3 w-3 flex-shrink-0" />
                                                <span className="truncate">{file.folder || 'Root'}</span>
                                                <span className="mx-1">•</span>
                                                <span className="flex-shrink-0">{formatFileSize(file.size_bytes)}</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )
                    ) : loading ? (
                        <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-3">
                            <Loader2 className="h-8 w-8 animate-spin text-primary" />
                            <p className="text-sm">Loading files...</p>
                        </div>
                    ) : files.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                            <p>Empty folder</p>
                        </div>
                    ) : viewMode === "grid" ? (
                        <FileGrid
                            files={files}
                            onFileClick={handleFileClick}
                            isSelectionMode={selection.isSelectionMode}
                            selectedFileIds={selection.selectedFileIds}
                            onToggleSelection={selection.toggleFileSelection}
                            onDownload={ops.handleDownload}
                            onDelete={handleDelete}
                            onShare={handleShare}
                        />
                    ) : (
                        <FileList
                            files={files}
                            onFileClick={handleFileClick}
                            isSelectionMode={selection.isSelectionMode}
                            selectedFileIds={selection.selectedFileIds}
                            onToggleSelection={selection.toggleFileSelection}
                            onDownload={ops.handleDownload}
                            onDelete={handleDelete}
                            onShare={handleShare}
                        />
                    )}
                </div>

                {/* Details Sidebar / Drawer */}
                {selectedFile && (
                    <>
                        {/* Mobile Overlay Backdrop */}
                        <div
                            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 lg:hidden animate-in fade-in"
                            onClick={() => setSelectedFile(null)}
                        />

                        {/* The Panel */}
                        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-80 bg-background p-4 shadow-xl lg:static lg:p-0 lg:shadow-none lg:border-l overflow-y-auto animate-in slide-in-from-right lg:animate-none border-l h-full">
                            <div className="flex justify-end lg:hidden mb-2">
                                <Button variant="ghost" size="icon" onClick={() => setSelectedFile(null)}>
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                            <FileDetails
                                file={selectedFile}
                                onClose={() => setSelectedFile(null)}
                                onShare={handleShare}
                                onDownload={ops.handleDownload}
                                onDelete={handleDelete}
                            />
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}
