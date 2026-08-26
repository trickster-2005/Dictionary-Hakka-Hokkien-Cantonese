interface Props {
  src: string
  label?: string
}

/** Cross-origin <audio>.play() proved unreliable for these government-hosted
 * files (silently never starts), so this just opens/downloads the file
 * directly instead of trying to play it inline — a plain navigation always
 * works regardless of CORS, and most browsers show a native player for a
 * direct .mp3 link if the download attribute itself gets ignored. */
export function PlayButton({ src, label = '播放/下載發音' }: Props) {
  return (
    <a className="play-button" href={src} download target="_blank" rel="noreferrer" aria-label={label}>
      🔊
    </a>
  )
}
