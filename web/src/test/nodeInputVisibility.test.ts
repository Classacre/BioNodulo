import { describe, expect, it } from 'vitest';
import type { NodeMetadata } from '../types';
import { getVisibleInputSpecs, isNodeInputVisible } from '../utils/nodeInputVisibility';

const httpMeta: NodeMetadata = {
  id: 'http_request',
  display_name: 'HTTP Request',
  category: 'api',
  input_types: {
    required: {
      url: { type: 'STRING', default: '' },
    },
    optional: {
      body_format: { type: 'STRING', default: 'none', options: ['none', 'json', 'text', 'form'] },
      body: {
        type: 'STRING',
        displayOptions: { show: { body_format: ['json', 'text', 'form'] } },
      },
      auth_mode: { type: 'STRING', default: 'none', options: ['none', 'bearer', 'basic'] },
      bearer_token: {
        type: 'STRING',
        displayOptions: { show: { auth_mode: ['bearer'] } },
      },
      username: {
        type: 'STRING',
        displayOptions: { show: { auth_mode: ['basic'] } },
      },
      password: {
        type: 'STRING',
        displayOptions: { show: { auth_mode: ['basic'] } },
      },
    },
  },
};

describe('node input visibility metadata', () => {
  it('hides conditional inputs until their controlling parameter matches', () => {
    const visible = getVisibleInputSpecs(httpMeta, {});

    expect(Object.keys(visible.required)).toEqual(['url']);
    expect(Object.keys(visible.optional)).toEqual(['body_format', 'auth_mode']);
  });

  it('uses params and input defaults when evaluating displayOptions.show', () => {
    expect(getVisibleInputSpecs(httpMeta, { body_format: 'json' }).optional).toHaveProperty('body');
    expect(getVisibleInputSpecs(httpMeta, { auth_mode: 'bearer' }).optional).toHaveProperty('bearer_token');
    expect(getVisibleInputSpecs(httpMeta, { auth_mode: 'bearer' }).optional).not.toHaveProperty('username');
    expect(getVisibleInputSpecs(httpMeta, { auth_mode: 'basic' }).optional).toHaveProperty('username');
    expect(getVisibleInputSpecs(httpMeta, { auth_mode: 'basic' }).optional).toHaveProperty('password');
    expect(getVisibleInputSpecs(httpMeta, { auth_mode: 'basic' }).optional).not.toHaveProperty('bearer_token');
  });

  it('treats inputs without displayOptions as visible', () => {
    expect(isNodeInputVisible('body_format', httpMeta.input_types?.optional?.body_format, httpMeta, {})).toBe(true);
  });
});
