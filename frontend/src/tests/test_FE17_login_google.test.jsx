import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Login from '../components/Login';

vi.mock('axios');

// Doble de Google Identity Services: captura initialize/renderButton sin cargar el script real.
function installGoogleStub() {
  const gsi = { initialize: vi.fn(), renderButton: vi.fn() };
  window.google = { accounts: { id: gsi } };
  return gsi;
}

function renderLogin(onLoginSuccess = vi.fn()) {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login onLoginSuccess={onLoginSuccess} />} />
        <Route path="/dashboard" element={<div>DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>
  );
  return onLoginSuccess;
}

describe('FE-17: Login con Google Identity Services (C24)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    delete axios.defaults.headers.common['Authorization'];
    delete window.google;
  });
  afterEach(() => { delete window.google; });

  it('pide el client id al backend (no usa variables VITE_*) e inicializa el botón con la pista de dominio', async () => {
    const gsi = installGoogleStub();
    axios.get.mockResolvedValueOnce({ data: { google_client_id: 'cliente.apps.googleusercontent.com' } });
    renderLogin();

    await waitFor(() => expect(gsi.initialize).toHaveBeenCalledTimes(1));
    expect(axios.get).toHaveBeenCalledWith('/api/auth/config');
    expect(gsi.initialize.mock.calls[0][0]).toMatchObject({
      client_id: 'cliente.apps.googleusercontent.com',
      hd: 'slepllanquihue.cl',
    });
    expect(gsi.renderButton).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('google-login')).not.toHaveClass('hidden');
  });

  it('envía el credential a /api/auth/google y reutiliza el cierre de login (token, cabecera, onLoginSuccess)', async () => {
    const gsi = installGoogleStub();
    axios.get.mockResolvedValueOnce({ data: { google_client_id: 'c.apps.googleusercontent.com' } });
    axios.post.mockResolvedValueOnce({ data: { access_token: 'jwt-de-google' } });
    const onLoginSuccess = renderLogin();

    await waitFor(() => expect(gsi.initialize).toHaveBeenCalled());
    await gsi.initialize.mock.calls[0][0].callback({ credential: 'id-token-de-google' });

    await waitFor(() => expect(screen.getByText('DASHBOARD')).toBeInTheDocument());
    expect(axios.post).toHaveBeenCalledWith('/api/auth/google', { credential: 'id-token-de-google' });
    expect(localStorage.getItem('token')).toBe('jwt-de-google');
    expect(axios.defaults.headers.common['Authorization']).toBe('Bearer jwt-de-google');
    expect(onLoginSuccess).toHaveBeenCalledTimes(1);
  });

  it('un rechazo del servidor muestra un mensaje genérico y no guarda nada', async () => {
    const gsi = installGoogleStub();
    axios.get.mockResolvedValueOnce({ data: { google_client_id: 'c.apps.googleusercontent.com' } });
    axios.post.mockRejectedValueOnce({ response: { status: 401, data: { detail: 'Could not validate credentials' } } });
    const onLoginSuccess = renderLogin();

    await waitFor(() => expect(gsi.initialize).toHaveBeenCalled());
    await gsi.initialize.mock.calls[0][0].callback({ credential: 'x' });

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/cuenta institucional/i));
    expect(screen.queryByText('Could not validate credentials')).not.toBeInTheDocument();
    expect(localStorage.getItem('token')).toBeNull();
    expect(onLoginSuccess).not.toHaveBeenCalled();
  });

  it('un 429 muestra el mensaje de espera del servidor', async () => {
    const gsi = installGoogleStub();
    axios.get.mockResolvedValueOnce({ data: { google_client_id: 'c.apps.googleusercontent.com' } });
    axios.post.mockRejectedValueOnce({
      response: { status: 429, data: { detail: { code: 'rate_limited', message: 'Demasiados intentos. Espera 15 min e inténtalo de nuevo.' } } },
    });
    renderLogin();

    await waitFor(() => expect(gsi.initialize).toHaveBeenCalled());
    await gsi.initialize.mock.calls[0][0].callback({ credential: 'x' });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Demasiados intentos'));
  });

  it('sin client id configurado no inicializa Google y el ingreso con contraseña sigue disponible', async () => {
    const gsi = installGoogleStub();
    axios.get.mockResolvedValueOnce({ data: { google_client_id: '' } });
    renderLogin();

    await waitFor(() => expect(axios.get).toHaveBeenCalled());
    expect(gsi.initialize).not.toHaveBeenCalled();
    expect(screen.getByTestId('google-login')).toHaveClass('hidden');
    expect(screen.getByRole('button', { name: /Ingresar al sistema/i })).toBeInTheDocument();
  });

  it('si /api/auth/config falla, el login por contraseña funciona igual', async () => {
    axios.get.mockRejectedValueOnce(new Error('network'));
    axios.post.mockResolvedValueOnce({ data: { access_token: 'jwt-clave' } });
    renderLogin();

    fireEvent.change(screen.getByLabelText(/Usuario de red/i), { target: { value: 'admin@slepllanquihue.cl' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), { target: { value: 'una-clave-larga-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Ingresar al sistema/i }));

    await waitFor(() => expect(localStorage.getItem('token')).toBe('jwt-clave'));
    expect(axios.post).toHaveBeenCalledWith('/api/auth/login', { username: 'admin@slepllanquihue.cl', password: 'una-clave-larga-1' });
  });
});
