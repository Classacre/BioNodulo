// React Flow devtools — a dev-only debugging overlay adapted from the official
// @xyflow devtools example. Rendered ONLY when import.meta.env.DEV is true, so it
// costs nothing in the production editor bundle.
//
// - NodeInspector: draws each node's id / position / size next to it, in a
//   <ViewportPortal> so the labels pan & zoom with the graph.
// - ViewportLogger: shows the live viewport (x / y / zoom) in a corner <Panel>.
import { useViewport, useNodes, ViewportPortal, Panel } from '@xyflow/react';

function NodeInspector() {
  const nodes = useNodes();
  return (
    <ViewportPortal>
      <div className="bio-devtools-nodes">
        {nodes.map((node) => {
          const x = node.position.x;
          const y = node.position.y;
          const w = node.measured?.width ?? node.width ?? 0;
          const h = node.measured?.height ?? node.height ?? 0;
          return (
            <div
              key={node.id}
              className="bio-devtools-node"
              style={{ position: 'absolute', transform: `translate(${x}px, ${y - 16}px)` }}
            >
              <div>id: {node.id}</div>
              <div>{Math.round(x)}, {Math.round(y)} · {Math.round(w)}×{Math.round(h)}</div>
            </div>
          );
        })}
      </div>
    </ViewportPortal>
  );
}

function ViewportLogger() {
  const vp = useViewport();
  return (
    <Panel position="bottom-center" className="bio-devtools-viewport">
      x {vp.x.toFixed(0)} · y {vp.y.toFixed(0)} · zoom {vp.zoom.toFixed(2)}
    </Panel>
  );
}

export default function Devtools() {
  return (
    <>
      <NodeInspector />
      <ViewportLogger />
    </>
  );
}
