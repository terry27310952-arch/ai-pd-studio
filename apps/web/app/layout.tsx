import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Story Pattern Lab",
  description: "Automatic viral story radar for overseas storytime content.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
