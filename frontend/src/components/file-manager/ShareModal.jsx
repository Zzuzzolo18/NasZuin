import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Copy, Check, Link } from "lucide-react";
import { toast } from "sonner";
import { fetchApi } from "@/lib/api";

export function ShareModal({ file, isOpen, onClose }) {
    const [loading, setLoading] = useState(false);
    const [shareLink, setShareLink] = useState("");
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (isOpen && file) {
            setShareLink("");
            setCopied(false);
            generateLink();
        }
    }, [isOpen, file]);

    const generateLink = async () => {
        setLoading(true);
        try {
            const response = await fetchApi('/api/files/share/create/', {
                method: 'POST',
                body: JSON.stringify({ file_id: file.id })
            });

            if (!response.ok) {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to generate link');
                } else {
                    throw new Error(`Server error: ${response.status} ${response.statusText}`);
                }
            }

            const data = await response.json();
            setShareLink(data.link);
        } catch (error) {
            console.error("Share error:", error);
            toast.error(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(shareLink).then(() => {
            setCopied(true);
            toast.success("Link copied to clipboard");
            setTimeout(() => setCopied(false), 2000);
        }).catch(() => {
            toast.error("Could not copy — try selecting and copying manually");
        });
    };

    if (!file) return null;

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Share "{file.name}"</DialogTitle>
                    <DialogDescription>
                        Anyone with this link will be able to view this file.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex items-center space-x-2">
                    <div className="grid flex-1 gap-2">
                        <Label htmlFor="link" className="sr-only">
                            Link
                        </Label>
                        <Input
                            id="link"
                            readOnly
                            value={shareLink}
                            placeholder={loading ? "Generating link..." : "Link will appear here"}
                        />
                    </div>
                    <Button type="submit" size="sm" className="px-3" onClick={handleCopy} disabled={!shareLink}>
                        <span className="sr-only">Copy</span>
                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                </div>
                <DialogFooter className="sm:justify-start">
                    <Button
                        type="button"
                        variant="secondary"
                        onClick={onClose}
                    >
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
