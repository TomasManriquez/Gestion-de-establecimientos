/**
 * test_FE08_users_list_view.test.jsx
 * ──────────────────────────────────
 * Tarea: US-40 · Vista de usuarios (propuesta A + tabla compacta de C)
 *
 * Verifica que:
 *   - la lista pide /api/users con page_size 25 y pinta cada fila con sus 6 columnas
 *   - permisos: un chip principal y «+N» que abre el detalle; la fila no crece
 *   - última actividad es columna propia (relativa, fecha exacta en title, «—» si nunca)
 *   - estado compacto con etiqueta (Activo / Sin enviar / Inactivo)
 *   - los filtros viven en la URL y disparan una nueva consulta con los parámetros correctos
 *   - estados de carga, vacío, error y 403
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import axios from 'axios';

vi.mock('axios');

import UsersPage from '@/components/users/UsersPage';
import { ADMIN, ANA, CARLA, DARIO, ELENA, GABRIELA, USERS, apiError, installGets, page, usersListCalls } from './usersFixtures';

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.pathname + loc.search}</output>;
}

function renderPage(entry = '/configuracion/usuarios') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <UsersPage currentUser={ADMIN} />
      <Where />
    </MemoryRouter>,
  );
}

const rowOf = (name) => screen.getByText(name).closest('tr');

beforeEach(() => {
  vi.resetAllMocks();
  installGets();
});
afterEach(() => { vi.useRealTimers(); });

describe('FE08: lista de usuarios', () => {
  it('FE08-A: pide la primera página con page_size 25 y pinta una fila por usuario', async () => {
    renderPage();
    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
    expect(usersListCalls()[0][1].params).toEqual({ page: 1, page_size: 25 });
    expect(screen.getAllByRole('row')).toHaveLength(USERS.length + 1);
    expect(screen.getByText(/Mostrando/).textContent).toBe('Mostrando 5 de 5 usuarios');
    for (const h of ['Usuario', 'Unidad o establecimiento', 'Permisos', 'Últ. actividad', 'Estado']) {
      expect(screen.getByRole('columnheader', { name: h })).toBeInTheDocument();
    }
  });

  it('FE08-B: funcionario SLEP muestra su unidad y código; establecimiento muestra RBD y cargos', async () => {
    renderPage();
    await screen.findByText('Ana Pérez');
    const ana = rowOf('Ana Pérez');
    expect(within(ana).getByText('Tecnologías de la Información')).toBeInTheDocument();
    expect(within(ana).getByText('AF-TI')).toBeInTheDocument();
    const dario = rowOf('Darío Vera');
    expect(within(dario).getByText('ESCUELA RURAL EL ROBLE')).toBeInTheDocument();
    expect(within(dario).getByText('RBD 7801 · Docente, Encargado PIE')).toBeInTheDocument();
  });

  it('FE08-C: un permiso = un chip; sin permisos = «Sin accesos»; varios = chip principal + «+N»', async () => {
    renderPage();
    await screen.findByText('Ana Pérez');
    expect(within(rowOf('Ana Pérez')).getByText('Datos · Editor')).toBeInTheDocument();
    expect(within(rowOf('Ana Pérez')).queryByRole('button', { name: /Ver los/ })).not.toBeInTheDocument();
    expect(within(rowOf('Elena Mora')).getByText('Sin accesos')).toBeInTheDocument();
    const carla = rowOf('Carla Soto');
    expect(within(carla).getByText('Admin global')).toBeInTheDocument();
    expect(within(carla).getByRole('button', { name: 'Ver los 3 permisos de Carla Soto' })).toHaveTextContent('+2');
  });

  it('FE08-D: «+2» abre el detalle con las tres plataformas', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    await user.click(within(rowOf('Carla Soto')).getByRole('button', { name: /Ver los 3 permisos/ }));
    const detail = await screen.findByText('Permisos de Carla Soto');
    const list = within(detail.closest('div')).getByRole('list');
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(within(list).getByText('Sello Verde')).toBeInTheDocument();
  });

  it('FE08-E: la última actividad es una columna propia con <time>; «—» si nunca ingresó', async () => {
    renderPage();
    await screen.findByText('Ana Pérez');
    const t = within(rowOf('Ana Pérez')).getByText(/^hace |^ayer|^ahora/);
    expect(t.tagName).toBe('TIME');
    expect(t).toHaveAttribute('dateTime', '2026-10-07T10:42:00');
    expect(t.getAttribute('title')).toMatch(/2026/);
    const never = within(rowOf('Darío Vera')).getByText('—');
    expect(never).toHaveAttribute('title', 'Nunca ha ingresado');
  });

  it('FE08-F: el estado es un punto + etiqueta corta, y la fila tiene altura fija', async () => {
    renderPage();
    await screen.findByText('Ana Pérez');
    expect(within(rowOf('Ana Pérez')).getByText('Activo')).toBeInTheDocument();
    expect(within(rowOf('Elena Mora')).getByText('Sin enviar')).toBeInTheDocument();
    expect(within(rowOf('Gabriela Ríos')).getByText('Inactivo')).toBeInTheDocument();
    for (const u of USERS) expect(rowOf(`${u.first_name} ${u.last_name}`).className).toMatch(/\bh-16\b/);
  });

  it('FE08-R: la columna Usuario tiene ancho acotado y la de unidad se queda con el espacio libre', async () => {
    const { container } = renderPage();
    await screen.findByText('Ana Pérez');
    const cols = [...container.querySelectorAll('colgroup col')];
    expect(cols).toHaveLength(7);
    expect(cols[1].className).toBe('w-72');   // Usuario: acotada
    expect(cols[2].className).toBe('');        // Unidad o establecimiento: flexible
  });

  it('FE08-G: mientras carga muestra el esqueleto y luego la tabla', async () => {
    let resolve;
    installGets({ '/api/users': () => new Promise((r) => { resolve = r; }) });
    renderPage();
    expect(screen.getByLabelText('Cargando usuarios')).toHaveAttribute('aria-busy', 'true');
    await waitFor(() => expect(resolve).toBeTypeOf('function'));
    resolve(page([ANA]));
    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
    expect(screen.queryByLabelText('Cargando usuarios')).not.toBeInTheDocument();
  });

  it('FE08-H: sin resultados muestra el estado vacío; con filtros ofrece «Limpiar filtros»', async () => {
    installGets({ '/api/users': () => page([]) });
    renderPage('/configuracion/usuarios?status=disabled');
    expect(await screen.findByText('No hay usuarios con esos criterios')).toBeInTheDocument();
    expect(screen.getByText('Prueba quitando algún filtro.')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/configuracion\/usuarios$/));
  });

  it('FE08-I: un error de red muestra una alerta con el mensaje', async () => {
    installGets({ '/api/users': () => { throw new Error('boom'); } });
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('No se pudo cargar la lista');
  });

  it('FE08-J: 403 reemplaza toda la vista por «Sin acceso»', async () => {
    installGets({ '/api/users': () => { throw apiError(403, 'Insufficient permissions'); } });
    renderPage();
    expect(await screen.findByText('Sin acceso')).toBeInTheDocument();
    expect(screen.queryByLabelText('Buscar')).not.toBeInTheDocument();
  });
});

describe('FE08: filtros en la URL', () => {
  it('FE08-K: los parámetros de la URL llegan al API con los nombres del backend', async () => {
    renderPage('/configuracion/usuarios?q=ana&unit=u-af&sub=0&kind=slep&platform=datos&role=editor&status=active&page=2');
    await screen.findByText('Ana Pérez');
    expect(usersListCalls()[0][1].params).toEqual({
      page: 2, page_size: 25, q: 'ana', unit_id: 'u-af', include_descendants: false,
      kind: 'slep', platform: 'datos', role: 'editor', status: 'active',
    });
    expect(screen.getByLabelText('Buscar')).toHaveValue('ana');
  });

  it('FE08-L: unidad sin «sub» incluye subunidades por defecto', async () => {
    renderPage('/configuracion/usuarios?unit=u-af');
    await screen.findByText('Ana Pérez');
    expect(usersListCalls()[0][1].params).toMatchObject({ unit_id: 'u-af', include_descendants: true });
    expect(screen.getByRole('checkbox', { name: 'Incluir subunidades' })).toBeChecked();
  });

  it('FE08-M: escribir en Buscar espera 300 ms (debounce), escribe ?q= y reinicia la página', async () => {
    const user = userEvent.setup();
    renderPage('/configuracion/usuarios?page=3');
    await screen.findByText('Ana Pérez');
    const before = usersListCalls().length;
    await user.type(screen.getByLabelText('Buscar'), 'carla');
    expect(usersListCalls().length).toBe(before);
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/configuracion/usuarios?q=carla'));
    expect(screen.getByTestId('where').textContent).not.toMatch(/page=/);
    await waitFor(() => expect(usersListCalls().at(-1)[1].params).toMatchObject({ q: 'carla', page: 1 }));
  });

  it('FE08-N: elegir un Estado escribe ?status= y consulta de nuevo', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    await user.click(screen.getByRole('combobox', { name: 'Estado' }));
    await user.click(await screen.findByRole('option', { name: 'Inactivo' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('?status=disabled'));
    await waitFor(() => expect(usersListCalls().at(-1)[1].params).toMatchObject({ status: 'disabled' }));
  });

  it('FE08-O: con varias páginas muestra la paginación y «Siguiente» avanza ?page=', async () => {
    installGets({ '/api/users': () => page([ANA, CARLA], { total: 40, total_pages: 2 }) });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Ana Pérez');
    expect(screen.getByText(/Mostrando/).textContent).toBe('Mostrando 2 de 40 usuarios');
    await user.click(screen.getByRole('link', { name: /siguiente|next/i }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('page=2'));
  });

  it('FE08-P: «Limpiar» vacía la URL y la caja de búsqueda', async () => {
    const user = userEvent.setup();
    renderPage('/configuracion/usuarios?q=ana&status=active');
    await screen.findByText('Ana Pérez');
    await user.click(screen.getByRole('button', { name: 'Limpiar' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/configuracion\/usuarios$/));
    expect(screen.getByLabelText('Buscar')).toHaveValue('');
  });

  it('FE08-Q: «Importar CSV» está deshabilitado (F4) y «Crear usuario» habilitado', async () => {
    renderPage();
    await screen.findByText('Ana Pérez');
    expect(screen.getByRole('button', { name: /Importar CSV/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Crear usuario/ })).toBeEnabled();
  });
});
