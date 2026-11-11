/**
 * test_FE27_portal.test.jsx — ADR-021, fase 3: página del portal (árbol de temas y subtemas, tarjetas, cuestionario de datos).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import PortalPage from '@/components/portal/PortalPage';

vi.mock('axios');

const TOPICS = [{ _id: 't1', name: 'Finanzas', parent_id: null }, { _id: 't2', name: 'Presupuesto', parent_id: 't1' },
  { _id: 't3', name: 'Compras', parent_id: null }];
const R_OPEN = { _id: 'r1', updated_at: 'v0', title: 'Ejecución', url: 'https://app.powerbi.com/x', platform: 'Power BI', topic_id: 't2', catastro_level: 1, visibility: 'org', created_by: 'u9' };
const R_RESTRICTED = { _id: 'r2', updated_at: 'v0', title: 'Sueldos', url: 'https://docs.google.com/spreadsheets/d/1', platform: 'Google Sheets', topic_id: 't3', catastro_level: 2, visibility: 'restricted', created_by: 'u9' };

const editor = { _id: 'u1', access: [{ platform_id: 'datos', role: 'editor', capabilities: ['read', 'write'] }] };
const viewer = { _id: 'u2', access: [{ platform_id: 'datos', role: 'viewer', capabilities: ['read'] }] };
const admin = { _id: 'u3', access: [{ platform_id: 'iam', role: 'admin', capabilities: ['read', 'write', 'delete'] },
  { platform_id: 'datos', role: 'admin', capabilities: ['read', 'write', 'delete'] }] };

const mockApi = (resources) => {
  axios.get.mockImplementation((url) => {
    if (url === '/api/v1/portal/topics') return Promise.resolve({ data: TOPICS });
    if (url === '/api/v1/portal/resources') return Promise.resolve({ data: resources });
    return Promise.resolve({ data: [] });
  });
};
const renderPage = (user) => render(<MemoryRouter><PortalPage currentUser={user} /></MemoryRouter>);

describe('FE27: portal de recursos', () => {
  beforeEach(() => { vi.resetAllMocks(); });

  it('FE27-A: abre en el primer subtema con proyectos, muestra lo restringido marcado y el enlace en pestaña nueva', async () => {
    mockApi([R_OPEN, R_RESTRICTED]);
    renderPage(viewer);
    const link = await screen.findByRole('link', { name: /Ejecución/ });
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(screen.getByText('Finanzas › Presupuesto')).toBeTruthy();                            // ruta del subtema activo
    expect(screen.queryByRole('link', { name: /Sueldos/ })).toBeNull();                          // vive en otro tema
    fireEvent.click(screen.getByRole('button', { name: /^Compras/ }));
    expect(screen.getByRole('link', { name: /Sueldos/ })).toBeTruthy();
    expect(screen.getByText('Restringido')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Registrar proyecto' })).toBeNull();            // viewer no escribe
    expect(screen.queryByRole('button', { name: 'Nuevo tema' })).toBeNull();
  });

  it('FE27-B: el árbol anida los subtemas con su conteo, el tema agrupa a sus subtemas y el buscador cruza todo', async () => {
    mockApi([R_OPEN, R_RESTRICTED]);
    renderPage(viewer);
    await screen.findByRole('link', { name: /Ejecución/ });
    const nav = screen.getByRole('navigation', { name: 'Temas y subtemas' });
    expect(nav.textContent).toContain('Finanzas');
    expect(nav.textContent).toContain('Presupuesto');                                           // subtema dentro del árbol
    fireEvent.click(screen.getByRole('button', { name: /^Finanzas/ }));                          // el tema principal agrupa
    expect(screen.getByRole('region', { name: 'Finanzas › Presupuesto' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Ejecución/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Buscar proyecto o unidad'), { target: { value: 'sueldos' } });
    expect(screen.queryByRole('link', { name: /Ejecución/ })).toBeNull();
    expect(screen.getByRole('link', { name: /Sueldos/ })).toBeTruthy();                          // la búsqueda ignora el tema elegido
    fireEvent.change(screen.getByLabelText('Buscar proyecto o unidad'), { target: { value: 'zzz' } });
    expect(screen.getByText(/Ningún proyecto coincide con «zzz»/)).toBeTruthy();
  });

  it('FE27-C: el cuestionario fija el nivel, solo se registra en subtemas y el aviso del nivel 2 sale antes y después de guardar', async () => {
    mockApi([]);
    axios.post.mockResolvedValue({ data: { ...R_RESTRICTED, created_by: 'u1' } });
    renderPage(editor);
    fireEvent.click(await screen.findByRole('button', { name: 'Registrar proyecto' }));
    fireEvent.change(await screen.findByLabelText('Título'), { target: { value: 'Sueldos' } });
    fireEvent.change(screen.getByLabelText('Enlace'), { target: { value: 'https://docs.google.com/spreadsheets/d/1' } });
    const topic = screen.getByLabelText('Tema');
    expect([...topic.options].map((o) => o.textContent)).toEqual(['Elige un tema', 'Finanzas › Presupuesto', 'Compras']);   // «Finanzas» agrupa: no se elige
    fireEvent.change(topic, { target: { value: 't3' } });
    expect(screen.getByText('Nivel 0 · Personal')).toBeTruthy();                                  // sin marcar nada
    fireEvent.click(screen.getByLabelText('Datos de funcionarios'));
    expect(screen.getByText('Nivel 1 · De unidad')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Datos de estudiantes'));                               // cualquiera de arriba → nivel 2
    expect(screen.getByText('Nivel 2 · Alto')).toBeTruthy();
    expect(screen.getByText(/no quedan\s+protegidos por el portal/)).toBeTruthy();               // aviso previo
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledWith('/api/v1/portal/resources',
      expect.objectContaining({ topic_id: 't3', data_categories: ['staff', 'students'], unit_id: null })));
    expect(axios.post.mock.calls[0][1]).not.toHaveProperty('catastro_level');                      // el nivel lo deduce el servidor
    expect(await screen.findByText(/quedó restringido/)).toBeTruthy();                            // aviso posterior
    expect(screen.getByText(/solicita a un administrador/)).toBeTruthy();
  });

  it('FE27-D: la carátula se pide al servidor y reemplaza la miniatura; sin carátula no se pide nada', async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:cover-1');
    axios.get.mockImplementation((url) => {
      if (url === '/api/v1/portal/topics') return Promise.resolve({ data: TOPICS });
      if (url === '/api/v1/portal/resources') return Promise.resolve({ data: [{ ...R_OPEN, has_cover: true, updated_at: 'v1' }, R_RESTRICTED] });
      if (url === '/api/v1/portal/resources/r1/cover') return Promise.resolve({ data: new Blob(['x'], { type: 'image/webp' }) });
      return Promise.resolve({ data: [] });
    });
    const { container } = renderPage(viewer);
    await waitFor(() => expect(container.querySelector('img[src="blob:cover-1"]')).toBeTruthy());
    expect(axios.get).toHaveBeenCalledWith('/api/v1/portal/resources/r1/cover', { responseType: 'blob' });
    expect(axios.get).not.toHaveBeenCalledWith('/api/v1/portal/resources/r2/cover', expect.anything());
  });
});
