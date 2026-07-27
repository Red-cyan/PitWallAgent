"use client";

import { FlaskConical, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function WorkspaceNav() {
  const pathname = usePathname();
  return (
    <nav className="workspace-nav" aria-label="Workspace navigation">
      <Link className="brand" href="/">
        <span className="brand-mark">PW</span>
        <span>PitWall Agent</span>
      </Link>
      <div className="nav-tabs">
        <Link className="nav-tab" data-active={pathname === "/"} href="/">
          <MessageSquareText size={16} />
          Chat
        </Link>
        <Link className="nav-tab" data-active={pathname.startsWith("/rag")} href="/rag">
          <FlaskConical size={16} />
          RAG Lab
        </Link>
      </div>
    </nav>
  );
}
