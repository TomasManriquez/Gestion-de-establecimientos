import React, { useState } from 'react';
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

export default function Login({ onLoginSuccess }) {
  const [username, setUsername]       = useState('');
  const [password, setPassword]       = useState('');
  const [error, setError]             = useState('');
  const [loading, setLoading]         = useState(false);
  const [searchParams]                = useSearchParams();
  const navigate                      = useNavigate();

  // Ruta de destino post-login (guardada por ProtectedRoute en ?from=)
  const redirectTo = searchParams.get('from') || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { data } = await axios.post('/api/auth/login', { username, password });
      localStorage.setItem('token', data.access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
      onLoginSuccess();
      navigate(redirectTo, { replace: true });
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
        </CardContent>

        <CardFooter className="flex justify-center border-t border-slate-100 dark:border-border/40 py-4 text-center text-xs text-slate-400 dark:text-muted-foreground">
          Servicio Local de Educación Pública de Llanquihue &copy; 2026
        </CardFooter>
      </Card>
    </div>
  );
}
