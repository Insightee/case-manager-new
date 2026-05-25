import { mergeAttributes } from '@tiptap/core'
import Image from '@tiptap/extension-image'

const REPORT_IMAGE_RE = /\/api\/v1\/reports\/images\/\d+/

/** Tiptap image: display blob src in editor, serialize API path in saved HTML. */
export const ReportImageExtension = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      dataApiSrc: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-api-src'),
      },
    }
  },
  renderHTML({ HTMLAttributes }) {
    const apiSrc = HTMLAttributes.dataApiSrc
    const attrs = { ...HTMLAttributes }
    if (apiSrc && REPORT_IMAGE_RE.test(apiSrc)) {
      attrs.src = apiSrc
      attrs['data-api-src'] = apiSrc
    }
    return ['img', mergeAttributes(this.options.HTMLAttributes, attrs)]
  },
})
