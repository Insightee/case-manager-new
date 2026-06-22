import { CreateGoalModal } from '../goals-strategy/CreateGoalModal.jsx'

/** Session log overlay — delegates to shared CreateGoalModal. */
export function CreateGoalOverlay(props) {
  return <CreateGoalModal {...props} />
}
