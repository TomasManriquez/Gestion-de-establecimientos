/**
 * connectivity.js — conectividad en tres bloques: programa 2030, BAM y otro tipo de conexión.
 * Un establecimiento puede tener los tres. «Sin internet» no se guarda: se calcula igual que en el
 * backend (`app/database/connectivity_migration.without_internet`).
 */
export const STATUS_2030 = [
  { value: 'fibra_optica', label: 'Fibra óptica' },
  { value: 'microondas', label: 'Red de microondas' },
  { value: 'starlink', label: 'Starlink (2030)' },
  { value: 'satelital', label: 'Satelital' },
  { value: 'pendiente_instalacion', label: 'Pendiente de instalar' },
  { value: 'sin_internet', label: 'Sin internet' },
];

export const OTHER_TYPES = [
  { value: 'fibra_optica', label: 'Fibra óptica' },
  { value: 'starlink', label: 'Starlink' },
  { value: 'microondas', label: 'Microondas' },
  { value: 'satelital', label: 'Satelital' },
  { value: 'movil', label: 'Red móvil' },
  { value: 'otro', label: 'Otro' },
];

export const labelOf = (list, value) => list.find((o) => o.value === value)?.label ?? '';

export const EMPTY_BAM = { number: '', oc: '', imei: '', device: '', holder: '', carrier: '', qty: null, start: '', term: '', end: '' };
const EMPTY_OTHER = { provider: '', type: null, download_speed: '', oc: '', expiry_date: '', support_whatsapp: '' };
const EMPTY_2030 = { enabled: false, status: null, download_speed: '', test_date: '' };

/** Completa los bloques que falten para que el editor siempre tenga todos los campos. */
export function withDefaults(conn) {
  const c = conn ?? {};
  return {
    ...c,
    program_2030: { ...EMPTY_2030, ...(c.program_2030 ?? {}) },
    ssid: c.ssid ?? '',
    ssid_password: c.ssid_password ?? '',
    bam: (c.bam ?? []).map((b) => ({ ...EMPTY_BAM, ...b })),
    other: { ...EMPTY_OTHER, ...(c.other ?? {}) },
    internal_network: c.internal_network ?? { installed_year: '', points_count: '', status: '', obs: '' },
    phone_extensions: c.phone_extensions ?? [],
  };
}

export const hasOther = (other) =>
  Boolean(other) && ['provider', 'type', 'download_speed', 'oc', 'expiry_date', 'support_whatsapp'].some((k) => other[k]);

/** null si tiene internet; si no, el motivo. */
export function withoutInternet(conn) {
  const p = conn?.program_2030 ?? {};
  if (p.enabled && p.status === 'sin_internet') return 'En el programa 2030, con estado «sin internet».';
  if (!p.enabled && !(conn?.bam?.length) && !hasOther(conn?.other)) return 'Sin 2030, BAM ni otro tipo de conexión registrados.';
  return null;
}

/** ¿La fecha AAAA-MM-DD ya pasó? */
export const isExpired = (isoDate, today = new Date()) =>
  Boolean(isoDate) && /^\d{4}-\d{2}-\d{2}/.test(isoDate) && new Date(`${isoDate.slice(0, 10)}T23:59:59`) < today;

/** Enlace de WhatsApp a partir de un número escrito a mano. */
export const whatsappLink = (raw) => {
  const digits = String(raw ?? '').replace(/\D/g, '');
  return digits ? `https://wa.me/${digits}` : null;
};

/** Solo la fecha de un texto como '2026-02-23 00:00:00'. */
export const shortDate = (raw) => (raw ? String(raw).slice(0, 10) : '');
