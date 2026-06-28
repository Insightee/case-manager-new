import { NeuroaffirmativeFieldHint } from './NeuroaffirmativeFieldHint.jsx'
import { CLINICAL_DOMAINS, OBSERVATION_KEY_TO_DOMAIN } from '../../lib/clinicalDomains.js'

export function ObservationDomainChecklist({ sectionKey, label, value, onChange, readOnly }) {
  const domainId = OBSERVATION_KEY_TO_DOMAIN[sectionKey]
  const domain = CLINICAL_DOMAINS.find((d) => d.id === domainId)

  return (
    <div className="cp-obs-domain-card cp-card">
      <div className="cp-card__head">
        <strong>{label}</strong>
        {domain ? <span className="cp-badge cp-badge--draft">{domain.label}</span> : null}
      </div>
      {readOnly ? (
        <p className="ic-case-clinical-body">{value || '—'}</p>
      ) : (
        <>
          <textarea
            value={value || ''}
            onChange={(e) => onChange(sectionKey, e.target.value)}
            rows={5}
            placeholder={`Observations for ${domain?.label || label}…`}
          />
          <NeuroaffirmativeFieldHint text={value} />
        </>
      )}
    </div>
  )
}
