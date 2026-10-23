import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { authApi } from '@/lib/api';

const INCOMPLETE_LINK = 'Abre el enlace completo del correo. Si el problema sigue, pide a un administrador que te envíe uno nuevo.';
const GENERIC_ERROR = 'No se pudo definir la contraseña. Inténtalo de nuevo en unos minutos.';

/** El token viaja en el fragmento (`#token=…`) para que no llegue a logs ni a la cabecera Referer (ADR-012). */
function readToken(hash) {
  const value = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('token');
  return value && value.trim() ? value.trim() : '';
}

function policyHint(policy) {
  if (!policy) return 'Usa una frase larga: es más segura que una palabra con símbolos.';
  const classes = policy.require_char_classes > 0
    ? ` Combina al menos ${policy.require_char_classes} tipos de caracteres (mayúsculas, minúsculas, números y símbolos).`
    : '';
  return `Usa al menos ${policy.min_length} caracteres. Una frase larga es más segura que una palabra con símbolos.${classes}`;
}

/** Pantalla pública a la que llega el enlace del correo de invitación o de restablecimiento (US-24). */
export default function SetPassword() {
  const location = useLocation();
  const navigate = useNavigate();
  const [token] = useState(() => readToken(location.hash));
  const [policy, setPolicy] = useState(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [violations, setViolations] = useState([]);
  const [formError, setFormError] = useState('');
  const [linkError, setLinkError] = useState('');
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  // Una vez leído, el token sale de la barra de direcciones y del historial: queda solo en memoria.
  useEffect(() => {
    if (location.hash) window.history.replaceState(window.history.state, '', location.pathname + location.search);
  }, []);

  // La política es pública (se necesita antes de tener sesión). Si falla, el formulario sigue siendo usable.
  useEffect(() => {
    let cancelled = false;
    authApi.passwordPolicy().then((p) => { if (!cancelled) setPolicy(p); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const goToLogin = () => navigate('/login', { replace: true });

  const validate = () => {
    const next = {};
    if (policy && password.length < policy.min_length) next.password = `Debe tener al menos ${policy.min_length} caracteres.`;
    if (policy && password.length > policy.max_length) next.password = `No puede superar ${policy.max_length} caracteres.`;
    if (!password) next.password = 'Escribe tu nueva contraseña.';
    if (confirm !== password) next.confirm = 'Las contraseñas no coinciden.';
    return next;
  };

  const submit = async (event) => {
    event.preventDefault();
    setFormError('');
    setViolations([]);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return;
    setPending(true);
    try {
      await authApi.setPassword(token, password);
      setPassword('');
      setConfirm('');
      setDone(true);
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;
      if (status === 400) {
        setLinkError(detail?.message || 'El enlace no es válido o ya venció. Pide a un administrador que te envíe uno nuevo.');
      } else if (status === 422 && Array.isArray(detail)) {
        setViolations(detail.map((d) => d?.message).filter(Boolean));
      } else if (status === 429) {
        setFormError(detail?.message || 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.');
      } else {
        setFormError(GENERIC_ERROR);
      }
    } finally {
      setPending(false);
    }
  };

  const unusable = !token || linkError;

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{done ? 'Contraseña definida' : 'Define tu contraseña'}</CardTitle>
          <CardDescription>SLEP Llanquihue · Gestión de Establecimientos</CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-4">
          {done && (
            <Alert>
              <AlertTitle>Listo</AlertTitle>
              <AlertDescription>
                Ya puedes iniciar sesión con tu correo institucional y la contraseña que acabas de crear.
              </AlertDescription>
            </Alert>
          )}

          {!done && !token && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>El enlace está incompleto</AlertTitle>
              <AlertDescription>{INCOMPLETE_LINK}</AlertDescription>
            </Alert>
          )}

          {!done && token && linkError && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>El enlace no sirve</AlertTitle>
              <AlertDescription>{linkError}</AlertDescription>
            </Alert>
          )}

          {!done && !unusable && (
            <form onSubmit={submit} noValidate className="flex flex-col gap-4">
              <FieldGroup>
                <Field data-invalid={errors.password ? true : undefined}>
                  <FieldLabel htmlFor="new-password">Nueva contraseña</FieldLabel>
                  <Input id="new-password" type="password" autoComplete="new-password" value={password}
                    aria-invalid={errors.password ? true : undefined}
                    aria-describedby={errors.password ? 'new-password-error' : 'new-password-hint'}
                    onChange={(e) => setPassword(e.target.value)} />
                  {errors.password
                    ? <FieldError id="new-password-error">{errors.password}</FieldError>
                    : <FieldDescription id="new-password-hint">{policyHint(policy)}</FieldDescription>}
                </Field>

                <Field data-invalid={errors.confirm ? true : undefined}>
                  <FieldLabel htmlFor="confirm-password">Repite la contraseña</FieldLabel>
                  <Input id="confirm-password" type="password" autoComplete="new-password" value={confirm}
                    aria-invalid={errors.confirm ? true : undefined}
                    aria-describedby={errors.confirm ? 'confirm-password-error' : undefined}
                    onChange={(e) => setConfirm(e.target.value)} />
                  {errors.confirm && <FieldError id="confirm-password-error">{errors.confirm}</FieldError>}
                </Field>
              </FieldGroup>

              {violations.length > 0 && (
                <Alert variant="destructive" role="alert">
                  <AlertTitle>La contraseña no cumple la política</AlertTitle>
                  <AlertDescription>
                    <ul className="ml-4 flex list-disc flex-col gap-1">
                      {violations.map((message) => <li key={message}>{message}</li>)}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {formError && (
                <Alert variant="destructive" role="alert"><AlertDescription>{formError}</AlertDescription></Alert>
              )}

              <Button type="submit" disabled={pending}>
                {pending && <Spinner data-icon="inline-start" />}
                {pending ? 'Guardando…' : 'Guardar contraseña'}
              </Button>
            </form>
          )}
        </CardContent>

        {(done || unusable) && (
          <CardFooter>
            <Button type="button" variant={done ? 'default' : 'outline'} onClick={goToLogin}>Ir a iniciar sesión</Button>
          </CardFooter>
        )}
      </Card>
    </main>
  );
}
