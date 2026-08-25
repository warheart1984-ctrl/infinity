import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiPost, getApiErrorMessage } from '../lib/api';

/**
 * OAuth callback — exchanges code for token via backend; never displays raw tokens.
 */
export default function OperatorOauthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('exchanging');

  const provider = useMemo(() => {
    const state = String(params.get('state') || '');
    if (state.startsWith('gmail:')) return 'gmail';
    if (state.startsWith('microsoft:')) return 'microsoft';
    return String(params.get('provider') || '').toLowerCase() || null;
  }, [params]);

  useEffect(() => {
    const code = params.get('code');
    const err = params.get('error');
    if (err) {
      setStatus('error');
      toast.error(err);
      return;
    }
    if (!code || !provider) {
      setStatus('error');
      toast.error('Missing OAuth code or provider');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await apiPost('/api/operator/oauth/callback', {
          provider,
          code,
          state: params.get('state'),
        });
        if (cancelled) return;
        if (res.data?.ok) {
          setStatus('connected');
          toast.success(`${provider} connected (${res.data?.status?.mode || 'live'})`);
          setTimeout(() => navigate('/operator/plugins'), 800);
        } else {
          setStatus('error');
          toast.error(res.data?.error || 'OAuth exchange failed');
        }
      } catch (error) {
        if (!cancelled) {
          setStatus('error');
          toast.error(getApiErrorMessage(error, 'OAuth exchange failed'));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params, provider, navigate]);

  return (
    <div className="workflow-page" data-testid="oauth-callback">
      <div className="page-intro">
        <h1>OAuth callback</h1>
        <p>Status: {status}. Tokens are stored server-side — never shown here.</p>
      </div>
    </div>
  );
}
