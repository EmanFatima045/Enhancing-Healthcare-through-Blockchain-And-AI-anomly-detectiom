export type ImageMetadata = { srcSet: string; width: number; height: number }

const imageMetadata = new Map<string, ImageMetadata>()
const optimizedAssets = import.meta.glob('../assets/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>
const image = (src: string, sources: Array<[string, number]>, width: number, height: number) => {
  imageMetadata.set(src, { srcSet: sources.map(([url, size]) => `${url} ${size}w`).join(', '), width, height })
  return src
}
const url = (path: string) => {
  const resolved = optimizedAssets[path]
  if (!resolved) throw new Error(`Missing optimized image asset: ${path}`)
  return resolved
}
const landscape = (stem: string, height: number) => image(
  url(`../assets/${stem}-1280.webp`),
  [[url(`../assets/${stem}-640.webp`), 640], [url(`../assets/${stem}-960.webp`), 960], [url(`../assets/${stem}-1280.webp`), 1280]],
  1280,
  height,
)
const portrait = (stem: string) => image(
  url(`../assets/${stem}-1024.webp`),
  [[url(`../assets/${stem}-480.webp`), 480], [url(`../assets/${stem}-800.webp`), 800], [url(`../assets/${stem}-1024.webp`), 1024]],
  1024,
  1536,
)

const authSignup = portrait('auth-signup-young-female-doctor')
const authSignin = portrait('auth-signin-doctor-nurse')
const staffDoctorMichael = portrait('staff-doctor-michael-reed')
const staffDoctorAmelia = portrait('staff-doctor-amelia-brooks')
const staffNurseChloe = portrait('staff-nurse-chloe-adams')
const hospitalExterior = landscape('healerplus-hospital-exterior-v2', 640)
const hospitalPatientRoom = landscape('hospital-patient-room', 853)
const hero = landscape('homepage-dr-amelia-consultation-v3', 720)
const consultation = landscape('homepage-dr-emily-consultation-v2', 720)
const remoteMonitoring = landscape('remote-patient-monitoring-v2', 720)
const contactReception = landscape('contact-hospital-reception-v2', 720)
const family = landscape('homepage-american-patients', 640)
const corridor = landscape('hospital-exterior', 720)
const team = landscape('professionals-team-hero-v2', 720)
const logo = image(url('../assets/healer-health-care-logo-128.webp'), [], 128, 128)

export const getImageMetadata = (src: string) => imageMetadata.get(src)

export const images = {
  logo,
  authSignup,
  authSignin,
  staffDoctorMichael,
  staffDoctorAmelia,
  staffNurseChloe,
  hospitalExterior,
  hospitalPatientRoom,
  hero,
  consultation,
  remoteMonitoring,
  contactReception,
  family,
  nurse: authSignin,
  imaging: hospitalPatientRoom,
  corridor,
  reception: contactReception,
  patientRoom: hospitalPatientRoom,
  team,
  doctorMale: staffDoctorMichael,
  doctorFemale: authSignup,
  doctorCare: staffNurseChloe,
}

export const services = [
  { slug: 'secure-health-records', title: 'Secure Health Records', category: 'Digital care', summary: 'Patient-controlled access to encrypted clinical records with a verifiable audit trail.', image: images.consultation },
  { slug: 'remote-patient-monitoring', title: 'Remote Patient Monitoring', category: 'Connected care', summary: 'Live IoMT telemetry with transparent anomaly detection and clinician-ready signals.', image: images.remoteMonitoring },
  { slug: 'clinical-consultation', title: 'Clinical Consultation', category: 'Patient care', summary: 'A calm, coordinated consultation experience built around clarity and informed consent.', image: images.family },
  { slug: 'diagnostic-imaging', title: 'Diagnostic Imaging', category: 'Diagnostics', summary: 'Privacy-aware diagnostic workflows supporting secure review and controlled sharing.', image: images.imaging },
]

export const professionals = [
  { slug: 'emily-carter', name: 'Dr. Emily Carter', specialty: 'Internal Medicine Physician', image: images.doctorFemale, bio: 'Fictional demonstration profile. Replace with a verified clinician name, registration, qualifications, and approved biography before launch.' },
  { slug: 'james-walker', name: 'Dr. James Walker', specialty: 'Cardiology Physician', image: images.doctorMale, bio: 'Fictional demonstration profile representing connected cardiac care. No real clinician identity or credential is claimed.' },
  { slug: 'amelia-brooks', name: 'Dr. Amelia Brooks', specialty: 'Diagnostic Medicine Physician', image: images.staffDoctorAmelia, bio: 'Fictional demonstration profile awaiting verified team information from HealerPlus.' },
  { slug: 'sophia-bennett', name: 'Sophia Bennett, RN', specialty: 'Patient Care Nurse', image: images.doctorCare, bio: 'Fictional demonstration nursing profile. Replace with verified staff information before public launch.' },
  { slug: 'michael-reed', name: 'Dr. Michael Reed', specialty: 'Family Medicine Physician', image: images.staffDoctorMichael, bio: 'Fictional demonstration profile created for the interface. It is not a real staff listing.' },
  { slug: 'chloe-adams', name: 'Chloe Adams, RN', specialty: 'Clinical Care Nurse', image: images.staffNurseChloe, bio: 'Fictional demonstration profile created for the interface. It is not a real staff listing.' },
]

export const faqs = [
  ['Is this a live clinical service?', 'This installation is an academic healthcare-security platform and local demonstration. It must not be used for emergencies or real clinical decisions.'],
  ['Can I confirm an appointment online?', 'You can submit a preferred appointment request. It remains pending until a real provider, schedule, database, and notification service are configured.'],
  ['How are health records protected?', 'The local API demonstrates encryption and AI-assisted anomaly detection. Blockchain anchoring and IPFS pinning remain disabled until real infrastructure is configured.'],
  ['Are the professionals shown real Healer clinicians?', 'No. The named staff profiles are clearly labeled fictional demonstrations until verified team names and credentials are supplied.'],
  ['Are the facility photographs actual Healer premises?', 'No. They are illustrative healthcare images and are labeled as such.'],
]
