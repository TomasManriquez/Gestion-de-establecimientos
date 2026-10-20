import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Login from '../components/Login';

vi.mock('axios');

describe('FE-00: Login — Migración a shadcn/ui', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    delete axios.defaults.headers.common['Authorization'];
  });

  it('renderiza título, logo, labels y botón con shadcn', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login onLoginSuccess={vi.fn()} />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('SLEP Llanquihue')).toBeInTheDocument();
    expect(screen.getByText('Gestión Centralizada de Establecimientos')).toBeInTheDocument();
    expect(screen.getByLabelText(/Usuario de red/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contraseña/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ingresar al sistema/i })).toBeInTheDocument();
  });

  it('muestra Alert de shadcn cuando la autenticación falla', async () => {
    axios.post.mockRejectedValueOnce({
      response: { data: { detail: 'Credenciales inválidas' } },
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login onLoginSuccess={vi.fn()} />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/Usuario de red/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: /Ingresar al sistema/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Credenciales inválidas')).toBeInTheDocument();
    });
  });

  it('autentica exitosamente sin guardar ningún token en el navegador (cookie HttpOnly)', async () => {
    const onLoginSuccess = vi.fn();
    axios.post.mockResolvedValueOnce({
      data: { expires_in: 10800 },
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login onLoginSuccess={onLoginSuccess} />} />
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/Usuario de red/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /Ingresar al sistema/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/auth/login', {
        username: 'admin',
        password: 'secret',
      });
      expect(localStorage.getItem('token')).toBeNull();
      expect(axios.defaults.headers.common['Authorization']).toBeUndefined();
      expect(onLoginSuccess).toHaveBeenCalled();
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    });
  });
});
