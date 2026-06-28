import { createPortal } from 'react-dom'

/** Render modals on document.body — avoids nested <form> submit bubbling in session log. */
export function SessionLogModalPortal({ children }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}
