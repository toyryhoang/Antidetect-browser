function getClipboardData() {
  const yPosition = window.pageYOffset || document.documentElement.scrollTop
  const el = document.createElement('input')
  el.style.position = 'absolute'
  el.style.left = '-9999px'
  el.style.top = `${yPosition}px`
  document.body.appendChild(el)
  el.focus()
  document.execCommand('paste')
  const text = el.value
  document.body.removeChild(el)
  return text
}

function getRandomTypeDelay() {
  const min = 50
  const max = 200
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function type(element, text, startIndex = 0) {
  if (startIndex < text.length) {
    const char = text.charAt(startIndex)
    const keypressEvent = new KeyboardEvent('keypress', {
      key: char,
      charCode: char.charCodeAt(),
      keyCode: char.charCodeAt(),
    })
    const inputEvent = new Event('input', { bubbles: true })

    element.value += char
    element.dispatchEvent(keypressEvent)
    element.dispatchEvent(inputEvent)

    document.dispatchEvent(keypressEvent)

    setTimeout(() => type(element, text, startIndex + 1), getRandomTypeDelay())
  }
}

if (document.activeElement) {
  const activeElement = document.activeElement
  const clipboardData = getClipboardData()

  activeElement.focus()

  setTimeout(() => type(activeElement, clipboardData), getRandomTypeDelay())
}
