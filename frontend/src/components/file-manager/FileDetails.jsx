import { FileIcon } from "./FileIcon"
import { Button } from "@/components/ui/button"
import { X, Download, Share2, Trash2 } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { formatFileSize, formatDate } from "@/lib/format"

function getFileExtension(filename) {
    if (!filename) return null
    const lastDot = filename.lastIndexOf('.')
    if (lastDot === -1 || lastDot === 0) return null
    return filename.substring(lastDot).toUpperCase()
}


export function FileDetails({ file, onClose, onShare, onDownload, onDelete }) {
    if (!file) return null

    const isFolder = file.type === 'folder'
    const extension = isFolder ? null : getFileExtension(file.name)
    const typeLabel = isFolder ? "Folder" : (extension || "File")
    const sizeLabel = isFolder ? "Folder" : (formatFileSize(file.size_bytes) || "—")

    return (
        <div className="w-80 border-l bg-card p-4 flex flex-col h-full overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-lg">Details</h3>
                <Button variant="ghost" size="icon" onClick={onClose}>
                    <X className="h-4 w-4" />
                </Button>
            </div>

            <div className="flex flex-col items-center mb-6">
                <FileIcon type={file.type} className="h-24 w-24 mb-4" />
                <h4 className="font-medium text-center break-all">{file.name}</h4>
                <p className="text-sm text-muted-foreground">{sizeLabel}</p>
            </div>

            <Separator className="my-4" />

            <div className="space-y-4">
                <div>
                    <span className="text-xs text-muted-foreground uppercase font-bold">Type</span>
                    <p className="text-sm">{typeLabel}</p>
                </div>
                <div>
                    <span className="text-xs text-muted-foreground uppercase font-bold">Last Modified</span>
                    <p className="text-sm">{formatDate(file.last_accessed || file.created_at)}</p>
                </div>
                <div>
                    <span className="text-xs text-muted-foreground uppercase font-bold">Created</span>
                    <p className="text-sm">{formatDate(file.created_at)}</p>
                </div>
                <div>
                    <span className="text-xs text-muted-foreground uppercase font-bold">Location</span>
                    <p className="text-sm truncate" title={file.relative_path}>
                        /{file.relative_path || file.name}
                    </p>
                </div>
            </div>

            <Separator className="my-6" />

            <div className="flex flex-col gap-2 mt-auto">
                <Button
                    className="w-full gap-2"
                    onClick={() => onDownload(file)}
                >
                    <Download className="h-4 w-4" /> Download
                </Button>
                <Button variant="outline" className="w-full gap-2" onClick={() => onShare(file)}>
                    <Share2 className="h-4 w-4" /> Share
                </Button>
                <Button variant="destructive" className="w-full gap-2" onClick={() => onDelete(file)}>
                    <Trash2 className="h-4 w-4" /> Delete
                </Button>
            </div>
        </div>
    )
}
