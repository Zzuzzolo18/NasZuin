import { ChevronRight, Home } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function FileBreadcrumb({ path, onNavigate }) {
    return (
        <nav className="flex items-center text-sm text-muted-foreground">
            <button
                onClick={() => onNavigate({ name: 'Home', path: '' })}
                className="hover:text-primary transition-colors font-medium px-1"
            >
                Home
            </button>
            {path.map((item, index) => (
                <div key={item.path} className="flex items-center">
                    <span className="mx-1">/</span>
                    <button
                        onClick={() => onNavigate(item)}
                        className={cn(
                            "hover:text-primary transition-colors px-1",
                            index === path.length - 1 && "text-foreground font-medium pointer-events-none"
                        )}
                    >
                        {item.name}
                    </button>
                </div>
            ))}
        </nav>
    )
}
