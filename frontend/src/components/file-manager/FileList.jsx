import { FileIcon } from "./FileIcon"
import { MoreVertical, CheckCircle2, Circle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { FileActionsMenu } from "./FileActionsMenu"

export function FileList({ files, onFileClick, isSelectionMode, selectedFileIds, onToggleSelection, onDownload, onDelete, onShare }) {
    return (
        <div className="space-y-1">
            <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-muted-foreground border-b select-none">
                <div className={cn("col-span-6 flex items-center gap-2", isSelectionMode && "pl-8")}>Name</div>
                <div className="col-span-2">Date Modified</div>
                <div className="col-span-2">Type</div>
                <div className="col-span-2 text-right">Size</div>
            </div>
            {files.map((file) => {
                const isSelected = selectedFileIds?.has(file.id);

                return (
                    <div
                        key={file.id}
                        className={cn(
                            "group grid grid-cols-12 gap-4 px-4 py-2 items-center rounded-md cursor-pointer transition-colors duration-200",
                            isSelected
                                ? "bg-primary/20 text-primary font-medium"
                                : "hover:bg-accent/50"
                        )}
                        onClick={() => {
                            if (isSelectionMode) {
                                onToggleSelection(file.id);
                            } else {
                                onFileClick(file);
                            }
                        }}
                    >
                        <div className="col-span-6 flex items-center gap-3 overflow-hidden relative">
                            {/* Selection Checkbox (Absolute positioning to not shift layout too much, or flex) */}
                            {isSelectionMode && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2">
                                    {isSelected ? (
                                        <CheckCircle2 className="h-4 w-4 text-primary fill-background" />
                                    ) : (
                                        <Circle className="h-4 w-4 text-muted-foreground/50 hover:text-primary transition-colors" />
                                    )}
                                </div>
                            )}

                            <div className={cn("flex items-center gap-3 overflow-hidden w-full", isSelectionMode && "pl-8")}>
                                <FileIcon type={file.type} className="h-5 w-5 flex-shrink-0" />
                                <span className="truncate text-sm font-medium">{file.name}</span>
                            </div>
                        </div>
                        <div className="col-span-2 text-xs text-muted-foreground truncate">{file.date}</div>
                        <div className="col-span-2 text-xs text-muted-foreground truncate capitalize">{file.type}</div>
                        <div className="col-span-2 text-xs text-muted-foreground text-right flex items-center justify-end gap-2">
                            <span>{file.size || '-'}</span>
                            {!isSelectionMode && (
                                <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                                    <FileActionsMenu
                                        file={file}
                                        onDownload={onDownload}
                                        onDelete={onDelete}
                                        onShare={onShare}
                                        onOpen={onFileClick}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    )
}
