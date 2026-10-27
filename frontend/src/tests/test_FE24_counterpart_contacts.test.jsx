/**
 * test_FE24_counterpart_contacts.test.jsx
 * ───────────────────────────────────────
 * Tarea: ficha · listado de contrapartes con contacto visible y copiable
 *
 * Verifica que:
 *   - el correo y el teléfono se ven como texto seleccionable, sin hipervínculos (mailto:/tel:)
 *   - cada dato tiene su botón de copiar, que escribe ese dato en el portapapeles y avisa
 *   - si el portapapeles falla, se avisa y no se rompe la fila
 *   - el director no se repite en «Equipo del establecimiento» (y el contador baja), salvo que la ficha
 *     no tenga director registrado
 *   - las contrapartes técnicas del SLEP no pierden a nadie
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import { toast } from 'sonner';

const VIEWER = { role: 'viewer', access: [{ platform_id: 'datos', role: 'viewer', capabilities: ['read'] }] };

const establishment = (director = 'Juan Ojeda Cárcamo') => ({
  rbd: '7722', rbd_full: '7722-3', name: 'LICEO PUNTA DE RIELES', comuna: 'PUERTO VARAS', area_type: 'URBANO',
  address: 'Arturo Prat 501', general_info: { director, category: '9. COLEGIO' },
  connectivity: {}, printers: { owned: [], leased: [] },
});

const COUNTERPARTS = [
  { _id: 'c1', origin: 'ESTABLECIMIENTO', role: 'UTP_JEFE', name: 'Ernesto Vargas', email: 'ernesto.vargas@slepllanquihue.cl', phone: '+56912345678' },
  { _id: 'c2', origin: 'ESTABLECIMIENTO', role: 'PIE_ENCARGADO', name: 'Estefanía Godoy Noriega', email: 'estefania.godoy@slepllanquihue.cl' },
  { _id: 'c3', origin: 'ESTABLECIMIENTO', role: 'DIRECTOR', name: 'Juan Ojeda Cárcamo', email: 'juan.ojeda@slepllanquihue.cl', phone: '+56987654321' },
  { _id: 'c4', origin: 'SLEP', role: 'GESTOR_INFRAESTRUCTURA', name: 'Leonardo Oyarzo', email: 'leonardo.oyarzo@slepllanquihue.cl' },
];

async function renderFicha(est = establishment()) {
  axios.get.mockImplementation((url) => {
    if (url.includes('/api/establishments/7722')) return Promise.resolve({ data: est });
    if (url.includes('/api/counterparts/establishment/7722')) return Promise.resolve({ data: COUNTERPARTS });
    return Promise.resolve({ data: [] });
  });
  const { default: Ficha } = await import('../../components/FichaEstablecimiento.jsx');
  render(
    <MemoryRouter initialEntries={['/establecimientos/7722']}>
      <Routes><Route path="/establecimientos/:rbd" element={<Ficha currentUser={VIEWER} />} /></Routes>
    </MemoryRouter>,
  );
  await screen.findByText('Ernesto Vargas');
  return screen.getByRole('heading', { name: /Equipo del establecimiento/ }).closest('section');
}

let writeText;
// userEvent.setup() instala su propio portapapeles: el doble propio se instala después de crear el `user`.
const installClipboard = () => Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
beforeEach(() => {
  vi.resetAllMocks();
  writeText = vi.fn().mockResolvedValue(undefined);
  installClipboard();
});

describe('FE24: contacto de las contrapartes', () => {
  it('FE24-A: correo y teléfono se muestran como texto, no como enlaces', async () => {
    const team = await renderFicha();
    expect(within(team).getByText('ernesto.vargas@slepllanquihue.cl')).toBeInTheDocument();
    expect(within(team).getByText('+56912345678')).toBeInTheDocument();
    expect(team.querySelector('a[href^="mailto:"], a[href^="tel:"]')).toBeNull();
    expect(within(team).getByText('ernesto.vargas@slepllanquihue.cl').className).toMatch(/select-text/);
  });

  it('FE24-B: el botón copia el dato exacto y avisa', async () => {
    const user = userEvent.setup();
    installClipboard();
    const team = await renderFicha();
    await user.click(within(team).getByRole('button', { name: 'Copiar correo de Ernesto Vargas' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('ernesto.vargas@slepllanquihue.cl'));
    expect(toast.success).toHaveBeenCalledWith('Correo copiado');
    await user.click(within(team).getByRole('button', { name: 'Copiar teléfono de Ernesto Vargas' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('+56912345678'));
    expect(toast.success).toHaveBeenCalledWith('Teléfono copiado');
  });

  it('FE24-C: sin teléfono no hay botón de teléfono, y la fila no se rompe', async () => {
    const team = await renderFicha();
    expect(within(team).queryByRole('button', { name: 'Copiar teléfono de Estefanía Godoy Noriega' })).not.toBeInTheDocument();
    expect(within(team).getByRole('button', { name: 'Copiar correo de Estefanía Godoy Noriega' })).toBeInTheDocument();
  });

  it('FE24-D: si el portapapeles falla, lo avisa con un error', async () => {
    const user = userEvent.setup();
    installClipboard();
    writeText.mockRejectedValue(new Error('denied'));
    document.execCommand = vi.fn(() => false);
    const team = await renderFicha();
    await user.click(within(team).getByRole('button', { name: 'Copiar correo de Ernesto Vargas' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('FE24-E: el director no se repite en el equipo y el contador baja', async () => {
    const team = await renderFicha();
    expect(within(team).queryByText('Juan Ojeda Cárcamo')).not.toBeInTheDocument();
    expect(within(team).queryByText('juan.ojeda@slepllanquihue.cl')).not.toBeInTheDocument();
    expect(within(team).getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Juan Ojeda Cárcamo')).toBeInTheDocument();           // sigue arriba, en «Director / Encargado»
  });

  it('FE24-F: sin director registrado en la ficha, la contraparte director se conserva', async () => {
    const team = await renderFicha(establishment(''));
    expect(within(team).getByText('Juan Ojeda Cárcamo')).toBeInTheDocument();
    expect(within(team).getByText('3')).toBeInTheDocument();
  });

  it('FE24-G: las contrapartes técnicas del SLEP se conservan', async () => {
    await renderFicha();
    const slep = screen.getByRole('heading', { name: /Contrapartes técnicas del SLEP/ }).closest('section');
    expect(within(slep).getByText('Leonardo Oyarzo')).toBeInTheDocument();
    expect(within(slep).getByRole('button', { name: 'Copiar correo de Leonardo Oyarzo' })).toBeInTheDocument();
  });
});

describe('FE24: títulos normalizados', () => {
  it('FE24-H: el cargo de cada contraparte usa el mismo estilo que «Director / Encargado»', async () => {
    const team = await renderFicha();
    const detail = screen.getByText('Director / Encargado');
    const role = within(team).getByText('Utp jefe');
    expect(role.className).toBe(`block ${detail.className}`);
    expect(detail.className).toMatch(/text-xs/);
    expect(detail.className).not.toMatch(/font-semibold|text-\[11px\]/);
  });
});

describe('FE24: contacto del director', () => {
  const withContact = () => ({ ...establishment(), general_info: { ...establishment().general_info,
    director_email: 'juan.ojeda@slepllanquihue.cl', director_phone: '+56987654321' } });

  it('FE24-I: el popup «Contacto» muestra correo y teléfono como texto, sin enlaces, y los copia', async () => {
    const user = userEvent.setup();
    installClipboard();
    await renderFicha(withContact());
    await user.click(screen.getByRole('button', { name: 'Contacto' }));
    const popup = await screen.findByText('Director / Encargado', { selector: 'span' }).then((el) => el.closest('#director-contact-popup'));
    expect(within(popup).getByText('juan.ojeda@slepllanquihue.cl')).toBeInTheDocument();
    expect(within(popup).getByText('+56987654321')).toBeInTheDocument();
    expect(popup.querySelector('a[href^="mailto:"], a[href^="tel:"]')).toBeNull();
    await user.click(within(popup).getByRole('button', { name: 'Copiar correo de Juan Ojeda Cárcamo' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('juan.ojeda@slepllanquihue.cl'));
  });

  it('FE24-J: sin correo ni teléfono registrados, el popup lo dice', async () => {
    const user = userEvent.setup();
    await renderFicha();
    await user.click(screen.getByRole('button', { name: 'Contacto' }));
    expect(await screen.findByText('Sin correo registrado')).toBeInTheDocument();
    expect(screen.getByText('Sin teléfono registrado')).toBeInTheDocument();
  });
});
