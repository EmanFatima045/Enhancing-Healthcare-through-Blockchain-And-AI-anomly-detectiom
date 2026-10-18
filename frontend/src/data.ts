export const images = {
  authSignup: new URL('../assets/auth-signup-young-female-doctor.png', import.meta.url).href,
  authSignin: new URL('../assets/auth-signin-doctor-nurse.png', import.meta.url).href,
  staffDoctorMichael: new URL('../assets/staff-doctor-michael-reed.png', import.meta.url).href,
  staffDoctorAmelia: new URL('../assets/staff-doctor-amelia-brooks.png', import.meta.url).href,
  staffNurseChloe: new URL('../assets/staff-nurse-chloe-adams.png', import.meta.url).href,
  hospitalExterior: new URL('../assets/healerplus-hospital-exterior-v2.png', import.meta.url).href,
  hospitalPatientRoom: new URL('../assets/hospital-patient-room.png', import.meta.url).href,
  hero: new URL('../assets/homepage-dr-amelia-consultation-v3.png', import.meta.url).href,
  consultation: new URL('../assets/homepage-dr-emily-consultation-v2.png', import.meta.url).href,
  remoteMonitoring: new URL('../assets/remote-patient-monitoring-v2.png', import.meta.url).href,
  contactReception: new URL('../assets/contact-hospital-reception-v2.png', import.meta.url).href,
  family: new URL('../assets/homepage-american-patients.png', import.meta.url).href,
  nurse: new URL('../assets/auth-signin-doctor-nurse.png', import.meta.url).href,
  imaging: 'https://images.pexels.com/photos/7088838/pexels-photo-7088838.jpeg?auto=compress&cs=tinysrgb&w=1400',
  corridor: 'https://images.pexels.com/photos/668300/pexels-photo-668300.jpeg?auto=compress&cs=tinysrgb&w=1400',
  reception: 'https://images.pexels.com/photos/263402/pexels-photo-263402.jpeg?auto=compress&cs=tinysrgb&w=1400',
  patientRoom: 'https://images.pexels.com/photos/236380/pexels-photo-236380.jpeg?auto=compress&cs=tinysrgb&w=1400',
  team: new URL('../assets/professionals-team-hero-v2.png', import.meta.url).href,
  doctorMale: 'https://images.pexels.com/photos/6129452/pexels-photo-6129452.jpeg?auto=compress&cs=tinysrgb&w=1000',
  doctorFemale: new URL('../assets/auth-signup-young-female-doctor.png', import.meta.url).href,
  doctorCare: 'https://images.pexels.com/photos/6129648/pexels-photo-6129648.jpeg?auto=compress&cs=tinysrgb&w=1000',
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
  { slug: 'amelia-brooks', name: 'Dr. Amelia Brooks', specialty: 'Diagnostic Medicine Physician', image: images.staffDoctorAmelia, bio: 'Fictional demonstration profile awaiting verified team information from Healer Mobile Care.' },
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
