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
      if (surface === 'canvas') expect(changed).not.toHaveBeenCalled();
      else expect(latest()).toEqual(['n', 'count', undefined]);
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
      const callsBeforeFocus = changed.mock.calls.length;
      fireEvent.blur(screen.getByLabelText('text'));
      if (surface === 'canvas') expect(changed).toHaveBeenCalledTimes(callsBeforeFocus);
      else expect(latest()).toEqual(['n', 'text', undefined]);
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

describe('canvas widget edits', () => {
  const widgets: NodeMetadata = {
    id: 'widgets', display_name: 'Widgets', category: 'Utility',
    input_types: { optional: {
      text: { type: 'STRING' }, content: { type: 'STRING', default: '', multiline: true },
      encoding: { type: 'STRING', default: 'utf-8' }, count: { type: 'INT', default: 4 },
      record: { type: 'JSON', default: { keep: true } }, color: { type: 'STRING', default: '#ff0000' },
      slider: { type: 'FLOAT', default: 0.5, display: 'slider', min: 0, max: 1, step: 0.1 },
    } },
  };
  function setup(params: Record<string, unknown> = {}) {
    const changed = vi.fn();
    const actions = { setParam: changed } as unknown as BioNodeActions;
    const view = (next: Record<string, unknown>) => <BioNodeActionsContext.Provider value={actions}>
      <NodeWidgets nodeId="n" meta={widgets} params={next} />
    </BioNodeActionsContext.Provider>;
    const result = render(view(params));
    return { changed, reset: (next: Record<string, unknown>) => result.rerender(view(next)) };
  }

  it('does not materialize omitted defaults on focus, blur or pointer up', () => {
    const { changed } = setup();
    for (const key of ['text', 'content', 'encoding', 'count', 'record', 'color', 'slider']) {
      const control = screen.getByLabelText(key);
      fireEvent.focus(control);
      fireEvent.pointerUp(control);
      fireEvent.blur(control);
    }
    expect(changed).not.toHaveBeenCalled();
  });

  it('preserves multiline bytes and commits real multiline edits once', () => {
    const { changed } = setup({ content: 'first\nsecond\n' });
    const content = screen.getByLabelText('content');
    expect(content.tagName).toBe('TEXTAREA');
    expect(content).toHaveValue('first\nsecond\n');
    fireEvent.blur(content);
    expect(changed).not.toHaveBeenCalled();
    fireEvent.change(content, { target: { value: 'changed\nlast\n' } });
    expect(changed).not.toHaveBeenCalled();
    fireEvent.blur(content);
    fireEvent.blur(content);
    expect(changed).toHaveBeenCalledExactlyOnceWith('n', 'content', 'changed\nlast\n', true);
  });

  it('keeps explicit empty strings and clears optional strings after edits', () => {
    const { changed } = setup({ text: 'old', content: 'old' });
    for (const key of ['text', 'content']) {
      fireEvent.change(screen.getByLabelText(key), { target: { value: '' } });
      fireEvent.blur(screen.getByLabelText(key));
    }
    expect(changed.mock.calls).toEqual([['n', 'text', undefined, true], ['n', 'content', '', true]]);
  });

  it('retains numeric parsing and color commits after real edits', () => {
    const { changed } = setup();
    fireEvent.change(screen.getByLabelText('count'), { target: { value: '7' } });
    fireEvent.blur(screen.getByLabelText('count'));
    fireEvent.change(screen.getByLabelText('color'), { target: { value: '#00ff00' } });
    fireEvent.blur(screen.getByLabelText('color'));
    expect(changed.mock.calls).toEqual([['n', 'count', 7, true], ['n', 'color', '#00ff00', true]]);
  });

  it('does not replace existing values with normalized display values on blur', () => {
    const { changed } = setup({ count: '004', color: 'red', record: { nested: [1, 2] } });
    for (const key of ['count', 'color', 'record']) fireEvent.blur(screen.getByLabelText(key));
    expect(changed).not.toHaveBeenCalled();
  });

  it('rejects invalid JSON and commits a subsequent correction', () => {
    const { changed } = setup();
    const record = screen.getByLabelText('record');
    fireEvent.change(record, { target: { value: '{broken' } });
    fireEvent.blur(record);
    expect(record).toBeInvalid();
    expect(changed).not.toHaveBeenCalled();
    fireEvent.change(record, { target: { value: '{"correct":true}' } });
    fireEvent.blur(record);
    expect(record).toBeValid();
    expect(changed).toHaveBeenCalledExactlyOnceWith('n', 'record', { correct: true }, true);
  });

  it('clears stale JSON validity after an external reset without committing', () => {
    const { changed, reset } = setup({ record: { original: true } });
    const record = screen.getByLabelText('record');
    fireEvent.change(record, { target: { value: '{broken' } });
    fireEvent.blur(record);
    expect(record).toBeInvalid();
    reset({ record: { remote: true } });
    fireEvent.blur(record);
    expect(record).toBeValid();
    expect(changed).not.toHaveBeenCalled();
  });

  it('commits sliders once for pointer interaction and on blur for keyboard interaction', () => {
    const { changed } = setup();
    const slider = screen.getByLabelText('slider');
    fireEvent.change(slider, { target: { value: '0.7' } });
    fireEvent.pointerUp(slider);
    fireEvent.blur(slider);
    expect(changed).toHaveBeenCalledExactlyOnceWith('n', 'slider', 0.7, true);
    fireEvent.change(slider, { target: { value: '0.8' } });
    fireEvent.blur(slider);
    expect(changed).toHaveBeenLastCalledWith('n', 'slider', 0.8, true);
    expect(changed).toHaveBeenCalledTimes(2);
  });

  it('resynchronizes undo, redo and remote edits without committing stale local edits', () => {
    const { changed, reset } = setup({ content: 'original\n' });
    const content = screen.getByLabelText('content');
    fireEvent.change(content, { target: { value: 'uncommitted' } });
    for (const value of ['remote\n', 'original\n', 'remote\n']) {
      reset({ content: value });
      expect(content).toHaveValue(value);
      fireEvent.blur(content);
    }
    expect(changed).not.toHaveBeenCalled();
  });
});
