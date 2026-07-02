import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PitWall Agent",
  description: "Formula 1 assistant with chat, citations, and session memory.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
