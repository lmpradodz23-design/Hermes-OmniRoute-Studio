// Pre-paint the themed background before the app bundle loads. Keeping this
// in a same-origin file preserves a strict Content Security Policy.
try {
  let background = localStorage.getItem('hermes-boot-background')
  let scheme = localStorage.getItem('hermes-boot-color-scheme')

  if (!background) {
    const dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    background = dark ? '#111111' : '#f7f7f7'
    scheme = dark ? 'dark' : 'light'
  }

  document.documentElement.style.backgroundColor = background

  if (scheme === 'dark' || scheme === 'light') {
    document.documentElement.style.colorScheme = scheme
  }
} catch {
  // localStorage may be unavailable during an early or restricted launch.
}
