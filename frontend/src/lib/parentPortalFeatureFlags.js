import { isBillingModuleEnabled, isReportsModuleEnabled } from './productFeatureFlags.js'

export const PARENT_REPORTS_COMING_SOON = !isReportsModuleEnabled()

export const PARENT_BILLING_COMING_SOON = !isBillingModuleEnabled()
