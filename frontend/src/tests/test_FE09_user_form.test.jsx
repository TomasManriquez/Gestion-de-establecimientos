/**
 * test_FE09_user_form.test.jsx
 * ────────────────────────────
 * Tarea: US-40 · Crear y editar usuario en un diálogo (un solo formulario)
 *
 * Verifica que:
 *   - «Crear usuario» abre un diálogo con título y valida los obligatorios antes de llamar al API
 *   - funcionario SLEP envía unit_id y nunca rbd; el interruptor limpia los campos del otro modo
 *   - usuario de establecimiento envía rbd + cargos y nunca unit_id
 *   - un 409 en el correo se marca en el propio campo; un error sin campo va en una alerta
 *   - mientras guarda, el botón queda deshabilitado (sin doble envío)
 *   - editar envía solo lo que cambió
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

import UsersPage from '@/components/users/UsersPage';
import { ADMIN, ANA, DARIO, apiError, installGets, makeUser, usersListCalls } from './usersFixtures';

const renderPage = () => render(<MemoryRouter initialEntries={['/configuracion/usuarios']}><UsersPage currentUser={ADMIN} /></MemoryRouter>);

async function openCreate(user) {
  renderPage();
  await screen.findByText('Ana Pérez');
  await user.click(screen.getByRole('button', { name: /Crear usuario/ }));
  return screen.findByRole('dialog', { name: 'Crear usuario' });
}

async function pickOption(user, trigger, optionName) {
  await user.click(trigger);
  await user.click(await screen.findByRole('option', { name: optionName }));
}

async function fillBasics(user, dialog, email = 'nuevo.usuario@slepllanquihue.cl') {
  await user.type(within(dialog).getByLabelText('Nombre'), 'Nuevo');
  await user.type(within(dialog).getByLabelText('Apellido'), 'Usuario');
  await user.type(within(dialog).getByLabelText('Correo institucional'), email);
}

beforeEach(() => {
  vi.resetAllMocks();
  installGets();
});

describe('FE09: crear usuario', () => {
  it('FE09-A: abre un diálogo con título accesible y por defecto es funcionario SLEP', async () => {
    const user = userEvent.setup();
    const dialog = await openCreate(user);
    expect(within(dialog).getByRole('switch', { name: 'Funcionario SLEP' })).toBeChecked();
    expect(within(dialog).getByLabelText('Unidad')).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Establecimiento')).not.toBeInTheDocument();
  });

  it('FE09-B: con campos obligatorios vacíos marca cada campo y NO llama al API', async () => {
    const user = userEvent.setup();
    const dialog = await openCreate(user);
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    expect(await within(dialog).findByText('Ingresa el nombre.')).toBeInTheDocument();
    expect(within(dialog).getByText('Ingresa el apellido.')).toBeInTheDocument();
    expect(within(dialog).getByText('Ingresa el correo institucional.')).toBeInTheDocument();
    expect(within(dialog).getByText('Selecciona la unidad.')).toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('FE09-C: SLEP válido envía unit_id y nunca rbd, avisa y recarga la lista', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: makeUser({ _id: 'u9', first_name: 'Nuevo', last_name: 'Usuario', invitation: { sent: true } }) });
    const dialog = await openCreate(user);
    await fillBasics(user, dialog);
    await pickOption(user, within(dialog).getByLabelText('Unidad'), 'Tecnologías de la Información');
    const before = usersListCalls().length;
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
    const [url, body] = axios.post.mock.calls[0];
    expect(url).toBe('/api/users');
    expect(body).toMatchObject({ first_name: 'Nuevo', last_name: 'Usuario', email: 'nuevo.usuario@slepllanquihue.cl', is_slep_staff: true, unit_id: 'u-ti', rbd: null, positions: [] });
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Crear usuario' })).not.toBeInTheDocument());
    await waitFor(() => expect(usersListCalls().length).toBeGreaterThan(before));
  });

  it('FE09-D: apagar «Funcionario SLEP» muestra establecimiento y cargo y descarta la unidad elegida', async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: makeUser({ invitation: { sent: false, last_error: 'mail_not_configured' } }) });
    const dialog = await openCreate(user);
    await fillBasics(user, dialog);
    await pickOption(user, within(dialog).getByLabelText('Unidad'), 'Tecnologías de la Información');
    await user.click(within(dialog).getByRole('switch', { name: 'Funcionario SLEP' }));
    expect(within(dialog).queryByLabelText('Unidad')).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole('combobox', { name: 'Establecimiento' }));
    await user.click(await screen.findByText('LICEO LOS ALERCES'));
    await pickOption(user, within(dialog).getByRole('combobox', { name: 'Cargo 1' }), 'Docente');
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));

    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
    expect(axios.post.mock.calls[0][1]).toMatchObject({ is_slep_staff: false, unit_id: null, rbd: '7722', positions: ['DOCENTE'] });
  });

  it('FE09-E: usuario de establecimiento sin establecimiento ni cargo no se envía', async () => {
    const user = userEvent.setup();
    const dialog = await openCreate(user);
    await fillBasics(user, dialog);
    await user.click(within(dialog).getByRole('switch', { name: 'Funcionario SLEP' }));
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    expect(await within(dialog).findByText('Selecciona el establecimiento.')).toBeInTheDocument();
    expect(within(dialog).getByText('Selecciona al menos un cargo.')).toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('FE09-F: el 409 de correo duplicado queda en el campo Correo y el diálogo sigue abierto', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue(apiError(409, { code: 'duplicate', message: 'Ya existe un usuario con ese correo', field: 'email' }));
    const dialog = await openCreate(user);
    await fillBasics(user, dialog, 'ana.perez@slepllanquihue.cl');
    await pickOption(user, within(dialog).getByLabelText('Unidad'), 'Tecnologías de la Información');
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    const msg = await within(dialog).findByText('Ya existe un usuario con ese correo');
    expect(msg.closest('[data-slot="field"]') ?? msg.parentElement).toContainElement(within(dialog).getByLabelText('Correo institucional'));
    expect(within(dialog).getByLabelText('Correo institucional')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('dialog', { name: 'Crear usuario' })).toBeInTheDocument();
  });

  it('FE09-G: un error sin campo (red) aparece como alerta del formulario', async () => {
    const user = userEvent.setup();
    axios.post.mockRejectedValue({});
    const dialog = await openCreate(user);
    await fillBasics(user, dialog);
    await pickOption(user, within(dialog).getByLabelText('Unidad'), 'Tecnologías de la Información');
    await user.click(within(dialog).getByRole('button', { name: 'Crear y enviar invitación' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('No se pudo conectar con el servidor');
  });

  it('FE09-H: mientras guarda, el botón está deshabilitado y un segundo clic no duplica el POST', async () => {
    const user = userEvent.setup();
    let resolve;
    axios.post.mockImplementation(() => new Promise((r) => { resolve = r; }));
    const dialog = await openCreate(user);
    await fillBasics(user, dialog);
    await pickOption(user, within(dialog).getByLabelText('Unidad'), 'Tecnologías de la Información');
    const submit = within(dialog).getByRole('button', { name: 'Crear y enviar invitación' });
    await user.click(submit);
    await waitFor(() => expect(submit).toBeDisabled());
    await user.click(submit);
    expect(axios.post).toHaveBeenCalledTimes(1);
    resolve({ data: makeUser({ invitation: { sent: true } }) });
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Crear usuario' })).not.toBeInTheDocument());
  });
});

describe('FE09: editar usuario', () => {
  async function openEdit(user, name, fullName) {
    renderPage();
    await screen.findByText(fullName);
    await user.click(screen.getByRole('button', { name: `Acciones de ${fullName}` }));
    await user.click(await screen.findByRole('menuitem', { name }));
    return screen.findByRole('dialog', { name: 'Editar usuario' });
  }

  it('FE09-I: precarga los datos del usuario', async () => {
    const user = userEvent.setup();
    const dialog = await openEdit(user, 'Editar datos', 'Ana Pérez');
    expect(within(dialog).getByLabelText('Nombre')).toHaveValue('Ana');
    expect(within(dialog).getByLabelText('Correo institucional')).toHaveValue(ANA.email);
    expect(within(dialog).getByLabelText('Anexo')).toHaveValue('4521');
  });

  it('FE09-J: guardar envía solo los campos que cambiaron (PATCH)', async () => {
    const user = userEvent.setup();
    axios.patch.mockResolvedValue({ data: makeUser({ work_extension: '9999' }) });
    const dialog = await openEdit(user, 'Editar datos', 'Ana Pérez');
    const ext = within(dialog).getByLabelText('Anexo');
    await user.clear(ext);
    await user.type(ext, '9999');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(axios.patch).toHaveBeenCalledTimes(1));
    expect(axios.patch).toHaveBeenCalledWith('/api/users/u1', { work_extension: '9999' });
  });

  it('FE09-K: guardar sin cambios cierra el diálogo y no llama al API', async () => {
    const user = userEvent.setup();
    const dialog = await openEdit(user, 'Editar datos', 'Ana Pérez');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Editar usuario' })).not.toBeInTheDocument());
    expect(axios.patch).not.toHaveBeenCalled();
  });

  it('FE09-L: usuario de establecimiento precarga el cargo y muestra «Agregar otro cargo»', async () => {
    const user = userEvent.setup();
    const dialog = await openEdit(user, 'Editar datos', 'Darío Vera');
    expect(within(dialog).getByRole('switch', { name: 'Funcionario SLEP' })).not.toBeChecked();
    expect(within(dialog).getByRole('combobox', { name: 'Cargo 1' })).toHaveTextContent('Docente');
    expect(within(dialog).getByRole('combobox', { name: 'Cargo 2' })).toHaveTextContent('Encargado PIE');
    expect(DARIO.positions).toHaveLength(2);
  });
});
