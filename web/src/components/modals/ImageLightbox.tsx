import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '../ui/Icon';

export interface LightboxImage {
  src: string;
  alt: string;
  filename: string;
}

interface ImageLightboxProps {
  images: LightboxImage[];
  initialIndex: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function ImageLightbox({ images, initialIndex, isOpen, onClose }: ImageLightboxProps) {
  const { t } = useTranslation();
  const [index, setIndex] = useState(initialIndex);
  const [zoomed, setZoomed] = useState(false);
  const [loading, setLoading] = useState(true);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setIndex(initialIndex);
      setZoomed(false);
      setLoading(true);
    }
  }, [isOpen, initialIndex]);

  const current = images[index];
  const total = images.length;

  const goPrev = useCallback(() => {
    if (total <= 1) return;
    setIndex(i => (i - 1 + total) % total);
    setZoomed(false);
    setLoading(true);
  }, [total]);

  const goNext = useCallback(() => {
    if (total <= 1) return;
    setIndex(i => (i + 1) % total);
    setZoomed(false);
    setLoading(true);
  }, [total]);

  const handleSave = useCallback(() => {
    if (!current) return;
    const a = document.createElement('a');
    a.href = current.src;
    a.download = current.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [current]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') goPrev();
      else if (e.key === 'ArrowRight') goNext();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose, goPrev, goNext]);

  if (!isOpen || !current) return null;

  return (
    <div
      className="lightbox-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Close button (top-right) */}
      <button className="lightbox-close" onClick={onClose} title={t('imageLightbox.closeEsc')} aria-label={t('imageLightbox.closeEsc')}>
        <Icon name="close" size={20} />
      </button>

      {/* Prev arrow */}
      {total > 1 && (
        <button className="lightbox-nav lightbox-nav-prev" onClick={goPrev} title={t('imageLightbox.previous')} aria-label={t('imageLightbox.previous')}>
          <Icon name="chevronLeft" size={32} />
        </button>
      )}

      {/* Image container */}
      <div className="lightbox-image-wrap">
        {loading && <div className="lightbox-spinner"><Icon name="spinner" size={32} /></div>}
        <img
          src={current.src}
          alt={current.alt}
          className={`lightbox-image ${zoomed ? 'zoomed' : ''}`}
          onLoad={() => setLoading(false)}
          onDoubleClick={() => setZoomed(z => !z)}
          draggable={false}
        />
      </div>

      {/* Next arrow */}
      {total > 1 && (
        <button className="lightbox-nav lightbox-nav-next" onClick={goNext} title={t('imageLightbox.next')} aria-label={t('imageLightbox.next')}>
          <Icon name="chevronRight" size={32} />
        </button>
      )}

      {/* Bottom toolbar */}
      <div className="lightbox-toolbar">
        <span className="lightbox-counter">{index + 1} / {total}</span>
        <span className="lightbox-filename" title={current.filename}>{current.filename}</span>
        <div style={{ flex: 1 }} />
        <button className="btn btn-sm btn-ghost" onClick={handleSave} title={t('imageLightbox.saveImage')}>
          <Icon name="download" size={14} /> {t('common.save')}
        </button>
      </div>
    </div>
  );
}
