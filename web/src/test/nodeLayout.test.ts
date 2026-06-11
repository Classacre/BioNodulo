import { describe, expect, it } from 'vitest';
import type { NodeMetadata } from '../types';
import {
  NODE_WIDGET_BOTTOM_PAD,
  NODE_WIDGET_ROW_H,
  calcRegularNodeHeight,
  getInteractiveWidgetEntries,
  getWidgetBlockTop,
} from '../utils/nodeLayout';

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
