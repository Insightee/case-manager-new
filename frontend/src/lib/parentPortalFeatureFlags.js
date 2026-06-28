import { isBillingModuleEnabled, isReportsModuleEnabled } from './productFeatureFlags.js'

/** Parent reports hub — hidden until VITE_ENABLE_REPORTS=true */
export const PARENT_REPORTS_COMING_SOON = !isReportsModuleEnabled()

/** Parent billing portal — hidden until VITE_ENABLE_BILLING=true */
export const PARENT_BILLING_COMING_SOON = !isBillingModuleEnabled()
