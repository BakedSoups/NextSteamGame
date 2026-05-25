import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const SITE_URL = 'https://nextsteamgame.com'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Find Similar Steam Games | NextSteamGame',
    template: '%s | NextSteamGame',
  },
  description:
    'Find similar Steam games by mechanics, tags, structure, genre, and music. Start with a game you love and discover what to play next.',
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: 'Find Similar Steam Games | NextSteamGame',
    description:
      'Find similar Steam games by mechanics, tags, structure, genre, and music.',
    url: SITE_URL,
    siteName: 'NextSteamGame',
    type: 'website',
    images: [
      {
        url: '/controller-icon.png',
        width: 512,
        height: 512,
        alt: 'NextSteamGame',
      },
    ],
  },
  twitter: {
    card: 'summary',
    title: 'Find Similar Steam Games | NextSteamGame',
    description:
      'Find similar Steam games by mechanics, tags, structure, genre, and music.',
    images: ['/controller-icon.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
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
