/**
 * test_FE24_tablero_matricula_page.test.jsx
 * ─────────────────────────────────────────
 * Tarea: página del tablero de matrícula (ADR-018) sobre GET /api/analytics/enrollment
 *
 * Verifica que:
 *   - carga con el último año y la comparación anterior, y las tarjetas muestran los números esperados
 *   - cambiar el año recalcula y reinicia la comparación
 *   - los gráficos filtran (barra de comuna) y «Limpiar filtros» restablece
 *   - una tarjeta sin dato ese año lo declara y ofrece ir al último año con dato
 *   - el origen del dato se abre desde cada tarjeta y se cierra con Escape
 *   - estados de error (con reintento) y sin datos
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import axios from 'axios';
import TableroMatricula from '@/components/TableroMatricula';

vi.mock('axios');

const DATASET = {
  establishments: [
    { rbd: 'A', name: 'Escuela A', comuna: 'FRESIA', area_type: 'URBANO', category: '4. ESCUELA COMPLETA', status: 'active', closed_year: null },
    { rbd: 'B', name: 'Escuela B', comuna: 'FRESIA', area_type: 'RURAL', category: '6. RURAL MULTIGRADO', status: 'active', closed_year: null },
    { rbd: 'C', name: 'Escuela C', comuna: 'FRUTILLAR', area_type: 'URBANO', category: '4. ESCUELA COMPLETA', status: 'closed', closed_year: 2025 },
    { rbd: 'D', name: 'Jardín D', comuna: 'FRUTILLAR', area_type: 'URBANO', category: '2. J. INFANTIL - S. CUNA', status: 'active', closed_year: null },
    { rbd: 'E', name: 'Escuela E', comuna: 'FRUTILLAR', area_type: 'RURAL', category: '9. COLEGIO', status: 'active', closed_year: null },
  ],
  points: [
    { rbd: 'A', year: 2024, enrollment: 90 },
    { rbd: 'A', year: 2025, enrollment: 100, attendance: 0.9, attendance_as_of: '' },
    { rbd: 'A', year: 2026, enrollment: 110, enrollment_as_of: '2026-03', teachers: 8 },
    { rbd: 'B', year: 2025, enrollment: 20, attendance: 0.8 },
    { rbd: 'B', year: 2026, enrollment: 10, enrollment_as_of: '2026-03', teachers: 2 },
    { rbd: 'C', year: 2024, enrollment: 60 },
    { rbd: 'C', year: 2025, enrollment: 50, attendance: 0.7 },
    { rbd: 'D', year: 2025, enrollment: 30 },
    { rbd: 'D', year: 2026, enrollment: 40, enrollment_as_of: '2026-03' },
    { rbd: 'E', year: 2026, enrollment: 70, enrollment_as_of: '2026-03', teachers: 5 },
  ],
  years: [2024, 2025, 2026],
  indicators: {
    enrollment: { label: 'Matrícula', years: [2024, 2025, 2026] },
    attendance: { label: 'Asistencia', years: [2025] },
    teachers: { label: 'Docentes', years: [2026] },
    assistants: { label: 'Asistentes', years: [] },
  },
};

const kpi = (name) => screen.getByRole('button', { name: new RegExp(`^${name}.*ver origen del dato`) }).parentElement;

beforeEach(() => {
  vi.resetAllMocks();
  axios.get.mockResolvedValue({ data: DATASET });
});

describe('FE24: tablero de matrícula', () => {
  it('FE24-A: carga con el último año y la comparación anterior', async () => {
    render(<TableroMatricula />);
    expect(screen.getByRole('status')).toHaveTextContent(/cargando/i);
    await screen.findByRole('heading', { name: 'Matrícula' });
    expect(axios.get).toHaveBeenCalledWith('/api/analytics/enrollment', expect.anything());
    expect(screen.getByLabelText('Año')).toHaveValue('2026');
    expect(screen.getByLabelText('Comparar con')).toHaveValue('2025');
    expect(within(kpi('Matrícula 2026')).getByText('230')).toBeInTheDocument();                // 110 + 10 + 40 + 70
    expect(within(kpi('Matrícula 2026')).getByText(/\+\d+,\d %.* vs 2025|vs 2025/)).toBeInTheDocument();
    expect(within(kpi('Matrícula 2026')).getByText(/3 establecimientos presentes en ambos años/)).toBeInTheDocument();
    expect(within(kpi('Establecimientos')).getByText(/1 entran · 1 salen vs 2025|1 entran/)).toBeInTheDocument();
    expect(screen.getByText('corte mar 2026')).toBeInTheDocument();
  });

  it('FE24-B: cambiar el año recalcula y reinicia la comparación', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    fireEvent.change(screen.getByLabelText('Año'), { target: { value: '2025' } });
    expect(screen.getByLabelText('Comparar con')).toHaveValue('2024');
    expect(within(kpi('Matrícula 2025')).getByText('200')).toBeInTheDocument();               // A 100 + B 20 + C 50 + D 30
    expect(screen.getByText('año completo')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Comparar con'), { target: { value: '' } });
    expect(within(kpi('Matrícula 2025')).getByText('sin comparar')).toBeInTheDocument();
  });

  it('FE24-C: un gráfico filtra y «Limpiar filtros» restablece', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Frutillar/ }));                       // barra de comuna
    expect(screen.getByLabelText('Comuna')).toHaveValue('FRUTILLAR');
    expect(within(kpi('Matrícula 2026')).getByText('110')).toBeInTheDocument();               // D 40 + E 70
    fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    expect(within(kpi('Matrícula 2026')).getByText('230')).toBeInTheDocument();
  });

  it('FE24-D: el interruptor de jardines excluye ese tipo', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    fireEvent.click(screen.getByRole('switch', { name: /incluir jardines/i }));
    expect(within(kpi('Matrícula 2026')).getByText('190')).toBeInTheDocument();               // sin D
  });

  it('FE24-E: sin asistencia ese año lo dice y ofrece ir al último año con dato', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    const att = kpi('Asistencia 2026');
    expect(within(att).getByText('—')).toBeInTheDocument();
    expect(within(att).getByText('sin dato este año')).toBeInTheDocument();
    fireEvent.click(within(att).getByRole('button', { name: /Último dato: 2025/ }));
    expect(screen.getByLabelText('Año')).toHaveValue('2025');
    expect(within(kpi('Asistencia 2025')).getByText(/ponderada · 3 de 4 con dato/)).toBeInTheDocument();
    expect(within(kpi('Asistencia 2025')).getByText('82,9 %')).toBeInTheDocument();           // (90 + 16 + 35) / 170
  });

  it('FE24-F: el origen del dato se abre desde la tarjeta y se cierra con Escape', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    fireEvent.click(screen.getByRole('button', { name: /^Matrícula 2026.*ver origen del dato/ }));
    const panel = screen.getByRole('complementary', { name: 'Origen del dato' });
    expect(within(panel).getByText('Matrícula 2026')).toBeInTheDocument();
    expect(within(panel).getByText('2024, 2025, 2026')).toBeInTheDocument();
    expect(within(panel).getByText(/solo los establecimientos presentes en ambos años/)).toBeInTheDocument();
    expect(within(panel).getByText(/D36/)).toBeInTheDocument();                              // no inventa quién cargó el dato
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('complementary', { name: 'Origen del dato' })).not.toBeInTheDocument();
  });

  it('FE24-G: error de carga con reintento', async () => {
    axios.get.mockRejectedValueOnce(new Error('red'));
    render(<TableroMatricula />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/no se pudieron cargar/i);
    fireEvent.click(screen.getByRole('button', { name: /reintentar/i }));
    await screen.findByRole('heading', { name: 'Matrícula' });
  });

  it('FE24-H: sin datos cargados', async () => {
    axios.get.mockResolvedValue({ data: { establishments: [], points: [], years: [], indicators: {} } });
    render(<TableroMatricula />);
    expect(await screen.findByText(/aún no hay datos de matrícula/i)).toBeInTheDocument();
  });

  it('FE24-I: los controles son accesibles (grupos con nombre y estado)', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    const area = screen.getByRole('group', { name: 'Área' });
    fireEvent.click(within(area).getByRole('button', { name: 'Rural' }));
    expect(within(area).getByRole('button', { name: 'Rural' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(kpi('Matrícula 2026')).getByText('80')).toBeInTheDocument();                // B 10 + E 70
  });

  it('FE24-J: la evolución por comuna rotula el valor exacto de cada punto anual', async () => {
    render(<TableroMatricula />);
    await screen.findByRole('heading', { name: 'Matrícula' });
    fireEvent.click(within(screen.getByRole('group', { name: 'Vista de la evolución' })).getByRole('button', { name: 'Por comuna' }));
    const chart = screen.getByRole('img', { name: /Matrícula por año\. Fresia: 2024 90, 2025 120, 2026 120\. Frutillar: 2024 60, 2025 80, 2026 110/ });
    const labels = Array.from(chart.querySelectorAll('text')).map((t) => t.textContent);
    ['90', '120', '60', '80', '110'].forEach((v) => expect(labels).toContain(v));
    expect(labels.filter((t) => t === '120')).toHaveLength(2);                              // Fresia 2025 y 2026
    expect(labels).toContain('Fresia');
    expect(labels).toContain('Frutillar');
  });
});
