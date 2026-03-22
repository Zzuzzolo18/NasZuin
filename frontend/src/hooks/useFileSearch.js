import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { apiRequest } from "@/lib/api"

/**
 * Hook for debounced file search.
 * Returns search state and handlers.
 */
export function useFileSearch(setSearchParams) {
    const [searchQuery, setSearchQuery] = useState("")
    const [searchResults, setSearchResults] = useState(null) // null = not searching
    const [isSearching, setIsSearching] = useState(false)

    // Debounced search effect
    useEffect(() => {
        if (searchQuery.trim().length < 2) {
            setSearchResults(null)
            setIsSearching(false)
            return
        }

        setIsSearching(true)
        const timer = setTimeout(async () => {
            try {
                const data = await apiRequest(`/api/files/search/?q=${encodeURIComponent(searchQuery.trim())}`)
                setSearchResults(data.files)
            } catch (error) {
                console.error('Search error:', error)
                toast.error('Search failed')
                setSearchResults([])
            } finally {
                setIsSearching(false)
            }
        }, 300)

        return () => clearTimeout(timer)
    }, [searchQuery])

    const clearSearch = useCallback(() => {
        setSearchQuery("")
        setSearchResults(null)
        setIsSearching(false)
    }, [])

    const handleSearchResultClick = useCallback((file) => {
        const folder = file.folder || ""
        clearSearch()
        if (folder) {
            setSearchParams({ path: folder })
        } else {
            setSearchParams({})
        }
    }, [clearSearch, setSearchParams])

    return {
        searchQuery,
        setSearchQuery,
        searchResults,
        isSearching,
        clearSearch,
        handleSearchResultClick,
    }
}
