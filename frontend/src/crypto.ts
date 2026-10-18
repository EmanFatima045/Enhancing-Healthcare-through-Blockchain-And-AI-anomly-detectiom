/* Browser-only record cryptography. Private keys and plaintext never cross the API boundary. */

const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', { fatal: true })

export type RecordEnvelope = {
  format: 'healerplus.record-envelope'
  version: 1
  cipher: 'AES-256-GCM'
  key_version: number
  nonce_b64: string
  ciphertext_b64: string
  aad: { format: 'healerplus.record-aad'; record_id: string; record_version: number }
  digest: string
}

export type KeyEnvelope = {
  format: 'healerplus.key-envelope'
  version: 1
  wrapping: 'RSA-OAEP-SHA-256'
  record_id: string
  record_version: number
  recipient_key_version: number
  wrapped_key_b64: string
  digest: string
}

export type PublicKeyRegistration = {
  algorithm: 'RSA-OAEP-SHA-256'
  public_key_spki_b64: string
}

function requireWebCrypto() {
  if (!window.isSecureContext || !globalThis.crypto?.subtle) {
    throw new Error('WebCrypto requires a secure context (HTTPS or localhost).')
  }
}

function b64(bytes: ArrayBuffer | Uint8Array): string {
  const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  let binary = ''
  for (let i = 0; i < data.length; i += 0x8000) binary += String.fromCharCode(...data.subarray(i, i + 0x8000))
  return btoa(binary)
}

function fromB64(value: string): Uint8Array<ArrayBuffer> {
  let raw: string
  try { raw = atob(value) } catch { throw new Error('Invalid base64 in encrypted envelope.') }
  const bytes = Uint8Array.from(raw, c => c.charCodeAt(0))
  if (b64(bytes) !== value) throw new Error('Non-canonical base64 in encrypted envelope.')
  return bytes
}

export function canonicalJson(value: unknown): string {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value)
  if (typeof value === 'number' && Number.isFinite(value)) return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (typeof value === 'object') {
    const object = value as Record<string, unknown>
    return `{${Object.keys(object).sort().map(k => `${JSON.stringify(k)}:${canonicalJson(object[k])}`).join(',')}}`
  }
  throw new Error('Envelope contains a value that cannot be canonicalized.')
}

async function digest(value: unknown): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', encoder.encode(canonicalJson(value)))
  return `sha256:${Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('')}`
}

export async function generateRecipientKeyPair(): Promise<{ publicRegistration: PublicKeyRegistration; privateKey: CryptoKey; privatePkcs8: ArrayBuffer }> {
  requireWebCrypto()
  const pair = await crypto.subtle.generateKey(
    { name: 'RSA-OAEP', modulusLength: 3072, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
    true,
    ['wrapKey', 'unwrapKey'],
  )
  const spki = await crypto.subtle.exportKey('spki', pair.publicKey)
  const pkcs8 = await crypto.subtle.exportKey('pkcs8', pair.privateKey)
  const privateKey = await crypto.subtle.importKey('pkcs8', pkcs8, { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['unwrapKey'])
  return { publicRegistration: { algorithm: 'RSA-OAEP-SHA-256', public_key_spki_b64: b64(spki) }, privateKey, privatePkcs8: pkcs8 }
}

export async function importPublicKey(spkiB64: string): Promise<CryptoKey> {
  requireWebCrypto()
  return crypto.subtle.importKey('spki', fromB64(spkiB64), { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['wrapKey'])
}

export async function encryptRecord(plaintext: string, recordId: string, recordVersion: number, recipients: Array<{ email: string; keyVersion: number; publicKey: CryptoKey }>) {
  requireWebCrypto()
  if (!recipients.length) throw new Error('At least one recipient key is required.')
  const dataKey = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt'])
  const nonce = crypto.getRandomValues(new Uint8Array(12))
  const aad = { format: 'healerplus.record-aad' as const, record_id: recordId, record_version: recordVersion }
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce, additionalData: encoder.encode(canonicalJson(aad)), tagLength: 128 }, dataKey, encoder.encode(plaintext))
  const unsigned = { format: 'healerplus.record-envelope' as const, version: 1 as const, cipher: 'AES-256-GCM' as const, key_version: recordVersion, nonce_b64: b64(nonce), ciphertext_b64: b64(ciphertext), aad }
  const envelope: RecordEnvelope = { ...unsigned, digest: await digest(unsigned) }
  const key_envelopes = await Promise.all(recipients.map(async recipient => {
    const wrapped = await crypto.subtle.wrapKey('raw', dataKey, recipient.publicKey, { name: 'RSA-OAEP' })
    const keyUnsigned = { format: 'healerplus.key-envelope' as const, version: 1 as const, wrapping: 'RSA-OAEP-SHA-256' as const, record_id: recordId, record_version: recordVersion, recipient_key_version: recipient.keyVersion, wrapped_key_b64: b64(wrapped) }
    return { recipient_email: recipient.email, envelope: { ...keyUnsigned, digest: await digest(keyUnsigned) } as KeyEnvelope }
  }))
  return { envelope, key_envelopes }
}

export async function decryptRecord(envelope: RecordEnvelope, keyEnvelope: KeyEnvelope, privateKey: CryptoKey): Promise<string> {
  requireWebCrypto()
  const { digest: claimedDigest, ...unsigned } = envelope
  if (await digest(unsigned) !== claimedDigest) throw new Error('Ciphertext envelope digest verification failed.')
  if (envelope.format !== 'healerplus.record-envelope' || envelope.version !== 1 || envelope.cipher !== 'AES-256-GCM') throw new Error('Unsupported encrypted envelope.')
  if (envelope.aad.record_id !== keyEnvelope.record_id || envelope.aad.record_version !== keyEnvelope.record_version || envelope.key_version !== envelope.aad.record_version) throw new Error('Record and key envelopes do not match.')
  const { digest: keyClaim, ...keyUnsigned } = keyEnvelope
  if (await digest(keyUnsigned) !== keyClaim) throw new Error('Wrapped-key envelope digest verification failed.')
  const nonce = fromB64(envelope.nonce_b64)
  if (nonce.byteLength !== 12) throw new Error('AES-GCM nonce must be 12 bytes.')
  const dataKey = await crypto.subtle.unwrapKey('raw', fromB64(keyEnvelope.wrapped_key_b64), privateKey, { name: 'RSA-OAEP' }, { name: 'AES-GCM', length: 256 }, false, ['decrypt'])
  try {
    const plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce, additionalData: encoder.encode(canonicalJson(envelope.aad)), tagLength: 128 }, dataKey, fromB64(envelope.ciphertext_b64))
    return decoder.decode(plaintext)
  } catch {
    throw new Error('Authentication failed. The ciphertext, tag, AAD, or private key is invalid.')
  }
}

export async function rewrapRecordKey(envelope: RecordEnvelope, current: KeyEnvelope, privateKey: CryptoKey, recipientKeyVersion: number, recipientPublicKey: CryptoKey): Promise<KeyEnvelope> {
  const { digest: envelopeClaim, ...envelopeUnsigned } = envelope
  const { digest: keyClaim, ...keyUnsigned } = current
  if (await digest(envelopeUnsigned) !== envelopeClaim || await digest(keyUnsigned) !== keyClaim) throw new Error('Envelope digest verification failed.')
  if (current.record_id !== envelope.aad.record_id || current.record_version !== envelope.aad.record_version) throw new Error('Record and key envelopes do not match.')
  const dataKey = await crypto.subtle.unwrapKey('raw', fromB64(current.wrapped_key_b64), privateKey, { name: 'RSA-OAEP' }, { name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt'])
  const wrapped = await crypto.subtle.wrapKey('raw', dataKey, recipientPublicKey, { name: 'RSA-OAEP' })
  const unsigned = { format: 'healerplus.key-envelope' as const, version: 1 as const, wrapping: 'RSA-OAEP-SHA-256' as const, record_id: current.record_id, record_version: current.record_version, recipient_key_version: recipientKeyVersion, wrapped_key_b64: b64(wrapped) }
  return { ...unsigned, digest: await digest(unsigned) }
}

const DB_NAME = 'healerplus-private-keys'
function keyDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore('keys')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new Error('Private-key storage is unavailable.'))
  })
}

export async function storePrivateKey(email: string, version: number, key: CryptoKey) {
  const db = await keyDb()
  await new Promise<void>((resolve, reject) => { const tx = db.transaction('keys', 'readwrite'); tx.objectStore('keys').put(key, `${email}:${version}`); tx.oncomplete = () => resolve(); tx.onerror = () => reject(new Error('Could not store the private key.')) })
  db.close()
}

export async function loadPrivateKey(email: string, version: number): Promise<CryptoKey | null> {
  const db = await keyDb()
  const value = await new Promise<CryptoKey | undefined>((resolve, reject) => { const req = db.transaction('keys').objectStore('keys').get(`${email}:${version}`); req.onsuccess = () => resolve(req.result); req.onerror = () => reject(new Error('Could not read the private key.')) })
  db.close(); return value || null
}

export async function encryptedPrivateKeyExport(pkcs8: ArrayBuffer, passphrase: string): Promise<string> {
  if (passphrase.length < 12) throw new Error('Use an export passphrase of at least 12 characters.')
  const salt = crypto.getRandomValues(new Uint8Array(16)); const nonce = crypto.getRandomValues(new Uint8Array(12))
  const material = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey'])
  const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 310000 }, material, { name: 'AES-GCM', length: 256 }, false, ['encrypt'])
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, pkcs8)
  return canonicalJson({ format: 'healerplus.private-key-backup', version: 1, kdf: 'PBKDF2-SHA-256', iterations: 310000, salt_b64: b64(salt), cipher: 'AES-256-GCM', nonce_b64: b64(nonce), ciphertext_b64: b64(ciphertext) })
}

export async function recoverPrivateKey(backupJson: string, passphrase: string): Promise<CryptoKey> {
  const backup = JSON.parse(backupJson)
  if (backup.format !== 'healerplus.private-key-backup' || backup.version !== 1 || backup.iterations !== 310000) throw new Error('Unsupported private-key backup.')
  const material = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey'])
  const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt: fromB64(backup.salt_b64), iterations: backup.iterations }, material, { name: 'AES-GCM', length: 256 }, false, ['decrypt'])
  let pkcs8: ArrayBuffer
  try { pkcs8 = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromB64(backup.nonce_b64) }, key, fromB64(backup.ciphertext_b64)) } catch { throw new Error('Private-key recovery failed: wrong passphrase or damaged backup.') }
  return crypto.subtle.importKey('pkcs8', pkcs8, { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['unwrapKey'])
}
