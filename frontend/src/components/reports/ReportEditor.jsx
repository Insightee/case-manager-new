import { useCallback, useEffect, useRef, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { apiFetchBlob, apiUpload } from '../../lib/apiClient.js'
import { compressImageFile } from '../../lib/compressImage.js'
import { dehydrateReportImages, hydrateReportImages } from '../../lib/reportHtml.js'
import { ReportImageExtension } from '../../lib/reportImageExtension.js'
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
  documentVersion = 0,
  initialHtml = '',
  planNextMonth = '',
  onPlanChange,
  onHtmlChange,
  disabled = false,
}) {
  const fileRef = useRef(null)
  const onHtmlChangeRef = useRef(onHtmlChange)
  onHtmlChangeRef.current = onHtmlChange
  const lastAppliedDocRef = useRef(-1)
  const [uploadError, setUploadError] = useState(null)
  const [pendingFile, setPendingFile] = useState(null)
  const [editorReady, setEditorReady] = useState(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [2, 3] } }),
      ReportImageExtension.configure({ inline: true, allowBase64: false }),
    ],
    content: '<p></p>',
    editable: !disabled,
    onUpdate: ({ editor: ed }) => {
      onHtmlChangeRef.current?.(dehydrateReportImages(ed.getHTML()))
    },
  })

  useEffect(() => {
    lastAppliedDocRef.current = -1
  }, [reportId])

  useEffect(() => {
    if (!editor) return
    setEditorReady(true)
  }, [editor])

  const initialHtmlRef = useRef(initialHtml)
  initialHtmlRef.current = initialHtml

  useEffect(() => {
    if (!editor || !editorReady || documentVersion < 1) return
    if (documentVersion === lastAppliedDocRef.current) return
    let cancelled = false
    const runForVersion = documentVersion
    const sourceHtml = initialHtmlRef.current || '<p></p>'
    ;(async () => {
      const displayHtml = await hydrateReportImages(sourceHtml)
      if (cancelled || runForVersion !== documentVersion) return
      if (!editor.isDestroyed) {
        editor.commands.setContent(displayHtml, false)
        lastAppliedDocRef.current = documentVersion
      }
    })()
    return () => {
      cancelled = true
    }
  }, [editor, editorReady, documentVersion])

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
      const apiPath = res.url || `/api/v1/reports/images/${res.id}`
      const blob = await apiFetchBlob(apiPath)
      const blobUrl = URL.createObjectURL(blob)
      editor.chain().focus().setImage({ src: blobUrl, dataApiSrc: apiPath }).run()
      queueMicrotask(() => {
        if (!editor.isDestroyed) {
          onHtmlChangeRef.current?.(dehydrateReportImages(editor.getHTML()))
        }
      })
    },
    [editor, reportId],
  )

  async function onPickImage(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setPendingFile(file)
    setUploadError(null)
    try {
      await insertImage(file)
      setPendingFile(null)
    } catch (err) {
      setUploadError(err.message || 'Could not upload image')
    }
  }

  async function retryUpload() {
    if (!pendingFile) return
    setUploadError(null)
    try {
      await insertImage(pendingFile)
      setPendingFile(null)
    } catch (err) {
      setUploadError(err.message || 'Could not upload image')
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
                  accept="image/jpeg,image/png,image/webp"
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
        {uploadError ? (
          <div className="report-editor__upload-error" role="alert" style={{ padding: '8px 12px', marginBottom: 8 }}>
            <span>{uploadError}</span>
            {pendingFile ? (
              <button type="button" className="btn btn-secondary btn-sm" onClick={retryUpload} style={{ marginLeft: 8 }}>
                Retry upload
              </button>
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
