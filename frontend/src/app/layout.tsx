import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { BusinessProvider } from "@/lib/business-context";
import { TopNav } from "@/components/TopNav";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DecisionGPT",
  description: "AI-powered decision support for Indian SMEs.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <BusinessProvider>
          <TopNav />
          <main className="flex-1">{children}</main>
        </BusinessProvider>
      </body>
    </html>
  );
}
