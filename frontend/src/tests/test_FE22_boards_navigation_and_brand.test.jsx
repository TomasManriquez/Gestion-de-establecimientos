/**
 * test_FE22_boards_navigation_and_brand.test.jsx
 * ──────────────────────────────────────────────
 * Tarea: identidad visual del SLEP y acceso directo a /tableros/matricula
 *
 * Verifica que:
 *   - /dashboard y /tableros redirigen a /tableros/matricula (los marcadores antiguos siguen vivos)
 *   - «Tableros» queda activo en cualquier /tableros/*, abierto o colapsado
 *   - el layout muestra el logo del SLEP con su nombre accesible y la franja de seis colores
 *   - la barra lateral usa la paleta institucional y el tipo Calibri/Carlito
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import { readFileSync } from 'fs';
import { join } from 'path';
import AppLayout from '@/components/AppLayout';
import { ADMIN } from './usersFixtures';

const src = (rel) => readFileSync(join(process.cwd(), rel), 'utf-8');

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout currentUser={ADMIN} onLogout={() => {}} />}>
          <Route path="/tableros/matricula" element={<p>Tablero de matrícula</p>} />
          <Route path="/tableros/otro" element={<p>Otro tablero</p>} />
          <Route path="/tableros" element={<Navigate to="/tableros/matricula" replace />} />
          <Route path="/dashboard" element={<Navigate to="/tableros/matricula" replace />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => { localStorage.clear(); });

describe('FE22: navegación a Tableros', () => {
  it.each(['/dashboard', '/tableros'])('FE22-A: %s redirige a Matrícula', (path) => {
    renderAt(path);
    expect(screen.getByText('Tablero de matrícula')).toBeInTheDocument();
  });

  it('FE22-B: «Tableros» apunta a Matrícula y está activo en cualquier /tableros/*', () => {
    renderAt('/tableros/otro');
    const link = screen.getByRole('link', { name: 'Tableros' });
    expect(link).toHaveAttribute('href', '/tableros/matricula');
    expect(link.className).toContain('bg-slep-active');
    expect(screen.queryByRole('link', { name: 'Panel General' })).not.toBeInTheDocument();
  });

  it('FE22-C: App.jsx declara las rutas de tableros y conserva /dashboard', () => {
    const app = src('src/App.jsx');
    expect(app).toContain('path="/tableros/matricula"');
    expect(app).toMatch(/path="\/dashboard"[^>]*Navigate to="\/tableros\/matricula"/);
  });
});

describe('FE22: identidad visual', () => {
  it('FE22-D: logo con nombre accesible y franja de seis colores', () => {
    const { container } = renderAt('/tableros/matricula');
    const logo = screen.getByRole('img', { name: 'Servicio Local de Educación Pública Llanquihue' });
    expect(logo).toHaveAttribute('src', '/slep-llanquihue.png');
    expect(container.querySelectorAll('header [aria-hidden="true"] > span')).toHaveLength(6);
  });

  it('FE22-E: paleta y tipografía institucionales', () => {
    const tw = src('tailwind.config.js');
    ['#0b3a66', '#1b5a96', '#76c93b', '#f24f63', '#f8c928'].forEach((hex) => expect(tw).toContain(hex));
    expect(tw).toContain("'Calibri', 'Carlito'");
    expect(src('index.html')).toContain('family=Carlito');
    const { container } = renderAt('/tableros/matricula');
    expect(container.querySelector('aside > div').className).toContain('bg-slep-navy');
  });
});
