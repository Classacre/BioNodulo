import React, { useState, useCallback, useEffect } from 'react';
import { fetchToken, setToken, generateGuestName } from './auth';

interface AuthDialogProps {
  isOpen: boolean;
  onLogin: (name: string) => void;
  onClose: () => void;
}

const AuthDialog: React.FC<AuthDialogProps> = ({ isOpen, onLogin, onClose }) => {
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setName('');
      setError(null);
      setIsLoading(false);
    }
  }, [isOpen]);

  const handleJoin = useCallback(async () => {
    const displayName = name.trim() || generateGuestName();
    setIsLoading(true);
    setError(null);
    try {
      const token = await fetchToken(displayName);
      setToken(token);
      onLogin(displayName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join');
    } finally {
      setIsLoading(false);
    }
  }, [name, onLogin]);

  const handleGuest = useCallback(async () => {
    const guestName = generateGuestName();
    setIsLoading(true);
    setError(null);
    try {
      const token = await fetchToken(guestName);
      setToken(token);
      onLogin(guestName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join as guest');
    } finally {
      setIsLoading(false);
    }
  }, [onLogin]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      e.preventDefault();
      handleJoin();
    }
    if (e.key === 'Escape') {
      onClose();
    }
  }, [handleJoin, isLoading, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="auth-dialog-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 400,
      }}
      onClick={onClose}
    >
      <div
        className="auth-dialog"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          width: 380,
          maxWidth: '90vw',
          padding: '28px 24px',
          boxShadow: '0 12px 40px rgba(0,0,0,0.3)',
        }}
        onClick={e => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <h2 style={{
          margin: '0 0 6px',
          fontSize: 18,
          fontWeight: 700,
          color: 'var(--text)',
        }}>
          Join Collaboration
        </h2>
        <p style={{
          margin: '0 0 20px',
          fontSize: 13,
          color: 'var(--muted)',
          lineHeight: 1.5,
        }}>
          Enter your display name to collaborate on workflows in real time.
        </p>

        <div style={{ marginBottom: 16 }}>
          <label style={{
            display: 'block',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text)',
            marginBottom: 6,
          }}>
            Display Name
          </label>
          <input
            type="text"
            placeholder="Your name"
            value={name}
            onChange={e => setName(e.target.value)}
            autoFocus
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 14,
              outline: 'none',
              boxSizing: 'border-box',
              transition: 'border-color 0.2s',
            }}
            onFocus={e => {
              e.currentTarget.style.borderColor = 'var(--accent)';
            }}
            onBlur={e => {
              e.currentTarget.style.borderColor = 'var(--border)';
            }}
          />
        </div>

        {error && (
          <div style={{
            marginBottom: 16,
            padding: '8px 12px',
            borderRadius: 6,
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.2)',
            color: '#ef4444',
            fontSize: 12,
          }}>
            {error}
          </div>
        )}

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}>
          <button
            className="btn btn-primary"
            onClick={handleJoin}
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '10px 16px',
              borderRadius: 8,
              border: 'none',
              background: isLoading ? 'var(--border)' : 'var(--accent)',
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.7 : 1,
              transition: 'opacity 0.2s',
            }}
          >
            {isLoading ? 'Joining…' : 'Join'}
          </button>

          <button
            className="btn"
            onClick={handleGuest}
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '10px 16px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'transparent',
              color: 'var(--muted)',
              fontSize: 13,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.5 : 1,
            }}
          >
            Continue as Guest
          </button>
        </div>

        <div style={{
          marginTop: 16,
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--muted)',
        }}>
          Your session is authenticated with a secure token.
        </div>
      </div>
    </div>
  );
};

export default AuthDialog;
