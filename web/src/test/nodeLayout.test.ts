import { describe, expect, it } from 'vitest';
import type { NodeMetadata } from '../types';
import {
  NODE_WIDGET_BOTTOM_PAD,
  NODE_WIDGET_ROW_H,
  calcRegularNodeHeight,
  getInteractiveWidgetEntries,
  getWidgetBlockTop,
  isColorParam,
  toHexColor,
} from '../utils/nodeLayout';

describe('color param detection', () => {
  it('treats *color/*colour STRING params and display:color as colour pickers', () => {
    expect(isColorParam('color', { type: 'STRING' })).toBe(true);
    expect(isColorParam('up_color', { type: 'STRING' })).toBe(true);
    expect(isColorParam('border_colour', { type: 'STRING' })).toBe(true);
    expect(isColorParam('fill', { type: 'STRING', display: 'color' })).toBe(true);
  });

  it('leaves non-colour and non-string params alone', () => {
    expect(isColorParam('title', { type: 'STRING' })).toBe(false);
    expect(isColorParam('count', { type: 'INT' })).toBe(false);
    expect(isColorParam('color', { type: 'STRING', options: ['a', 'b'] })).toBe(false);
    expect(isColorParam('color', { type: 'STRING', forceInput: true })).toBe(false);
  });

  it('coerces named and short-hex colours to #rrggbb', () => {
    expect(toHexColor('steelblue')).toBe('#4682b4');
    expect(toHexColor('#FFF')).toBe('#ffffff');
    expect(toHexColor('#1A2B3C')).toBe('#1a2b3c');
    expect(toHexColor('not-a-color')).toBe('#4682b4');
  });
});

const validatorLikeMeta: NodeMetadata = {
  id: 'data_validator',
  display_name: 'Data Validator',
  category: 'workflow',
  input_types: {
    required: {
      input: { type: 'ANY' },
    },
    optional: {
      expected_format: { type: 'STRING', options: ['auto', 'fasta', 'fastq'], default: 'auto' },
      min_size_bytes: { type: 'INT', default: 0 },
      max_size_bytes: { type: 'INT', default: 0 },
      required_fields: { type: 'STRING', default: '' },
      min_records: { type: 'INT', default: 0 },
      checksum_expected: { type: 'STRING', default: '' },
      fail_on_error: { type: 'BOOLEAN', default: true },
    },
  },
  return_types: ['ANY', 'BOOLEAN', 'JSON', 'FILE'],
  return_names: ['passthrough', 'passed', 'validation_report', 'report_file'],
};

describe('node layout metrics', () => {
  it('sizes a node tall enough to contain every DOM widget row', () => {
    const params = {
      expected_format: 'fasta',
      min_size_bytes: 1,
      max_size_bytes: 0,
      required_fields: '',
      min_records: 1,
      checksum_expected: '',
      fail_on_error: true,
    };

    const widgets = getInteractiveWidgetEntries(validatorLikeMeta, params);
    const height = calcRegularNodeHeight(validatorLikeMeta, params);
    const widgetTop = getWidgetBlockTop(
      Object.keys(validatorLikeMeta.input_types?.required ?? {}).length
        + Object.keys(validatorLikeMeta.input_types?.optional ?? {}).length,
      validatorLikeMeta.return_types?.length ?? 0,
    );
    const lastWidgetBottom = widgetTop + widgets.length * NODE_WIDGET_ROW_H;

    expect(widgets.map(widget => widget.key)).toEqual([
      'expected_format',
      'min_size_bytes',
      'max_size_bytes',
      'required_fields',
      'min_records',
      'checksum_expected',
      'fail_on_error',
    ]);
    expect(height).toBeGreaterThanOrEqual(lastWidgetBottom + NODE_WIDGET_BOTTOM_PAD);
  });
});
