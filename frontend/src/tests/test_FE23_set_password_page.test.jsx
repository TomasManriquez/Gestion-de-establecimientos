/**
 * test_FE23_set_password_page.test.jsx
 * ────────────────────────────────────
 * Tarea: F4b · Pantalla pública /definir-contrasena (la ruta a la que apunta el enlace del correo, ADR-012)
 *
 * Verifica que:
 *   - la ruta existe y es pública: con la App real, sin sesión, el enlace del correo muestra el formulario
 *     (antes caía en la vista 404) y no redirige al login
 *   - el token se lee del fragmento (#token=…), sale de la barra de direcciones y viaja solo en el POST
 *   - pide la contraseña dos veces y valida el largo con la política pública antes de enviar
 *   - cada respuesta del servidor tiene su mensaje: 204, 400 (enlace inválido), 422 (todas las infracciones,
 *     el formulario sigue disponible), 429 y error de red
 *   - sin token en el enlace no se muestra el formulario ni se llama al servidor
 *   - cumple las reglas de shadcn del proyecto (sin colores crudos, sin space-*, solo primitivas de ui)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import axios from 'axios';

vi.mock('axios');

import SetPassword from '@/components/SetPassword';
import App from '@/App';

const POLICY = { min_length: 15, max_length: 64, require_char_classes: 0 };
const LONG = 'una-contrasena-larga-de-prueba';
const URL_OK = '/definir-contrasena#token=TOKEN-DE-PRUEBA-123';

const apiError = (status, detail) => Object.assign(new Error(`HTTP ${status}`), { response: { status, data: { detail } } });

function renderPage(path = URL_OK) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/definir-contrasena" element={<SetPassword />} />
        <Route path="/login" element={<div>PANTALLA DE LOGIN</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const postCalls = () => axios.post.mock.calls.filter(([url]) => url === '/api/auth/set-password');

async function fill(user, password = LONG, confirm = password) {
  await user.type(screen.getByLabelText('Nueva contraseña'), password);
  await user.type(screen.getByLabelText('Repite la contraseña'), confirm);
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  axios.interceptors = { response: { use: vi.fn(() => 1), eject: vi.fn() } };
  axios.get.mockImplementation((url) => (url === '/api/auth/password-policy'
    ? Promise.resolve({ data: POLICY })
    : Promise.reject(apiError(401, 'Not authenticated'))));
});

describe('FE23: pantalla /definir-contrasena', () => {
  it('FE23-A: con la App real y sin sesión, el enlace del correo muestra el formulario (ya no es un 404)', async () => {
    render(<MemoryRouter initialEntries={[URL_OK]}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /Define tu contraseña/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Nueva contraseña')).toBeInTheDocument();
    expect(screen.queryByText(/no existe|404|no encontrada/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Usuario de red')).not.toBeInTheDocument();      // no fue al login
  });

  it('FE23-B: muestra la política pública y pide la contraseña dos veces', async () => {
    renderPage();
    expect(await screen.findByText(/al menos 15 caracteres/)).toBeInTheDocument();
    expect(axios.get).toHaveBeenCalledWith('/api/auth/password-policy');
    expect(screen.getByLabelText('Nueva contraseña')).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText('Nueva contraseña')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByLabelText('Repite la contraseña')).toHaveAttribute('type', 'password');
  });

  it('FE23-C: si la política exige clases de caracteres, lo dice', async () => {
    axios.get.mockResolvedValue({ data: { ...POLICY, require_char_classes: 3 } });
    renderPage();
    expect(await screen.findByText(/al menos 3 tipos de caracteres/)).toBeInTheDocument();
  });

  it('FE23-D: envía el token del fragmento y la contraseña, y lo informa al terminar', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ status: 204, data: undefined });
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));
    expect(postCalls()[0][1]).toEqual({ token: 'TOKEN-DE-PRUEBA-123', password: LONG });
    expect(await screen.findByRole('heading', { name: 'Contraseña definida' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument();     // el formulario desaparece
    expect(screen.queryByDisplayValue(LONG)).not.toBeInTheDocument();                // y la contraseña no queda en pantalla

    await user.click(screen.getByRole('button', { name: 'Ir a iniciar sesión' }));
    expect(await screen.findByText('PANTALLA DE LOGIN')).toBeInTheDocument();
  });

  it('FE23-E: el token sale de la barra de direcciones y no se guarda en el navegador', async () => {
    const replaceState = vi.spyOn(window.history, 'replaceState');
    renderPage();
    await screen.findByLabelText('Nueva contraseña');
    expect(replaceState).toHaveBeenCalled();
    expect(replaceState.mock.calls[0][2]).not.toContain('token');
    expect(replaceState.mock.calls[0][2]).not.toContain('#');
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain('TOKEN-DE-PRUEBA-123');
    replaceState.mockRestore();
  });

  it('FE23-F: las contraseñas distintas se marcan en el campo y no se envía nada', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user, LONG, `${LONG}x`);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText('Las contraseñas no coinciden.')).toBeInTheDocument();
    expect(screen.getByLabelText('Repite la contraseña')).toHaveAttribute('aria-invalid', 'true');
    expect(postCalls()).toHaveLength(0);
  });

  it('FE23-G: una contraseña más corta que la política no se envía', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user, 'corta-123');
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText('Debe tener al menos 15 caracteres.')).toBeInTheDocument();
    expect(postCalls()).toHaveLength(0);
  });

  it('FE23-H: 400 (enlace usado, vencido o inexistente) muestra el mensaje del servidor y retira el formulario', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue(apiError(400, { code: 'invalid_or_expired_link', message: 'El enlace no es válido o ya venció. Pide a un administrador que te envíe uno nuevo.' }));
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText('El enlace no sirve')).toBeInTheDocument();
    expect(screen.getByText(/ya venció/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ir a iniciar sesión' })).toBeInTheDocument();
  });

  it('FE23-I: 422 lista todas las infracciones y deja el formulario para corregir (el enlace no se consumió)', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue(apiError(422, [
      { code: 'common_password', message: 'Es una contraseña demasiado común o predecible' },
      { code: 'contains_email', message: 'No puede contener tu correo' },
    ]));
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText('La contraseña no cumple la política')).toBeInTheDocument();
    expect(screen.getByText('Es una contraseña demasiado común o predecible')).toBeInTheDocument();
    expect(screen.getByText('No puede contener tu correo')).toBeInTheDocument();
    expect(screen.getByLabelText('Nueva contraseña')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar contraseña' })).toBeEnabled();
  });

  it('FE23-J: 429 muestra el mensaje de espera del servidor', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue(apiError(429, { code: 'rate_limited', message: 'Demasiados intentos. Espera 5 min e inténtalo de nuevo.' }));
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText('Demasiados intentos. Espera 5 min e inténtalo de nuevo.')).toBeInTheDocument();
  });

  it('FE23-K: un fallo de red da un mensaje genérico sin detalles técnicos y se puede reintentar', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue(new Error('Network Error'));
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByText(/No se pudo definir la contraseña/)).toBeInTheDocument();
    expect(screen.queryByText(/Network Error/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar contraseña' })).toBeEnabled();
  });

  it('FE23-L: sin token en el enlace no hay formulario ni se llama a set-password', async () => {
    renderPage('/definir-contrasena');
    expect(await screen.findByText('El enlace está incompleto')).toBeInTheDocument();
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ir a iniciar sesión' })).toBeInTheDocument();
    expect(postCalls()).toHaveLength(0);
  });

  it('FE23-M: un fragmento sin valor (#token=) se trata como enlace incompleto', async () => {
    renderPage('/definir-contrasena#token=');
    expect(await screen.findByText('El enlace está incompleto')).toBeInTheDocument();
  });

  it('FE23-N: si la política no carga, el formulario sigue funcionando y el servidor decide', async () => {
    const user = userEvent.setup();
    axios.get.mockRejectedValue(apiError(500, 'error'));
    axios.post.mockResolvedValue({ status: 204 });
    renderPage();
    await user.type(await screen.findByLabelText('Nueva contraseña'), LONG);
    await user.type(screen.getByLabelText('Repite la contraseña'), LONG);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    await waitFor(() => expect(postCalls()).toHaveLength(1));
  });

  it('FE23-O: mientras guarda, el botón queda deshabilitado (sin envíos dobles)', async () => {
    const user = userEvent.setup();
    let release;
    axios.post.mockReturnValue(new Promise((resolve) => { release = resolve; }));
    renderPage();
    await screen.findByText(/al menos 15 caracteres/);
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
    expect(await screen.findByRole('button', { name: /Guardando/ })).toBeDisabled();
    release({ status: 204 });
    await screen.findByRole('heading', { name: 'Contraseña definida' });
    expect(postCalls()).toHaveLength(1);
  });
});

// ─── Reglas de shadcn del proyecto (mismo criterio que FE16, para este componente) ───
describe('FE23: SetPassword cumple las reglas de shadcn', () => {
  const source = readFileSync(join(process.cwd(), 'src/components/SetPassword.jsx'), 'utf-8');
  const RAW_COLOR = /\b(?:bg|text|border|ring|fill|stroke|from|to|via|outline|divide|decoration|shadow)-(?:red|green|blue|sky|slate|gray|grey|zinc|emerald|amber|yellow|orange|rose|indigo|violet|purple|pink|teal|cyan|lime|stone|neutral|fuchsia)-\d{2,3}\b|\b(?:bg|text|border)-(?:white|black)\b/;

  it('FE23-P: sin colores crudos, sin space-x/space-y y sin z-index manual', () => {
    expect(source.match(RAW_COLOR)?.[0]).toBeUndefined();
    expect(source).not.toMatch(/\bspace-[xy]-/);
    expect(source).not.toMatch(/(?:^|[\s"'`])-?z-(?:\d|\[)/);
  });

  it('FE23-Q: solo importa primitivas de @/components/ui, @/lib, react y react-router-dom (ni axios ni radix)', () => {
    const imports = [...source.matchAll(/from ['"]([^'"]+)['"]/g)].map((m) => m[1]);
    for (const i of imports) {
      expect(/^(react|react-router-dom)$/.test(i) || i.startsWith('@/components/ui/') || i.startsWith('@/lib/'), `import inesperado: ${i}`).toBe(true);
    }
  });

  it('FE23-R: el formulario usa FieldGroup/Field y los errores usan FieldError', () => {
    expect(source).toMatch(/<FieldGroup>/);
    expect(source).toMatch(/<Field\b/);
    expect(source).toMatch(/<FieldError\b/);
  });

  it('FE23-S: el token no se guarda en el navegador ni se escribe en consola', () => {
    expect(source).not.toMatch(/localStorage|sessionStorage|console\./);
  });
});
