/**
 * test_FE16_shadcn_conformance.test.jsx
 * ─────────────────────────────────────
 * Tarea: US-40 · Conformidad de los componentes nuevos con las reglas de shadcn/ui del proyecto
 *
 * Es un análisis estático (como FE05): los componentes de la vista de usuarios y RequireAccess
 * deben seguir las reglas, para que un cambio posterior no las rompa en silencio.
 *   - sin colores crudos (bg-sky-600, text-red-500…): solo tokens semánticos
 *   - sin space-x-* / space-y-* (se usa flex + gap-*)
 *   - sin z-index manual en overlays
 *   - los diálogos tienen su título (accesibilidad)
 *   - los íconos dentro de componentes no se dimensionan con clases
 *   - solo se importan primitivas desde @/components/ui/* (no de @radix-ui directo)
 *   - formularios con FieldGroup/Field
 * AppLayout (heredado, con paleta slate/sky propia) queda fuera de este escaneo.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';

const ROOT = join(process.cwd(), 'src');
const usersDir = join(ROOT, 'components/users');
const FILES = [
  ...readdirSync(usersDir).filter((f) => f.endsWith('.jsx')).map((f) => join(usersDir, f)),
  join(ROOT, 'components/RequireAccess.jsx'),
];
const read = (f) => readFileSync(f, 'utf-8');
const rel = (f) => f.slice(ROOT.length + 1);

const RAW_COLOR = /\b(?:bg|text|border|ring|fill|stroke|from|to|via|outline|divide|decoration|shadow)-(?:red|green|blue|sky|slate|gray|grey|zinc|emerald|amber|yellow|orange|rose|indigo|violet|purple|pink|teal|cyan|lime|stone|neutral|fuchsia)-\d{2,3}\b|\b(?:bg|text|border)-(?:white|black)\b/;

describe('FE16: reglas shadcn en la vista de usuarios', () => {
  it('FE16-A: el escaneo encuentra los archivos esperados', () => {
    const names = FILES.map(rel);
    for (const n of ['UsersPage', 'UsersTable', 'UserForm', 'BulkBar', 'AccessDialog', 'PermissionsCell', 'UsersFilters', 'UserRowActions']) {
      expect(names).toContain(`components/users/${n}.jsx`);
    }
    expect(names).toContain('components/RequireAccess.jsx');
  });

  it.each(FILES)('FE16-B: sin colores crudos — %s', (file) => {
    expect(read(file).match(RAW_COLOR)?.[0]).toBeUndefined();
  });

  it.each(FILES)('FE16-C: sin space-x/space-y — %s', (file) => {
    expect(read(file)).not.toMatch(/\bspace-[xy]-/);
  });

  it.each(FILES)('FE16-D: sin z-index manual — %s', (file) => {
    expect(read(file)).not.toMatch(/(?:^|[\s"'`])-?z-(?:\d|\[)/);
  });

  it.each(FILES)('FE16-E: sin imports directos de @radix-ui ni de axios — %s', (file) => {
    const src = read(file);
    expect(src).not.toMatch(/from ['"]@radix-ui\//);
    expect(src).not.toMatch(/from ['"]axios['"]/);
  });

  it.each(FILES)('FE16-F: los componentes de UI vienen de @/components/ui/* — %s', (file) => {
    const imports = [...read(file).matchAll(/from ['"]([^'"]+)['"]/g)].map((m) => m[1]);
    for (const i of imports) {
      expect(
        /^(react|react-router-dom|lucide-react|sonner)$/.test(i) || i.startsWith('@/components/ui/') || i.startsWith('@/lib/') || i.startsWith('./'),
        `import inesperado: ${i}`,
      ).toBe(true);
    }
  });

  it.each(FILES)('FE16-G: cada Dialog/AlertDialog tiene título — %s', (file) => {
    const src = read(file);
    const dialogs = (src.match(/<DialogContent\b/g) ?? []).length;
    const titles = (src.match(/<DialogTitle\b/g) ?? []).length;
    expect(titles).toBeGreaterThanOrEqual(dialogs);
    const alerts = (src.match(/<AlertDialogContent\b/g) ?? []).length;
    expect((src.match(/<AlertDialogTitle\b/g) ?? []).length).toBeGreaterThanOrEqual(alerts);
  });

  it.each(FILES)('FE16-H: los íconos de lucide no llevan clases de tamaño — %s', (file) => {
    const src = read(file);
    const lucide = src.match(/import \{([^}]+)\} from 'lucide-react'/)?.[1];
    if (!lucide) return;
    for (const name of lucide.split(',').map((s) => s.trim()).filter(Boolean)) {
      const tags = [...src.matchAll(new RegExp(`<${name}\\b[^>]*>`, 'g'))].map((m) => m[0]);
      for (const tag of tags) expect(tag, `${name} con clase de tamaño`).not.toMatch(/className="[^"]*\b(?:size|w|h)-\d/);
    }
  });

  it.each(FILES)('FE16-I: los íconos dentro de botones usan data-icon, no márgenes — %s', (file) => {
    expect(read(file)).not.toMatch(/<(?:Spinner|Loader2)\b[^>]*className="[^"]*\bm[rl]-\d/);
  });

  it('FE16-J: los formularios usan FieldGroup y Field', () => {
    for (const name of ['UserForm', 'AccessDialog', 'UsersFilters']) {
      const src = read(join(usersDir, `${name}.jsx`));
      expect(src).toContain('<FieldGroup');
      expect(src).toContain('<Field');
    }
    // Nada de <label> o <input> sueltos: se usan FieldLabel e Input de shadcn
    for (const file of FILES) {
      expect(read(file)).not.toMatch(/<label\b/);
      expect(read(file)).not.toMatch(/<input\b/);
    }
  });

  it('FE16-K: los tokens success/warning usados existen en CSS y Tailwind', () => {
    const css = read(join(ROOT, 'index.css'));
    const tw = readFileSync(join(process.cwd(), 'tailwind.config.js'), 'utf-8');
    for (const t of ['--success:', '--success-foreground:', '--warning:', '--warning-foreground:']) expect(css).toContain(t);
    expect(tw).toMatch(/success:/);
    expect(tw).toMatch(/warning:/);
    expect(read(join(usersDir, 'UsersTable.jsx'))).toMatch(/bg-success/);
  });

  it('FE16-L: components.json es JSON válido sin BOM y con JSX', () => {
    const raw = readFileSync(join(process.cwd(), 'components.json'), 'utf-8');
    expect(raw.charCodeAt(0)).not.toBe(0xfeff);
    const cfg = JSON.parse(raw);
    expect(cfg.tsx).toBe(false);
    expect(cfg.tailwind.baseColor).toBe('slate');
  });
});
