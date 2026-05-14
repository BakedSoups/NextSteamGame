import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

export const metadata: Metadata = {
  title: 'Game Recommendation Lab',
  description: 'Search, inspect, and tune game recommendations with precision controls',
  icons: {
    icon: '/controller-icon.png',
    apple: '/controller-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark bg-background">
      <body className="font-sans antialiased">{children}</body>
    </html>
  )
}
