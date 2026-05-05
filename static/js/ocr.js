/* PrecioValida — cámara + OCR con Tesseract.js */

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const placeholder = document.getElementById('camera-placeholder');
const btnCapturar = document.getElementById('btn-capturar');
const btnReintentar = document.getElementById('btn-reintentar');
const btnOk = document.getElementById('btn-confirmar');
const btnBad = document.getElementById('btn-discrepancia');
const ocrPanel = document.getElementById('ocr-panel');
const ocrStatus = document.getElementById('ocr-status');
const valCodigo = document.getElementById('val-codigo');
const valPrecio = document.getElementById('val-precio');
const fieldCodigo = document.getElementById('field-codigo');
const fieldPrecio = document.getElementById('field-precio');
const checkCodigo = document.getElementById('check-codigo');
const checkPrecio = document.getElementById('check-precio');
const veredicto = document.getElementById('veredicto');

const productoId = document.getElementById('producto-id').value;
const codigoEsperado = document.getElementById('codigo-esperado').value.trim();
const precioEsperado = parseFloat(document.getElementById('precio-esperado').value);
const TOLERANCIA = 0.05;

let currentBlob = null;
let ocrCodigo = '';
let ocrPrecio = null;

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 960 } },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    placeholder.style.display = 'none';
    btnCapturar.disabled = false;
  } catch (err) {
    placeholder.textContent = 'No se pudo acceder a la cámara. Permite el acceso en tu navegador.';
  }
}

btnCapturar.addEventListener('click', async () => {
  const vw = video.videoWidth, vh = video.videoHeight;
  canvas.width = vw;
  canvas.height = vh;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, vw, vh);

  // Mostrar foto capturada reemplazando el video
  const dataUrl = canvas.toDataURL('image/jpeg', 0.88);
  currentBlob = await (await fetch(dataUrl)).blob();
  video.style.display = 'none';
  let preview = document.getElementById('preview');
  if (!preview) {
    preview = document.createElement('img');
    preview.id = 'preview';
    document.getElementById('camera-box').appendChild(preview);
  }
  preview.src = dataUrl;

  btnCapturar.style.display = 'none';
  btnReintentar.style.display = 'inline-flex';
  ocrPanel.style.display = 'block';
  ocrStatus.textContent = 'Analizando imagen con OCR…';

  await runOCR(dataUrl);
});

btnReintentar.addEventListener('click', () => {
  const preview = document.getElementById('preview');
  if (preview) preview.remove();
  video.style.display = '';
  btnCapturar.style.display = '';
  btnReintentar.style.display = 'none';
  ocrPanel.style.display = 'none';
  currentBlob = null;
});

async function runOCR(imageData) {
  try {
    const { data } = await Tesseract.recognize(imageData, 'spa+eng', {
      // logger: m => console.log(m)
    });
    const text = data.text || '';
    ocrStatus.textContent = 'Lectura completa.';
    console.log('OCR raw:', text);

    // Extraer código: buscar número de 4-7 dígitos que coincida con el esperado o el más cercano
    ocrCodigo = extractCodigo(text, codigoEsperado);
    ocrPrecio = extractPrecio(text);

    // Mostrar
    valCodigo.textContent = ocrCodigo || '—';
    valPrecio.textContent = ocrPrecio !== null ? `Q ${ocrPrecio.toFixed(2)}` : '—';

    // Validar coincidencias
    const codigoOk = ocrCodigo && ocrCodigo === codigoEsperado;
    const precioOk = ocrPrecio !== null && Math.abs(ocrPrecio - precioEsperado) <= TOLERANCIA;

    fieldCodigo.classList.toggle('match', codigoOk);
    fieldCodigo.classList.toggle('mismatch', !codigoOk);
    checkCodigo.textContent = codigoOk ? '✓ coincide' : (ocrCodigo ? '✕ no coincide' : 'no detectado');

    fieldPrecio.classList.toggle('match', precioOk);
    fieldPrecio.classList.toggle('mismatch', !precioOk);
    checkPrecio.textContent = precioOk ? '✓ coincide' : (ocrPrecio !== null ? '✕ no coincide' : 'no detectado');

    if (codigoOk && precioOk) {
      veredicto.textContent = '✅ Todo coincide — confirma el cambio.';
      veredicto.style.color = 'var(--ok)';
    } else if (codigoOk && !precioOk) {
      veredicto.textContent = '⚠️ Precio en piso no coincide con el esperado.';
      veredicto.style.color = 'var(--bad)';
    } else if (!codigoOk && precioOk) {
      veredicto.textContent = '⚠️ Código no coincide — ¿es la etiqueta correcta?';
      veredicto.style.color = 'var(--bad)';
    } else {
      veredicto.textContent = '❓ No pude leer con certeza. Revisa manualmente o reintenta.';
      veredicto.style.color = 'var(--warn)';
    }
  } catch (err) {
    ocrStatus.textContent = 'Error en OCR: ' + err.message;
    veredicto.textContent = 'No se pudo procesar — puedes confirmar manualmente.';
  }
}

function extractCodigo(text, esperado) {
  const regex = /\b(\d{4,7})\b/g;
  const matches = [...text.matchAll(regex)].map(m => m[1]);
  // Comparar ignorando ceros a la izquierda
  const normalizar = (c) => String(parseInt(c, 10));
  const espNorm = normalizar(esperado);
  const coincide = matches.find(m => normalizar(m) === espNorm);
  if (coincide) return coincide;
  const mismaLong = matches.find(m => m.length === esperado.length);
  if (mismaLong) return mismaLong;
  return matches[0] || '';
}

function extractPrecio(text) {
  // Busca patrones como Q 24.90 / Q24.90 / 24.90 / 1,234.50
  // Prioriza patrones con Q
  const withQ = text.match(/Q\s*\$?\s*([\d,]+\.?\d{0,2})/i);
  if (withQ) return parseFloat(withQ[1].replace(/,/g, ''));
  // Luego cualquier número con decimal
  const decimal = text.match(/\b(\d{1,5}[,.]?\d{0,3}\.\d{2})\b/);
  if (decimal) return parseFloat(decimal[1].replace(/,/g, ''));
  // Último recurso: cualquier número de al menos 2 dígitos
  const any = text.match(/\b(\d{2,6})\b/);
  if (any) return parseFloat(any[1]);
  return null;
}

async function enviarValidacion(resultado) {
  const fd = new FormData();
  fd.append('producto_id', productoId);
  fd.append('codigo_ocr', ocrCodigo || '');
  fd.append('precio_ocr', ocrPrecio !== null ? String(ocrPrecio) : '');
  fd.append('resultado', resultado);
  fd.append('comentario', document.getElementById('comentario').value);
  if (currentBlob) fd.append('foto', currentBlob, 'captura.jpg');

  btnOk.disabled = true; btnBad.disabled = true;
  try {
    const res = await fetch('/api/validar', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      window.location.href = '/gerente';
    } else {
      alert('Error: ' + (data.error || 'desconocido'));
      btnOk.disabled = false; btnBad.disabled = false;
    }
  } catch (err) {
    alert('Error de red: ' + err.message);
    btnOk.disabled = false; btnBad.disabled = false;
  }
}

btnOk.addEventListener('click', () => enviarValidacion('OK'));
btnBad.addEventListener('click', () => {
  if (!confirm('¿Reportar como discrepancia? Esto quedará registrado para revisión.')) return;
  enviarValidacion('DISCREPANCIA');
});

startCamera();
