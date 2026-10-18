import { artifacts, ethers, network } from 'hardhat'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

async function main() {
  if (network.config.chainId !== 31337) throw new Error('This deployment script is restricted to local chain ID 31337.')
  const [deployer, serviceWriter] = await ethers.getSigners()
  const Auth = await ethers.getContractFactory('HealerAuth'); const auth = await Auth.deploy(); await auth.waitForDeployment()
  const Consent = await ethers.getContractFactory('ConsentManager'); const consent = await Consent.deploy(await auth.getAddress()); await consent.waitForDeployment()
  const Audit = await ethers.getContractFactory('MedicalAuditRegistry'); const audit = await Audit.deploy(await auth.getAddress(), await consent.getAddress()); await audit.waitForDeployment()
  const BreakGlass = await ethers.getContractFactory('BreakGlassEmergency'); const breakGlass = await BreakGlass.deploy(await auth.getAddress(), await audit.getAddress()); await breakGlass.waitForDeployment()
  await (await audit.setEmergencyLogger(await breakGlass.getAddress(), true)).wait()
  await (await audit.setServiceWriter(serviceWriter.address, true)).wait()

  const names = ['HealerAuth', 'ConsentManager', 'MedicalAuditRegistry', 'BreakGlassEmergency'] as const
  const contracts = [auth, consent, audit, breakGlass]
  const outputs = [
    resolve(__dirname, '..', 'deployments', '31337'),
    resolve(__dirname, '..', '..', 'frontend', 'src', 'generated', 'contracts', '31337'),
    resolve(__dirname, '..', '..', 'backend', 'app', 'generated', 'contracts', '31337'),
  ]
  await Promise.all(outputs.map(output => mkdir(output, { recursive: true })))
  const manifest: Record<string, unknown> = { chainId: 31337, rpcUrl: 'http://127.0.0.1:8545', deployer: deployer.address, serviceWriter: serviceWriter.address, contracts: {} }
  for (let i = 0; i < names.length; i++) {
    const artifact = await artifacts.readArtifact(names[i]); const address = await contracts[i].getAddress()
    await Promise.all(outputs.map(output => writeFile(resolve(output, `${names[i]}.abi.json`), JSON.stringify(artifact.abi, null, 2))))
    ;(manifest.contracts as Record<string, unknown>)[names[i]] = { address, abi: `${names[i]}.abi.json` }
  }
  await Promise.all(outputs.map(output => writeFile(resolve(output, 'addresses.json'), JSON.stringify(manifest, null, 2))))
  console.log(JSON.stringify(manifest, null, 2))
}
main().catch(error => { console.error(error); process.exitCode = 1 })
