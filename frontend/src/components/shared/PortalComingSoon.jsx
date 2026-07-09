import './portal-coming-soon.css'

const COPY = {
  therapistReports: {
    title: 'Reports — Coming Soon',
    body: 'We’re improving the report-writing flow so it is faster, clearer, and clinically reviewed. For now, please continue using the current approved process shared by your case manager.',
  },
  therapistBilling: {
    title: 'Billing — Coming Soon',
    body: 'Billing and payout details are being updated. Please contact the admin team for current billing-related queries.',
  },
  parentReports: {
    title: 'Reports — Coming Soon',
    body: 'Approved reports will appear here once the new parent report view is launched. Until then, your case team will continue sharing reports through the existing process.',
  },
  parentBilling: {
    title: 'Billing — Coming Soon',
    body: 'Your billing view is being upgraded. Please contact the Insighte team for payment or invoice details.',
  },
  adminReports: {
    title: 'Reports — Coming Soon',
    body: 'The new review and approval workflow is under development. Existing reporting operations should continue through the current internal process.',
  },
  adminBilling: {
    title: 'Billing — Coming Soon',
    body: 'The billing module is being rebuilt to match the updated service and session logic.',
  },
  clinicalBrain: {
    title: 'Clinical Brain — Coming Soon',
    body: 'Goal bank, strategy intelligence, and review queues are in staged rollout. Your case workflows are unchanged.',
  },
}

export function PortalComingSoon({ variant = 'generic', title, body, className = '' }) {
  const preset = COPY[variant] || {}
  const heading = title || preset.title || 'Coming Soon'
  const message = body || preset.body || 'This area is being prepared for a future release.'

  return (
    <div className={`portal-coming-soon forest-light ${className}`.trim()} role="status">
      <div className="portal-coming-soon__card">
        <p className="portal-coming-soon__eyebrow">InsighteCase</p>
        <h1 className="portal-coming-soon__title">{heading}</h1>
        <p className="portal-coming-soon__body">{message}</p>
      </div>
    </div>
  )
}
