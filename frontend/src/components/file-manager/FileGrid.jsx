import { Card, CardContent } from "@/components/ui/card"
import { FileIcon } from "./FileIcon"
import { MoreVertical, CheckCircle2, Circle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { FileActionsMenu } from "./FileActionsMenu"

export function FileGrid({ files, onFileClick, isSelectionMode, selectedFileIds, onToggleSelection, onDownload, onDelete, onShare }) {
    return (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {files.map((file) => {
                const isSelected = selectedFileIds?.has(file.id);

                return (
                    <Card
                        key={file.id}
                        className={cn(
                            "group relative cursor-pointer transition-all duration-200 shadow-none",
                            isSelected
                                ? "bg-primary/20 border-2 border-primary ring-0"
                                : "hover:bg-accent/50 border border-transparent hover:border-border hover:shadow-sm"
                        )}
                        onClick={() => {
                            if (isSelectionMode) {
                                onToggleSelection(file.id);
                            } else {
                                onFileClick(file);
                            }
                        }}
                    >
                        <CardContent className="p-4 flex flex-col items-center justify-center text-center space-y-3">
                            {/* Selection Checkbox Overlay */}
                            {isSelectionMode && (
                                <div className="absolute top-2 left-2 z-10">
                                    {isSelected ? (
                                        <CheckCircle2 className="h-5 w-5 text-primary fill-background" />
                                    ) : (
                                        <Circle className="h-5 w-5 text-muted-foreground/50 hover:text-primary transition-colors" />
                                    )}
                                </div>
                            )}

                            {/* Standard Actions (Hidden in selection mode) */}
                            {!isSelectionMode && (
                                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <FileActionsMenu
                                        file={file}
                                        onDownload={onDownload}
                                        onDelete={onDelete}
                                        onShare={onShare}
                                        onOpen={onFileClick}
                                    />
                                </div>
                            )}

                            <FileIcon type={file.type} className="h-12 w-12" />
                            <div className="w-full space-y-1">
                                <p className="font-medium truncate text-sm" title={file.name}>{file.name}</p>
                                <p className="text-xs text-muted-foreground">{file.size || (file.type === 'folder' ? `${file.items} items` : '-')}</p>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    )
}
