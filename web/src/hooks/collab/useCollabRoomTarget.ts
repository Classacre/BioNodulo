import { useAtom } from 'jotai';
import { requestedWorkflowIdAtom } from '../../state/appAtoms';

/** Explicit room intent gates connection; it never changes document identity. */
export function useCollabRoomTarget(activeWorkflowId: string | null | undefined) {
  const [requestedWorkflowId, setRequestedWorkflowId] = useAtom(requestedWorkflowIdAtom);
  return {
    requestedWorkflowId,
    setRequestedWorkflowId,
    requestedWorkflowPending: Boolean(requestedWorkflowId && activeWorkflowId !== requestedWorkflowId),
  };
}
