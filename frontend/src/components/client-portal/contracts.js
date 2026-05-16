/**
 * @typedef {Object} ParentCaseSummary
 * @property {string} caseId
 * @property {string} childName
 * @property {string} serviceType
 * @property {string} caseManager
 * @property {string} therapist
 * @property {string} status
 * @property {string} latestApprovedReportMonth
 * @property {'pending'|'acknowledged'} iepAcknowledgementStatus
 */

/**
 * @typedef {Object} ApprovedReport
 * @property {string} id
 * @property {string} caseId
 * @property {string} childName
 * @property {string} month
 * @property {'approved'} status
 * @property {string} publishedAt
 * @property {string} summary
 * @property {string[]} goalsCovered
 */

/**
 * @typedef {Object} IepAckStatus
 * @property {string} id
 * @property {string} caseId
 * @property {string} childName
 * @property {string} version
 * @property {'pending'|'acknowledged'} status
 * @property {string} issuedAt
 * @property {string|null} acknowledgedAt
 */

/**
 * @typedef {Object} BillingSnapshot
 * @property {string} id
 * @property {string} caseId
 * @property {string} month
 * @property {number} amountINR
 * @property {'paid'|'queried'|'pending'} status
 * @property {string} updatedAt
 */

/**
 * @typedef {Object} ParentNotification
 * @property {string} id
 * @property {string} title
 * @property {string} detail
 * @property {string} createdAt
 */

export const parentApiContract = {
  getCases: 'GET /parent/cases',
  getReports: 'GET /parent/reports',
  getReportById: 'GET /parent/reports/:id',
  getIepStatus: 'GET /parent/iep-status',
  acknowledgeIep: 'POST /parent/iep-acknowledgements',
  getBillingSummaries: 'GET /parent/billing-summaries',
  submitSupportRequest: 'POST /parent/support-requests',
}
