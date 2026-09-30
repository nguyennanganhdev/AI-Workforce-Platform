import type { Photo } from '../types';
import { MAX_PHOTOS } from './reception-agent';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
/** Small enough that a few photos fit next to the operations store in localStorage. */
const MAX_PHOTO_BYTES = 250 * 1024;
const MAX_EDGE = 1024;

/** Validates, downsizes and re-encodes photos to JPEG data URLs (ported from resident-app). */
export async function readPhotos(files: File[]): Promise<Photo[]> {
  if (files.length > MAX_PHOTOS) throw new Error('Bạn chọn tối đa 3 ảnh mỗi lần nhé.');
  for (const file of files) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Vui lòng dùng ảnh JPG, PNG hoặc WebP.');
    if (file.size > MAX_UPLOAD_BYTES) throw new Error(`Ảnh “${file.name}” vượt 10 MB. Hãy chọn ảnh nhỏ hơn nhé.`);
  }
  const result: Photo[] = [];
  // Sequential so several large phone photos are not decoded at once.
  for (const file of files) {
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error(`Không đọc được ảnh “${file.name}”. Hãy chọn lại ảnh JPG, PNG hoặc WebP hợp lệ.`);
    }
    try {
      const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Trình duyệt chưa hỗ trợ xử lý ảnh.');
      context.fillStyle = '#fff';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      let url = canvas.toDataURL('image/jpeg', 0.72);
      if (url.length > (MAX_PHOTO_BYTES * 4) / 3) url = canvas.toDataURL('image/jpeg', 0.45);
      if (url.length > (MAX_PHOTO_BYTES * 4) / 3) throw new Error('Ảnh vẫn quá lớn sau khi thu nhỏ. Hãy chọn ảnh khác nhé.');
      result.push({ id: crypto.randomUUID(), name: file.name, url });
    } finally {
      bitmap.close();
    }
  }
  return result;
}
