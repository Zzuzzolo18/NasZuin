import { File, Folder, FileImage, FileText, FileVideo, FileAudio, FileCode, FileArchive } from "lucide-react"

export function FileIcon({ type, className }) {
    const props = { className }

    switch (type) {
        case "folder":
            return <Folder {...props} className={`${className} text-blue-500 fill-blue-500/20`} />
        case "image":
            return <FileImage {...props} className={`${className} text-purple-500`} />
        case "video":
            return <FileVideo {...props} className={`${className} text-red-500`} />
        case "audio":
            return <FileAudio {...props} className={`${className} text-yellow-500`} />
        case "text":
        case "document":
            return <FileText {...props} className={`${className} text-gray-500`} />
        case "code":
            return <FileCode {...props} className={`${className} text-green-500`} />
        case "archive":
            return <FileArchive {...props} className={`${className} text-orange-500`} />
        default:
            return <File {...props} className={`${className} text-gray-400`} />
    }
}
