import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

function Stars({ rating }) {
  const n = Math.round(rating || 0)
  return (
    <span className="therapist-profile__stars" aria-label={`${n} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} style={{ opacity: i <= n ? 1 : 0.25 }}>
          ★
        </span>
      ))}
    </span>
  )
}

function formatReviewDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', year: 'numeric', day: 'numeric' })
}

export function TherapistReviewsSection({ apiPath = '/api/v1/therapist/reviews', title = 'Client reviews' }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    apiFetch(apiPath)
      .then(setData)
      .catch((err) => setError(err.message || 'Could not load reviews'))
      .finally(() => setLoading(false))
  }, [apiPath])

  const summary = data?.summary
  const reviews = data?.reviews || []

  return (
    <section className="therapist-profile__card">
      <div className="therapist-profile__card-head">
        <h2>{title}</h2>
        {summary?.average_rating != null ? (
          <span className="therapist-profile__rating-pill">
            <Stars rating={summary.average_rating} />
            {summary.average_rating} · {summary.total_count} review{summary.total_count === 1 ? '' : 's'}
          </span>
        ) : null}
      </div>
      <p className="therapist-profile__card-hint">
        Families rate sessions after approved session updates. Reviews marked public can appear on a future public
        profile page.
        {summary?.public_count > 0 ? ` ${summary.public_count} shared publicly.` : ''}
      </p>

      {error ? <p className="therapist-profile__alert therapist-profile__alert--error">{error}</p> : null}
      {loading ? <p className="therapist-profile__reviews-empty">Loading reviews…</p> : null}
      {!loading && !error && reviews.length === 0 ? (
        <p className="therapist-profile__reviews-empty">No client reviews yet. They appear after families rate a session.</p>
      ) : null}

      {!loading && !error
        ? reviews.map((r) => (
            <article key={r.id} className="therapist-profile__review">
              <div className="therapist-profile__review-head">
                <div>
                  {r.rating ? <Stars rating={r.rating} /> : null}
                  <p className="therapist-profile__review-meta">
                    {r.child_name ? `${r.child_name}` : 'Family'}
                    {r.scheduled_date ? ` · ${formatReviewDate(r.scheduled_date)}` : ''}
                    {r.feedback_at ? ` · ${formatReviewDate(r.feedback_at)}` : ''}
                  </p>
                </div>
                <span
                  className={
                    r.is_public ? 'therapist-profile__badge' : 'therapist-profile__badge therapist-profile__badge--private'
                  }
                >
                  {r.is_public ? 'Public' : 'Private'}
                </span>
              </div>
              {r.feedback ? <p className="therapist-profile__review-body">{r.feedback}</p> : null}
            </article>
          ))
        : null}
    </section>
  )
}
