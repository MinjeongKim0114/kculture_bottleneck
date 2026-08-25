import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "한류 인지-행동 Gap 대시보드",
  description: "23개국의 한류 경험, 인식, 방한의향 사이 관찰된 패턴과 Gap을 탐색하는 대시보드",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
