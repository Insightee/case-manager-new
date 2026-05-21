import { useCallback, useEffect, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { apiUpload } from '../../lib/apiClient.js'
import { compressImageFile } from '../../lib/compressImage.js'
import './report-editor.css'

function ToolbarButton({ active, onClick, children, title }) {
  return (
    <button type="button" className={active ? 'is-active' : ''} onClick={onClick} title={title}>
      {children}
    </button>
  )
}

export function ReportEditor({
  reportId,
  initialHtml = '',
  planNextMonth = '',
  onPlanChange,
  onHtmlChange,
  disabled = false,
}) {
  const fileRef = useRef(null)
  const onHtmlChangeRef = useRef(onHtmlChange)
  onHtmlChangeRef.current = onHtmlChange

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [2, 3] } }),
      Image.configure({ inline: true, allowBase64: false }),
    ],
    content: initialHtml || '<p></p>',
    editable: !disabled,
    onUpdate: ({ editor: ed }) => {
      onHtmlChangeRef.current?.(ed.getHTML())
    },
  })

  useEffect(() => {
    if (!editor) return
    const current = editor.getHTML()
    const next = initialHtml || '<p></p>'
    if (initialHtml !== undefined && current !== next && !editor.isFocused) {
      editor.commands.setContent(next, false)
    }
  }, [editor, initialHtml])

  useEffect(() => {
    if (editor) editor.setEditable(!disabled)
  }, [editor, disabled])

  const insertImage = useCallback(
    async (file) => {
      if (!reportId || !editor) return
      const compressed = await compressImageFile(file)
      const fd = new FormData()
      fd.append('file', compressed)
      const res = await apiUpload(`/api/v1/reports/monthly/${reportId}/images`, fd)
      const path = res.url || `/api/v1/reports/images/${res.id}`
      editor.chain().focus().setImage({ src: path }).run()
    },
    [editor, reportId],
  )

  async function onPickImage(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      await insertImage(file)
    } catch (err) {
      alert(err.message || 'Could not upload image')
    }
  }

  if (!editor) return <p className="text-sm text-slate-500">Loading editor…</p>

  return (
    <div>
      <div className="report-editor__shell">
        {!disabled ? (
          <div className="report-editor__toolbar">
            <ToolbarButton
              active={editor.isActive('bold')}
              onClick={() => editor.chain().focus().toggleBold().run()}
              title="Bold"
            >
              B
            </ToolbarButton>
            <ToolbarButton
              active={editor.isActive('italic')}
              onClick={() => editor.chain().focus().toggleItalic().run()}
              title="Italic"
            >
              I
            </ToolbarButton>
            <ToolbarButton
              active={editor.isActive('heading', { level: 2 })}
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
              title="Heading"
            >
              H2
            </ToolbarButton>
            <ToolbarButton
              active={editor.isActive('bulletList')}
              onClick={() => editor.chain().focus().toggleBulletList().run()}
              title="Bullet list"
            >
              • List
            </ToolbarButton>
            <ToolbarButton
              active={editor.isActive('orderedList')}
              onClick={() => editor.chain().focus().toggleOrderedList().run()}
              title="Numbered list"
            >
              1. List
            </ToolbarButton>
            <ToolbarButton
              active={editor.isActive('blockquote')}
              onClick={() => editor.chain().focus().toggleBlockquote().run()}
              title="Quote"
            >
              “
            </ToolbarButton>
            {reportId ? (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  onChange={onPickImage}
                />
                <ToolbarButton onClick={() => fileRef.current?.click()} title="Insert image">
                  Image
                </ToolbarButton>
              </>
            ) : null}
          </div>
        ) : null}
        <EditorContent editor={editor} className="report-editor__content" />
      </div>

      <div className="report-editor__plan">
        <label>
          Plan for next month
          <textarea
            value={planNextMonth}
            onChange={(e) => onPlanChange?.(e.target.value)}
            placeholder="Goals, focus areas, and recommendations for the coming month…"
            disabled={disabled}
          />
        </label>
      </div>
    </div>
  )
}
