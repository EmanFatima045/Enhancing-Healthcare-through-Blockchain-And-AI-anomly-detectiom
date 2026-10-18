import { expect } from 'chai'
import { ethers } from 'hardhat'

describe('HealerPlus local contracts', () => {
  async function fixture() {
    const [owner, patient, doctor, outsider, auditor, otherPatient] = await ethers.getSigners()
    const auth = await (await ethers.getContractFactory('HealerAuth')).deploy()
    const consent = await (await ethers.getContractFactory('ConsentManager')).deploy(await auth.getAddress())
    const audit = await (await ethers.getContractFactory('MedicalAuditRegistry')).deploy(await auth.getAddress(), await consent.getAddress())
    const emergency = await (await ethers.getContractFactory('BreakGlassEmergency')).deploy(await auth.getAddress(), await audit.getAddress())
    await audit.setEmergencyLogger(await emergency.getAddress(), true)
    await auth.connect(patient).registerPatient(); await auth.connect(otherPatient).registerPatient()
    await auth.registerStaff(doctor.address, 2); await auth.setVerified(doctor.address, true)
    await auth.registerStaff(auditor.address, 5); await auth.setVerified(auditor.address, true)
    return { owner, patient, doctor, outsider, auditor, otherPatient, auth, consent, audit, emergency }
  }
  const category = ethers.id('Cardiology'); const all = ethers.id('ALL'); const recordId = ethers.id('opaque-record-1')

  it('blocks public admin escalation, unauthorized verification, and invalid staff roles', async () => {
    const { auth, outsider, doctor } = await fixture()
    await expect(auth.connect(outsider).registerStaff(outsider.address, 4)).to.be.revertedWith('ADMIN_REQUIRED')
    await expect(auth.connect(outsider).setVerified(doctor.address, false)).to.be.revertedWith('ADMIN_REQUIRED')
    await expect(auth.registerStaff(outsider.address, 1)).to.be.revertedWith('INVALID_STAFF_ROLE')
  })

  it('enforces consent ownership, bounded expiry, status, precedence, and separate write permission', async () => {
    const { patient, doctor, outsider, auth, consent } = await fixture(); const now = (await ethers.provider.getBlock('latest'))!.timestamp
    await expect(consent.connect(outsider).grantConsent(doctor.address, category, 1, now + 3600)).to.be.revertedWith('ACTIVE_PATIENT_REQUIRED')
    await expect(consent.connect(patient).grantConsent(doctor.address, category, 1, now)).to.be.revertedWith('INVALID_EXPIRY')
    await expect(consent.connect(patient).grantConsent(doctor.address, category, 1, now + 366 * 86400)).to.be.revertedWith('INVALID_EXPIRY')
    await consent.connect(patient).grantConsent(doctor.address, all, 2, now + 3600)
    await consent.connect(patient).grantConsent(doctor.address, category, 1, now + 1800)
    expect((await consent.resolveConsent(patient.address, doctor.address, category))[1]).to.equal(1)
    expect(await consent.canWrite(patient.address, doctor.address, category)).to.equal(false)
    await consent.connect(patient).revokeConsent(doctor.address, category)
    expect(await consent.canWrite(patient.address, doctor.address, category)).to.equal(true)
    await auth.setActive(doctor.address, false)
    expect(await consent.canRead(patient.address, doctor.address, category)).to.equal(false)
  })

  it('blocks forged audit writes and permits the normal read/write consent flow', async () => {
    const { patient, doctor, outsider, consent, audit } = await fixture(); const now = (await ethers.provider.getBlock('latest'))!.timestamp
    await expect(audit.connect(outsider).registerRecord(recordId, patient.address, ethers.id('envelope'), ethers.id('LOCAL'), category)).to.be.revertedWith('WRITE_CONSENT_REQUIRED')
    await audit.connect(patient).registerRecord(recordId, patient.address, ethers.id('envelope'), ethers.id('LOCAL'), category)
    await expect(audit.connect(doctor).logRecordAction(recordId, 1)).to.be.revertedWith('READ_CONSENT_REQUIRED')
    await consent.connect(patient).grantConsent(doctor.address, category, 1, now + 3600)
    await audit.connect(doctor).logRecordAction(recordId, 1)
    await expect(audit.connect(doctor).logRecordAction(recordId, 2)).to.be.revertedWith('WRITE_CONSENT_REQUIRED')
  })

  it('restricts opaque incident attestations to explicitly scoped service writers', async () => {
    const { owner, outsider, audit } = await fixture()
    await expect(audit.connect(outsider).attestIncident(ethers.id('incident'))).to.be.revertedWith('SERVICE_WRITER_REQUIRED')
    await audit.connect(owner).setServiceWriter(outsider.address,true)
    await expect(audit.connect(outsider).attestIncident(ethers.id('incident'))).to.emit(audit,'IncidentAttested')
  })

  it('binds emergency sessions to doctor, patient and record and invalidates rejection', async () => {
    const { patient, doctor, auditor, otherPatient, audit, emergency } = await fixture()
    await audit.connect(patient).registerRecord(recordId, patient.address, ethers.id('envelope'), ethers.id('LOCAL'), category)
    await expect(emergency.connect(doctor).open(otherPatient.address, recordId, ethers.id('reason'), 1)).to.be.revertedWith('PATIENT_RECORD_MISMATCH')
    await expect(emergency.connect(doctor).open(patient.address, recordId, ethers.id('reason'), 0)).to.be.revertedWith('INVALID_EMERGENCY_TYPE')
    await emergency.connect(doctor).open(patient.address, recordId, ethers.id('reason'), 1)
    expect(await emergency.isActive(0, doctor.address, patient.address, recordId)).to.equal(true)
    await emergency.connect(auditor).review(0, false)
    expect(await emergency.isActive(0, doctor.address, patient.address, recordId)).to.equal(false)
    const entry = await audit.auditAt(1); expect(entry.actor).to.equal(doctor.address)
  })

  it('treats the expiry instant as expired', async () => {
    const { patient, doctor, consent } = await fixture(); const now = (await ethers.provider.getBlock('latest'))!.timestamp
    await consent.connect(patient).grantConsent(doctor.address, category, 1, now + 60)
    await ethers.provider.send('evm_setNextBlockTimestamp', [now + 60]); await ethers.provider.send('evm_mine', [])
    expect(await consent.canRead(patient.address, doctor.address, category)).to.equal(false)
  })

  it('expires and explicitly revokes emergency sessions', async () => {
    const { patient, doctor, auditor, audit, emergency } = await fixture()
    await audit.connect(patient).registerRecord(recordId, patient.address, ethers.id('envelope'), ethers.id('LOCAL'), category)
    await emergency.connect(doctor).open(patient.address, recordId, ethers.id('reason-a'), 2)
    await emergency.connect(auditor).revoke(0)
    expect(await emergency.isActive(0, doctor.address, patient.address, recordId)).to.equal(false)
    await emergency.connect(doctor).open(patient.address, recordId, ethers.id('reason-b'), 3)
    const session = await emergency.sessions(1)
    await ethers.provider.send('evm_setNextBlockTimestamp', [Number(session.expiresAt)])
    await ethers.provider.send('evm_mine', [])
    expect(await emergency.isActive(1, doctor.address, patient.address, recordId)).to.equal(false)
  })
})
