import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NodeWidgets from '../components/canvas/NodeWidgets';
import NodePropertiesDialog from '../components/canvas/NodePropertiesDialog';
import { BioNodeActionsContext, type BioNodeActions } from '../components/canvas/bioNodeActions';
import type { NodeMetadata } from '../types';
import { defaultsFor } from '../utils';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
afterEach(cleanup);

const meta: NodeMetadata = {
  id: 'generated', display_name: 'Generated tool', category: 'Generated',
  input_types: { optional: {
    count: { type: 'INT' }, choice: { type: 'STRING', options: ['alpha', 'beta'] },
    record: { type: 'JSON' }, enabled: { type: 'BOOLEAN' }, pinned: { type: 'INT', default: 0 }, text: { type: 'STRING' },
    nullable_flag: { type: 'BOOLEAN', default: null },
  } },
};

describe('generated option defaults', () => {
  it('only initializes optional values explicitly declared by the tool', () => {
    expect(defaultsFor(meta)).toEqual({ pinned: 0, nullable_flag: null });
  });

  for (const surface of ['canvas', 'properties']) {
    it(`preserves unset, explicit zero, false and structured values in ${surface}`, () => {
      const changed = vi.fn();
      if (surface === 'canvas') {
        const actions = { setParam: changed } as unknown as BioNodeActions;
        render(<BioNodeActionsContext.Provider value={actions}>
          <NodeWidgets nodeId="n" meta={meta} params={defaultsFor(meta)} />
        </BioNodeActionsContext.Provider>);
      } else {
        render(<NodePropertiesDialog node={{ id: 'n', type: 'generated', params: defaultsFor(meta) }}
          objectInfo={{ generated: meta }} onRename={vi.fn()} onClose={vi.fn()} onParamChange={changed} />);
      }
      const latest = () => changed.mock.calls[changed.mock.calls.length - 1]?.slice(0, 3);
      const count = screen.getByLabelText('count');
      expect(count).toHaveValue(null);
      fireEvent.blur(count);
      expect(latest()).toEqual(['n', 'count', undefined]);
      fireEvent.change(count, { target: { value: '0' } });
      fireEvent.blur(count);
      expect(latest()).toEqual(['n', 'count', 0]);
      fireEvent.change(count, { target: { value: '' } });
      fireEvent.blur(count);
      expect(latest()).toEqual(['n', 'count', undefined]);
      expect(screen.getByLabelText('choice')).toHaveValue('');
      expect(screen.getByLabelText('nullable_flag')).toHaveValue('');
      fireEvent.change(screen.getByLabelText('enabled'), { target: { value: 'false' } });
      expect(latest()).toEqual(['n', 'enabled', false]);
      const record = screen.getByLabelText('record');
      fireEvent.change(record, { target: { value: '{"forward":true}' } });
      fireEvent.blur(record);
      expect(latest()).toEqual(['n', 'record', { forward: true }]);
      fireEvent.change(record, { target: { value: '' } });
      fireEvent.blur(record);
      expect(latest()).toEqual(['n', 'record', undefined]);
      expect(record).toBeValid();
      fireEvent.blur(screen.getByLabelText('text'));
      expect(latest()).toEqual(['n', 'text', undefined]);
    });
  }

  it('resynchronizes property fields after an external reset before blur', () => {
    const changed = vi.fn();
    const props = { objectInfo: { generated: meta }, onRename: vi.fn(), onClose: vi.fn(), onParamChange: changed };
    const { rerender } = render(<NodePropertiesDialog {...props}
      node={{ id: 'n', type: 'generated', params: { count: 9, record: { forward: true }, text: 'old' } }} />);
    rerender(<NodePropertiesDialog {...props} node={{ id: 'n', type: 'generated', params: {} }} />);
    expect(screen.getByLabelText('count')).toHaveValue(null);
    expect(screen.getByLabelText('record')).toHaveValue('');
    expect(screen.getByLabelText('text')).toHaveValue('');
    fireEvent.blur(screen.getByLabelText('count'));
    expect(changed).toHaveBeenLastCalledWith('n', 'count', undefined);
  });
});
