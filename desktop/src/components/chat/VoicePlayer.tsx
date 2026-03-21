import { useState, useRef, useEffect } from 'react'
import { Play, Pause } from 'lucide-react'

interface VoicePlayerProps {
  src: string
  duration?: number | null
}

const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export const VoicePlayer = ({ src, duration }: VoicePlayerProps) => {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [totalDuration, setTotalDuration] = useState(duration ?? 0)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onDurationChange = () => setTotalDuration(audio.duration)
    const onEnded = () => { setIsPlaying(false); setCurrentTime(0) }

    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('durationchange', onDurationChange)
    audio.addEventListener('ended', onEnded)
    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('durationchange', onDurationChange)
      audio.removeEventListener('ended', onEnded)
    }
  }, [])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      void audio.play()
      setIsPlaying(true)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return
    const t = Number(e.target.value)
    audio.currentTime = t
    setCurrentTime(t)
  }

  const progress = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0

  return (
    <div className="voice-player">
      <audio ref={audioRef} src={src} preload="metadata" />

      <button
        className="voice-play-btn"
        onClick={togglePlay}
        aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}
      >
        {isPlaying ? <Pause size={14} /> : <Play size={14} />}
      </button>

      <div className="voice-track">
        <input
          type="range"
          className="voice-range"
          min={0}
          max={totalDuration || 0}
          step={0.1}
          value={currentTime}
          onChange={handleSeek}
          style={{ '--progress': `${progress}%` } as React.CSSProperties}
        />
        <div className="voice-waveform">
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              className="voice-bar"
              style={{
                height: `${30 + Math.sin(i * 0.8) * 20}%`,
                opacity: (i / 20) * 100 < progress ? 1 : 0.35,
              }}
            />
          ))}
        </div>
      </div>

      <span className="voice-time">
        {isPlaying || currentTime > 0
          ? formatDuration(currentTime)
          : formatDuration(totalDuration)}
      </span>

      <style>{`
        .voice-player {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 2px;
          min-width: 180px;
          max-width: 240px;
        }
        .voice-play-btn {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--color-primary);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          transition: background 0.15s;
        }
        .voice-play-btn:hover { background: var(--color-primary-hover); }
        .voice-track {
          flex: 1;
          position: relative;
          height: 28px;
          display: flex;
          align-items: center;
        }
        .voice-range {
          position: absolute;
          inset: 0;
          width: 100%;
          opacity: 0;
          cursor: pointer;
          z-index: 1;
          height: 100%;
        }
        .voice-waveform {
          display: flex;
          align-items: center;
          gap: 2px;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }
        .voice-bar {
          flex: 1;
          background: var(--color-primary);
          border-radius: 2px;
          transition: opacity 0.1s;
        }
        .voice-time {
          font-size: 11px;
          color: var(--color-text-secondary);
          white-space: nowrap;
          flex-shrink: 0;
          min-width: 32px;
        }
      `}</style>
    </div>
  )
}
