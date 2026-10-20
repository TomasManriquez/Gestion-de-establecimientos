import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { School, Lock, User, AlertCircle, Loader2 } from 'lucide-react';

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';

const GSI_SRC = 'https://accounts.google.com/gsi/client';
// `hd` es solo una pista de interfaz para Google: la protección real es la verificación del servidor.
const GOOGLE_HOSTED_DOMAIN = 'slepllanquihue.cl';
const GOOGLE_ERROR = 'No se pudo iniciar sesión con Google. Use su cuenta institucional @slepllanquihue.cl.';

/** Carga el script de Google Identity Services una sola vez y entrega `window.google`. */
function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google);
  return new Promise((resolve, reject) => {
    let script = document.querySelector(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement('script');
      script.src = GSI_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    script.addEventListener('load', () => resolve(window.google), { once: true });
    script.addEventListener('error', () => reject(new Error('gsi')), { once: true });
  });
}

export default function Login({ onLoginSuccess }) {
  const [username, setUsername]       = useState('');
  const [password, setPassword]       = useState('');
  const [error, setError]             = useState('');
  const [loading, setLoading]         = useState(false);
  const [searchParams]                = useSearchParams();
  const navigate                      = useNavigate();
  const [googleReady, setGoogleReady] = useState(false);
  const googleButtonRef               = useRef(null);
  const finishLoginRef                = useRef(null);

  // Ruta de destino post-login (guardada por ProtectedRoute en ?from=)
  const redirectTo = searchParams.get('from') || '/dashboard';

  // Misma salida para ambos métodos: guarda el token y deja que App cargue al usuario.
  const finishLogin = (accessToken) => {
    localStorage.setItem('token', accessToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
    onLoginSuccess();
    navigate(redirectTo, { replace: true });
  };
  finishLoginRef.current = finishLogin;

  const handleGoogleCredential = async (response) => {
    setError('');
    setLoading(true);
    try {
      const { data } = await axios.post('/api/auth/google', { credential: response.credential });
      finishLoginRef.current(data.access_token);
    } catch (err) {
      setError(err.response?.status === 429 ? err.response.data?.detail?.message || GOOGLE_ERROR : GOOGLE_ERROR);
    } finally {
      setLoading(false);
    }
  };

  // Botón de Google: el client id viene del backend (el frontend no tiene variables de entorno, ADR-008).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await axios.get('/api/auth/config');
        const clientId = response?.data?.google_client_id;
        if (!clientId) return;
        const google = await loadGoogleScript();
        if (cancelled || !google?.accounts?.id || !googleButtonRef.current) return;
        google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGoogleCredential,
          hd: GOOGLE_HOSTED_DOMAIN,
        });
        google.accounts.id.renderButton(googleButtonRef.current, {
          theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular', locale: 'es',
          width: googleButtonRef.current.offsetWidth || 320,
        });
        setGoogleReady(true);
      } catch {
        // Sin Google (config vacía, script bloqueado, sin red): queda el ingreso con contraseña.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { data } = await axios.post('/api/auth/login', { username, password });
      finishLogin(data.access_token);
    } catch (err) {
      console.error(err);
      setError(
        err.response?.data?.detail ||
        'Error de conexión. Verifique sus credenciales o intente más tarde.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 sm:p-6 md:p-8 bg-gradient-to-tr from-sky-950 via-slate-900 to-indigo-950 overflow-hidden">
      {/* Elementos decorativos de fondo con desenfoque adaptativo */}
      <div
        className="absolute -top-24 -left-24 size-72 sm:size-96 rounded-full bg-sky-500/15 blur-3xl pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute -bottom-24 -right-24 size-72 sm:size-96 rounded-full bg-indigo-500/15 blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <Card className="w-full max-w-sm sm:max-w-md bg-white/95 dark:bg-card/90 backdrop-blur-xl border-white/20 shadow-2xl animate-fade-in z-10">
        <CardHeader className="flex flex-col items-center text-center pb-6">
          <div className="flex items-center justify-center size-14 sm:size-16 rounded-2xl bg-sky-600 text-white shadow-lg shadow-sky-600/30 mb-3 transition-transform hover:scale-105">
            <School className="size-7 sm:size-8" />
          </div>
          <CardTitle className="text-2xl sm:text-3xl font-bold font-outfit tracking-tight text-slate-800 dark:text-foreground">
            SLEP Llanquihue
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm text-slate-500 dark:text-muted-foreground font-sans">
            Gestión Centralizada de Establecimientos
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          {error && (
            <Alert variant="destructive" className="animate-fade-in">
              <AlertCircle className="size-4" />
              <AlertDescription className="text-xs sm:text-sm font-medium">
                {error}
              </AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label
                htmlFor="username"
                className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300"
              >
                Usuario de red
              </Label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground pointer-events-none">
                  <User className="size-4" />
                </span>
                <Input
                  id="username"
                  name="username"
                  type="text"
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ej. admin"
                  className="pl-9 h-11 text-sm bg-slate-50/70 dark:bg-background focus-visible:ring-sky-500 font-sans"
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label
                htmlFor="password"
                className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300"
              >
                Contraseña
              </Label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground pointer-events-none">
                  <Lock className="size-4" />
                </span>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-9 h-11 text-sm bg-slate-50/70 dark:bg-background focus-visible:ring-sky-500 font-sans"
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 mt-2 text-sm sm:text-base font-semibold font-outfit shadow-md shadow-sky-600/20 active:scale-[0.99] transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" data-icon="inline-start" />
                  Iniciando sesión...
                </>
              ) : (
                'Ingresar al sistema'
              )}
            </Button>
          </form>

          <div className={googleReady ? 'flex flex-col gap-4' : 'hidden'} data-testid="google-login">
            <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-muted-foreground" aria-hidden="true">
              <span className="h-px flex-1 bg-slate-200 dark:bg-border" />
              o
              <span className="h-px flex-1 bg-slate-200 dark:bg-border" />
            </div>
            <div ref={googleButtonRef} className="flex justify-center min-h-11" />
          </div>
        </CardContent>

        <CardFooter className="flex justify-center border-t border-slate-100 dark:border-border/40 py-4 text-center text-xs text-slate-400 dark:text-muted-foreground">
          Servicio Local de Educación Pública de Llanquihue &copy; 2026
        </CardFooter>
      </Card>
    </div>
  );
}
