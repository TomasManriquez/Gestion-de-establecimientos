import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

// ADR-016: la sesión es una cookie HttpOnly. Ningún código de la app puede volver a guardar o leer un
// token en el navegador ni armar la cabecera `Authorization`: un XSS no tendría nada que robar.
function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'tests' ? [] : sourceFiles(path);
    return /\.(jsx?|tsx?)$/.test(name) ? [path] : [];
  });
}

const stripComments = (code) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

describe('FE-18: sin token en el navegador (cookie HttpOnly)', () => {
  const files = sourceFiles(join(process.cwd(), 'src'));

  it('FE18-A: ningún archivo de la app guarda un token en localStorage ni sessionStorage', () => {
    const offenders = files.filter((f) => /(localStorage|sessionStorage)\.setItem\(\s*['"`]token['"`]/.test(stripComments(readFileSync(f, 'utf-8'))));
    expect(offenders).toEqual([]);
  });

  it('FE18-B: ningún archivo de la app arma la cabecera Authorization', () => {
    const offenders = files.filter((f) => /headers[^\n]*Authorization|\[\s*['"`]Authorization['"`]\s*\]\s*=/.test(stripComments(readFileSync(f, 'utf-8'))));
    expect(offenders).toEqual([]);
  });

  it('FE18-C: App purga el token que dejaron las versiones anteriores', () => {
    const app = stripComments(readFileSync(join(process.cwd(), 'src/App.jsx'), 'utf-8'));
    expect(app).toMatch(/localStorage\.removeItem\(\s*['"`]token['"`]\s*\)/);
  });
});
