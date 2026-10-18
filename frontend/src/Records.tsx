import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { Download, KeyRound, LockKeyhole, Share2, ShieldCheck, Upload } from 'lucide-react'
import {
  decryptRecord, encryptedPrivateKeyExport, encryptRecord, generateRecipientKeyPair,
  importPublicKey, loadPrivateKey, recoverPrivateKey, rewrapRecordKey, storePrivateKey,
  type KeyEnvelope, type RecordEnvelope,
} from './crypto'
import { connectAndSign, openEmergency, registerPatientWallet, requestWalletAddress, writeConsent } from './wallet'

type Props = { token: string; email: string; role: string }
type KeyInfo = { version: number; public_key_spki_b64: string; fingerprint_sha256: string }
type RecordMeta = { record_id: string; title: string; category: string; envelope_digest: string; storage_status: string; cid?: string | null }
type Recipient = { email: string; name: string; key: KeyInfo }
type Consent = { id:string; practitioner_email:string; category:string; access_level:string; valid_until:string; status:string }

export default function Records({ token, email, role }: Props) {
  const [records, setRecords] = useState<RecordMeta[]>([]); const [key, setKey] = useState<KeyInfo | null>(null)
  const [recipients, setRecipients] = useState<Recipient[]>([]); const [message, setMessage] = useState(''); const [error, setError] = useState('')
  const [consents, setConsents] = useState<Consent[]>([])
  const [escrow, setEscrow] = useState<{email:string;key:KeyInfo}|null>(null)
  const [plaintext, setPlaintext] = useState(''); const [form, setForm] = useState({ title: '', category: '', clinicalText: '' }); const [passphrase, setPassphrase] = useState('')
  const [share, setShare] = useState({ recordId: '', doctorEmail: '', access: 'ReadOnly', hours: 24 })
  const [wallet, setWallet] = useState(''); const [txState, setTxState] = useState('')
  const [emergency,setEmergency]=useState({recordId:'',justification:'',type:1})
  const headers = { Authorization: `Bearer ${token}` }
  const api = async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const response = await fetch(`/api/v1${path}`, { ...init, headers: { ...headers, ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(init.headers || {}) } })
    const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Secure record request failed.'); return body as T
  }
  const confirmIntent=async(intentId:string,hash:string)=>{let state=await api<{status:string}>('/blockchain/transactions/submit',{method:'POST',body:JSON.stringify({intent_id:intentId,tx_hash:hash})});setTxState(state.status);for(let i=0;i<30&&state.status==='SUBMITTED';i++){await new Promise(resolve=>setTimeout(resolve,2000));state=await api<{status:string}>(`/blockchain/transactions/${intentId}`);setTxState(state.status)}return state}
  const refresh = async () => {
    const path = role === 'Patient' ? '/records/mine' : '/records/accessible'
    const list = await api<{ items: RecordMeta[] }>(path); setRecords(list.items)
    try { setKey(await api<KeyInfo>('/auth/keys/me')) } catch { setKey(null) }
    if (role === 'Patient') { setRecipients((await api<{ items: Recipient[] }>('/auth/recipients')).items); setConsents((await api<{items:Consent[]}>('/blockchain/consents/mine')).items); try{setEscrow(await api<{email:string;key:KeyInfo}>('/auth/emergency-escrow-key'))}catch{setEscrow(null)} }
  }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [token, role])

  const createKey = async () => {
    setError(''); setMessage('')
    try {
      const generated = await generateRecipientKeyPair(); const registered = await api<KeyInfo>('/auth/keys', { method: 'POST', body: JSON.stringify(generated.publicRegistration) })
      await storePrivateKey(email, registered.version, generated.privateKey)
      const backup = await encryptedPrivateKeyExport(generated.privatePkcs8, passphrase)
      const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([backup], { type: 'application/json' })); link.download = `healerplus-key-v${registered.version}.json`; link.click(); URL.revokeObjectURL(link.href)
      setKey(registered); setPassphrase(''); setMessage('RSA key created. Keep the encrypted backup and passphrase separately; the server cannot recover either one.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Key creation failed.') }
  }
  const recover = async (event: ChangeEvent<HTMLInputElement>) => {
    setError(''); const file = event.target.files?.[0]; if (!file || !key) return
    try { const privateKey = await recoverPrivateKey(await file.text(), passphrase); await storePrivateKey(email, key.version, privateKey); setMessage(`Private key version ${key.version} restored on this browser.`) } catch (e) { setError(e instanceof Error ? e.message : 'Recovery failed.') }
  }
  const upload = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setMessage('')
    try {
      if (!key) throw new Error('Create or register a recipient key first.'); const publicKey = await importPublicKey(key.public_key_spki_b64)
      const recordId = `REC-${Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('').toUpperCase()}`
      const encryptionRecipients = [{ email, keyVersion: key.version, publicKey }]
      if(escrow) encryptionRecipients.push({email:escrow.email,keyVersion:escrow.key.version,publicKey:await importPublicKey(escrow.key.public_key_spki_b64)})
      const encrypted = await encryptRecord(form.clinicalText, recordId, 1, encryptionRecipients)
      await api('/records/upload', { method: 'POST', body: JSON.stringify({ record_id: recordId, title: form.title, category: form.category, ...encrypted }) })
      setForm({ title: '', category: '', clinicalText: '' }); setMessage(`Encrypted record stored. Clinical plaintext remained in this browser. Emergency escrow: ${escrow?'included':'not configured'}.`); await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Encryption failed.') }
  }
  const decrypt = async (recordId: string) => {
    setError(''); setPlaintext('')
    try {
      const result = await api<{ envelope: RecordEnvelope; key_envelope: KeyEnvelope }>(`/records/${recordId}/envelope`)
      const privateKey = await loadPrivateKey(email, result.key_envelope.recipient_key_version)
      if (!privateKey) throw new Error(`Private key version ${result.key_envelope.recipient_key_version} is missing on this browser. Import its encrypted backup.`)
      setPlaintext(await decryptRecord(result.envelope, result.key_envelope, privateKey))
    } catch (e) { setError(e instanceof Error ? e.message : 'Authenticated decryption failed.') }
  }
  const grant = async () => {
    setError(''); setMessage('')
    try {
      const doctor = recipients.find(value => value.email === share.doctorEmail); if (!doctor || !share.recordId) throw new Error('Choose a record and verified recipient.')
      const result = await api<{ envelope: RecordEnvelope; key_envelope: KeyEnvelope; record_version: number }>(`/records/${share.recordId}/envelope`)
      const privateKey = await loadPrivateKey(email, result.key_envelope.recipient_key_version); if (!privateKey) throw new Error('The patient private key needed to create this recipient envelope is missing.')
      const doctorPublicKey = await importPublicKey(doctor.key.public_key_spki_b64)
      const envelope = await rewrapRecordKey(result.envelope, result.key_envelope, privateKey, doctor.key.version, doctorPublicKey)
      await api(`/records/${share.recordId}/versions/${result.record_version}/key-envelopes`, { method: 'POST', body: JSON.stringify({ recipient_email: doctor.email, envelope }) })
      const record = records.find(value => value.record_id === share.recordId)!
      const intent = await api<{intent_id:string;contract:`0x${string}`;function:'grantConsent';args:readonly unknown[]} >('/blockchain/consent/prepare', { method: 'POST', body: JSON.stringify({ practitioner_email: doctor.email, category: record.category, access_level: share.access, duration_hours: Number(share.hours) }) })
      setTxState('AWAITING_SIGNATURE'); const hash = await writeConsent(intent.contract, intent.function, intent.args); setTxState('SUBMITTED')
      const verified = await confirmIntent(intent.intent_id,hash)
      setMessage(`Recipient key stored and patient-wallet consent is ${verified.status.toLowerCase()}. Revocation blocks future delivery but cannot erase downloaded material.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Consent grant failed.') }
  }
  const linkWallet = async () => {
    setError(''); setTxState('AWAITING_SIGNATURE')
    try { const address = await requestWalletAddress(); const challenge = await api<{challenge_id:string;message:string;chain_id:number}>('/blockchain/wallet/challenge',{method:'POST',body:JSON.stringify({wallet_address:address})}); const signed = await connectAndSign(challenge.message, challenge.chain_id); const linked = await api<{wallet_address:string}>('/blockchain/wallet/verify',{method:'POST',body:JSON.stringify({challenge_id:challenge.challenge_id,signature:signed.signature})}); setWallet(linked.wallet_address); if(role==='Patient'){const intent=await api<{intent_id?:string;contract?:`0x${string}`;already_registered?:boolean}>('/blockchain/identity/patient/prepare',{method:'POST',body:'{}'}); if(!intent.already_registered&&intent.intent_id&&intent.contract){setTxState('AWAITING_SIGNATURE');const hash=await registerPatientWallet(intent.contract);setTxState('SUBMITTED');await confirmIntent(intent.intent_id,hash)}else setTxState('CONFIRMED');setMessage('Wallet linked and patient contract identity confirmed.')}else{setTxState('SUBMITTED');setMessage('Wallet linked. Verified staff registration is queued for the separately scoped backend worker.')} } catch(e){setTxState('FAILED');setError(e instanceof Error?e.message:'Wallet linking failed.')}
  }
  const revoke = async (consent: Consent) => {
    setError(''); setTxState('AWAITING_SIGNATURE')
    try { const intent = await api<{intent_id:string;contract:`0x${string}`;function:'revokeConsent';args:readonly unknown[]}>('/blockchain/consent/revoke/prepare',{method:'POST',body:JSON.stringify({practitioner_email:consent.practitioner_email,category:consent.category})}); const hash=await writeConsent(intent.contract,intent.function,intent.args); setTxState('SUBMITTED'); const verified=await confirmIntent(intent.intent_id,hash);await refresh();setMessage(`Revocation transaction is ${verified.status.toLowerCase()}. Previously downloaded keys or plaintext cannot be erased.`) } catch(e){setTxState('FAILED');setError(e instanceof Error?e.message:'Revocation failed.')}
  }
  const requestEmergency=async()=>{setError('');setPlaintext('');try{const prepared=await api<{emergency_id:string;intent_id:string;contract:`0x${string}`;args:readonly unknown[];key_delivery_state:string}>('/blockchain/emergency/prepare',{method:'POST',body:JSON.stringify({record_id:emergency.recordId,justification:emergency.justification,emergency_type:emergency.type})});setTxState('AWAITING_SIGNATURE');const hash=await openEmergency(prepared.contract,prepared.args);setTxState('SUBMITTED');const verified=await confirmIntent(prepared.intent_id,hash);if(verified.status!=='CONFIRMED')throw new Error(`Emergency transaction is ${verified.status}.`);const delivered=await api<{envelope:RecordEnvelope;key_envelope:KeyEnvelope;key_delivery_state:string}>(`/blockchain/emergency/${prepared.emergency_id}/envelope`);const privateKey=await loadPrivateKey(email,delivered.key_envelope.recipient_key_version);if(!privateKey)throw new Error('Doctor RSA private key is missing on this browser.');setPlaintext(await decryptRecord(delivered.envelope,delivered.key_envelope,privateKey));setMessage(`Emergency key delivery: ${delivered.key_delivery_state}. Review notifications are queued for the deterministic local sink.`)}catch(e){setTxState('FAILED');setError(e instanceof Error?e.message:'Emergency access failed.')}}

  return <div className="records-workspace">
    <div className="dash-title"><div><span className="eyebrow">Encrypted records</span><h1>Authenticated record vault</h1></div><span className="dash-live"><i/> {txState || (key ? `RSA key v${key.version}` : 'Key setup required')}</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}{message && <div className="notice"><ShieldCheck/><span>{message}</span></div>}
    <section className="dash-panel record-key-panel"><KeyRound/><div><h2>Private decryption key</h2><p>The non-extractable working key stays in this browser's IndexedDB. Create an encrypted backup for recovery; an Ethereum wallet is not a decryption key.</p></div><label>Backup passphrase<input type="password" minLength={12} value={passphrase} onChange={e => setPassphrase(e.target.value)} placeholder="12+ characters"/></label>{!key ? <button className="button" onClick={createKey} disabled={passphrase.length < 12}><Download/> Create key + backup</button> : <label className="button ghost"><Upload/> Recover backup<input hidden type="file" accept="application/json" onChange={recover}/></label>}</section>
    <section className="dash-panel record-key-panel"><ShieldCheck/><div><h2>{role==='Patient'?'Patient transaction wallet':'Practitioner transaction wallet'}</h2><p>MetaMask signs wallet linkage and user-authorized transactions. Wallet secrets are never requested or sent to this application.</p></div><code>{wallet || 'Not linked in this browser session'}</code><button className="button" onClick={linkWallet}>Link MetaMask</button></section>
    {role === 'Patient' && <form className="dash-panel record-form" onSubmit={upload}><h2>Encrypt a new record</h2><div className="form-grid"><label>Title<input required value={form.title} onChange={e => setForm({...form,title:e.target.value})}/></label><label>Category<input required pattern="[A-Za-z0-9 _-]+" value={form.category} onChange={e => setForm({...form,category:e.target.value})}/></label><label className="wide">Clinical plaintext<textarea required rows={6} value={form.clinicalText} onChange={e => setForm({...form,clinicalText:e.target.value})}/></label></div><button className="button"><LockKeyhole/> Encrypt and upload</button></form>}
    <section className="dash-panel"><h2>{role === 'Patient' ? 'My encrypted records' : 'Consent-authorized records'}</h2>{records.length ? records.map(record => <div className="appointment-row" key={record.record_id}><LockKeyhole/><span><b>{record.title}</b><small>{record.category} · {record.storage_status} · {record.envelope_digest.slice(0, 22)}…</small></span><button className="button ghost" onClick={() => decrypt(record.record_id)}>Verify + decrypt</button></div>) : <p>No encrypted records are available.</p>}</section>
    {plaintext && <section className="dash-panel decrypted-output"><ShieldCheck/><div><h2>Authenticated plaintext</h2><pre>{plaintext}</pre></div></section>}
    {role === 'Patient' && <section className="dash-panel record-share"><Share2/><div><h2>Share with a verified doctor</h2><p>This unwraps your record key locally and creates a doctor-specific RSA-OAEP envelope. No private key is sent to the backend.</p></div><select value={share.recordId} onChange={e=>setShare({...share,recordId:e.target.value})}><option value="">Choose record</option>{records.map(r=><option key={r.record_id} value={r.record_id}>{r.title}</option>)}</select><select value={share.doctorEmail} onChange={e=>setShare({...share,doctorEmail:e.target.value})}><option value="">Choose doctor</option>{recipients.map(r=><option key={r.email} value={r.email}>{r.name}</option>)}</select><select value={share.access} onChange={e=>setShare({...share,access:e.target.value})}><option>ReadOnly</option><option>ReadAndWrite</option></select><input type="number" min={1} max={8760} value={share.hours} onChange={e=>setShare({...share,hours:Number(e.target.value)})}/><button className="button" onClick={grant}>Create envelope + grant</button></section>}
    {role === 'Patient' && <section className="dash-panel"><h2>On-chain consent transactions</h2>{consents.length?consents.map(c=><div className="appointment-row" key={c.id}><ShieldCheck/><span><b>{c.practitioner_email}</b><small>{c.category} · {c.access_level} · {c.status}</small></span>{c.status==='CONFIRMED'&&<button className="button ghost" onClick={()=>revoke(c)}>Revoke with MetaMask</button>}</div>):<p>No patient-wallet consent transactions yet.</p>}</section>}
    {role === 'Doctor' && <section className="dash-panel record-form"><h2>Emergency break-glass</h2><p>Requires a linked, on-chain verified doctor wallet and configured institutional key escrow. Detailed justification stays off chain; only its commitment is emitted.</p><div className="form-grid"><label>Opaque record ID<input value={emergency.recordId} placeholder="REC-…" onChange={e=>setEmergency({...emergency,recordId:e.target.value})}/></label><label>Emergency type<select value={emergency.type} onChange={e=>setEmergency({...emergency,type:Number(e.target.value)})}><option value={1}>Cardiac arrest</option><option value={2}>Trauma</option><option value={3}>Critical care</option><option value={4}>Stroke</option></select></label><label className="wide">Detailed justification<textarea minLength={20} value={emergency.justification} onChange={e=>setEmergency({...emergency,justification:e.target.value})}/></label></div><button className="button" disabled={!emergency.recordId||emergency.justification.length<20} onClick={requestEmergency}>Sign emergency request</button></section>}
  </div>
}
