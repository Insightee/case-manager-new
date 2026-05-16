import { useState } from 'react'
import { ClientPortalLayout } from './ClientPortalLayout'

export function ClientSupportPage({ onSubmit }) {
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(event) {
    event.preventDefault()
    if (!subject.trim() || !message.trim()) {
      return
    }

    onSubmit({ subject: subject.trim(), message: message.trim() })
    setSubmitted(true)
    setSubject('')
    setMessage('')
  }

  return (
    <ClientPortalLayout
      title="Support Request"
      subtitle="Raise a non-sensitive concern to your case manager and support team."
      actionLabel="View open requests"
    >
      <section className="card client-support">
        <div className="card-head">
          <h3>Submit Request</h3>
        </div>
        <form onSubmit={handleSubmit}>
          <input
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="Subject"
          />
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Describe your concern"
            rows={5}
          />
          <button type="submit">Submit request</button>
        </form>
        {submitted ? <p className="client-support__success">Request submitted successfully.</p> : null}
      </section>
    </ClientPortalLayout>
  )
}
