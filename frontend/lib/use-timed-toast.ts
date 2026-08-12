"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export function useTimedToast(durationMs = 1600) {
  const [isVisible, setIsVisible] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
      }
    }
  }, [])

  const showToast = useCallback(() => {
    setIsVisible(true)
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
    }
    timerRef.current = window.setTimeout(() => {
      setIsVisible(false)
      timerRef.current = null
    }, durationMs)
  }, [durationMs])

  return [isVisible, showToast] as const
}
