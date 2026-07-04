// Canvas overlay that draws the alignment guide lines computed by getHelperLines.
// Adapted from the official React Flow helper-lines example: it reads the live
// viewport transform + pane size from the store and paints thin lines on a
// pointer-events:none <canvas> layered over the flow.
import { useEffect, useRef } from 'react';
import { useStore, type ReactFlowState } from '@xyflow/react';

export interface HelperLinesProps {
  horizontal?: number;
  vertical?: number;
}

const selWidth = (s: ReactFlowState) => s.width;
const selHeight = (s: ReactFlowState) => s.height;
const selTransform = (s: ReactFlowState) => s.transform;

export default function HelperLines({ horizontal, vertical }: HelperLinesProps) {
  const width = useStore(selWidth);
  const height = useStore(selHeight);
  const transform = useStore(selTransform);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !width || !height) return;

    const dpi = window.devicePixelRatio || 1;
    canvas.width = width * dpi;
    canvas.height = height * dpi;
    ctx.scale(dpi, dpi);
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = '#0891b2';
    ctx.lineWidth = 1;

    if (typeof vertical === 'number') {
      const x = vertical * transform[2] + transform[0];
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    if (typeof horizontal === 'number') {
      const y = horizontal * transform[2] + transform[1];
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  }, [width, height, transform, horizontal, vertical]);

  return (
    <canvas
      ref={canvasRef}
      className="bio-helper-lines"
      style={{ width, height, position: 'absolute', top: 0, left: 0, pointerEvents: 'none', zIndex: 4 }}
    />
  );
}
