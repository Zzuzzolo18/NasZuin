import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { MoreVertical, Download, Trash2, Share2, FolderOpen } from "lucide-react"

export function FileActionsMenu({ file, onDownload, onDelete, onShare, onOpen }) {
    const isFolder = file.type === 'folder';

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:bg-muted/50 data-[state=open]:bg-muted"
                    onClick={(e) => e.stopPropagation()}
                >
                    <MoreVertical className="h-4 w-4" />
                    <span className="sr-only">Open menu</span>
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
                {isFolder && onOpen && (
                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onOpen(file); }}>
                        <FolderOpen className="mr-2 h-4 w-4" />
                        Open
                    </DropdownMenuItem>
                )}
                <DropdownMenuItem
                    onClick={(e) => { e.stopPropagation(); onDownload(file); }}
                >
                    <Download className="mr-2 h-4 w-4" />
                    Download
                </DropdownMenuItem>
                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onShare(file); }}>
                    <Share2 className="mr-2 h-4 w-4" />
                    Share
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                    onClick={(e) => { e.stopPropagation(); onDelete(file); }}
                    className="text-destructive focus:text-destructive"
                >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
