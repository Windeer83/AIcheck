import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 事实核查工作台",
  description: "AI 输出事实核查与可信度评估系统 MVP"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

