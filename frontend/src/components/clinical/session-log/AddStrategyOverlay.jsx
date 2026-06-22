import { CreateStrategyModal } from '../goals-strategy/CreateStrategyModal.jsx'

/** Session log overlay — delegates to shared CreateStrategyModal. */
export function AddStrategyOverlay(props) {
  return <CreateStrategyModal {...props} />
}
