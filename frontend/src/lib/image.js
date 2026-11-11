const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
export const COVER_MAX_BYTES = 512 * 1024;      // el backend lo exige igual (portal_entity.COVER_MAX_BYTES)

/** Reduce la imagen elegida a un WebP liviano: sube rápido y no pesa en cada tarjeta del portal. */
export async function shrinkImage(file) {
  if (!TYPES.includes(file.type)) throw new Error('Elige una imagen PNG, JPEG o WebP.');
  const bitmap = await createImageBitmap(file);
  try {
    for (const [width, quality] of [[960, 0.85], [720, 0.7], [480, 0.6]]) {
      const scale = Math.min(1, width / bitmap.width);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', quality));
      if (blob && blob.size <= COVER_MAX_BYTES) return blob;
    }
  } finally {
    bitmap.close?.();
  }
  throw new Error('No se pudo reducir la imagen a menos de 512 KB.');
}
