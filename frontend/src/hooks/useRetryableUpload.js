import { useCallback, useState } from 'react'

/**
 * Tracks multipart upload attempts with retry for a single file slot.
 */
export function useRetryableUpload() {
  const [state, setState] = useState(null)

  const runUpload = useCallback(async (file, uploadFn) => {
    setState({ file, status: 'uploading', error: null })
    try {
      const result = await uploadFn(file)
      setState({ file, status: 'done', error: null, result })
      return result
    } catch (err) {
      setState({
        file,
        status: 'failed',
        error: err?.message || 'Upload failed',
      })
      throw err
    }
  }, [])

  const retry = useCallback(
    async (uploadFn) => {
      if (!state?.file) return
      return runUpload(state.file, uploadFn)
    },
    [state?.file, runUpload],
  )

  const clear = useCallback(() => setState(null), [])

  return { state, runUpload, retry, clear, setState }
}
