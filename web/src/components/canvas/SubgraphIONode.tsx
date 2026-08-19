// Boundary panels shown inside a subgraph: 'Subgraph Inputs' on the left,
// 'Subgraph Outputs' on the right. One port row per entry in the host node's
// params.input_ports / params.output_ports, plus a '+' row — wiring from the
// inputs '+' (or to the outputs '+') creates a new port. These are canvas-only
// node types: they never appear in the node library and are never stored in
// the workflow (the canvas synthesizes them in deriveView and strips them in
// writeViewBack).
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { useTranslation } from 'react-i18next';
import { NODE_HEADER_H, NODE_PIN_H } from '../../utils/nodeLayout';
import { ADD_PORT_HANDLE } from '../../utils/subgraphView';

export interface SubgraphIONodeData extends Record<string, unknown> {
  kind: 'inputs' | 'outputs';
  ports: { name: string; type: string; connected: boolean }[];
}

function SubgraphIONodeComponent({ data, selected }: NodeProps) {
  const { t } = useTranslation();
  const { kind, ports } = data as SubgraphIONodeData;
  const isInputs = kind === 'inputs';

  return (
    <div
      className={`bio-node bio-node-shape-card bio-subgraph-io ${selected ? 'selected' : ''}`}
      style={{ ['--bio-node-color' as string]: '#6366f1' }}
      data-io-kind={kind}
    >
      <div className="bio-node-header" style={{ height: NODE_HEADER_H, background: '#6366f1' }}>
        <span className="bio-node-title">
          {isInputs ? t('canvas.subgraphInputsTitle') : t('canvas.subgraphOutputsTitle')}
        </span>
      </div>
      <div className="bio-node-io">
        <div className={isInputs ? 'bio-node-outputs' : 'bio-node-inputs'}>
          {ports.map(port => (
            <div
              className={`bio-node-port ${isInputs ? 'bio-node-port-out' : 'bio-node-port-in'}`}
              key={port.name}
              style={{ height: NODE_PIN_H }}
              title={`${port.name}: ${port.type}`}
            >
              {!isInputs && (
                <Handle
                  type="target"
                  position={Position.Left}
                  id={port.name}
                  className={`bio-handle bio-handle-in ${port.connected ? 'connected' : ''}`}
                />
              )}
              <span className="bio-node-port-label">{port.name}</span>
              {isInputs && (
                <Handle
                  type="source"
                  position={Position.Right}
                  id={port.name}
                  className={`bio-handle bio-handle-out ${port.connected ? 'connected' : ''}`}
                />
              )}
            </div>
          ))}
          {/* '+' row: drag a wire from here (inputs) or onto here (outputs) to
              create a new boundary port. */}
          <div
            className={`bio-node-port bio-subgraph-io-add ${isInputs ? 'bio-node-port-out' : 'bio-node-port-in'}`}
            style={{ height: NODE_PIN_H }}
          >
            {!isInputs && (
              <Handle type="target" position={Position.Left} id={ADD_PORT_HANDLE} className="bio-handle bio-handle-in bio-handle-add" />
            )}
            <span className="bio-node-port-label bio-subgraph-io-add-label">
              {isInputs ? t('canvas.subgraphAddInput') : t('canvas.subgraphAddOutput')}
            </span>
            {isInputs && (
              <Handle type="source" position={Position.Right} id={ADD_PORT_HANDLE} className="bio-handle bio-handle-out bio-handle-add" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const SubgraphIONode = memo(SubgraphIONodeComponent);
export default SubgraphIONode;
