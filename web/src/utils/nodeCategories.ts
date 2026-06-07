import type { TFunction } from 'i18next';

const NODE_CATEGORY_KEYS: Record<string, string> = {
  Alignment: 'alignment',
  Annotation: 'annotation',
  Assembly: 'assembly',
  'ChIP-Seq': 'chipSeq',
  Input: 'input',
  Metagenomics: 'metagenomics',
  Output: 'output',
  Phylogenetics: 'phylogenetics',
  'Quality Control': 'qualityControl',
  'Read Preprocessing': 'readPreprocessing',
  'RNA-Seq': 'rnaSeq',
  'Single Cell': 'singleCell',
  Utility: 'utility',
  'Variant Calling': 'variantCalling',
  Visualization: 'visualization',
};

export function nodeCategoryDisplayLabel(category: string | undefined, t: TFunction, otherLabel: string): string {
  const label = category || 'Other';
  if (label === 'Other') return otherLabel;
  const key = NODE_CATEGORY_KEYS[label];
  if (!key) return label;
  const translated = t(`nodeCategories.${key}`, { defaultValue: label });
  return typeof translated === 'string' && translated ? translated : label;
}
