import { createPublicClient, createWalletClient, custom, defineChain, http, type Address, type Hash } from 'viem'
import consentAbi from './generated/contracts/31337/ConsentManager.abi.json'
import authAbi from './generated/contracts/31337/HealerAuth.abi.json'
import emergencyAbi from './generated/contracts/31337/BreakGlassEmergency.abi.json'

export const localChain = defineChain({ id: 31337, name: 'Hardhat Local', nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 }, rpcUrls: { default: { http: ['http://127.0.0.1:8545'] } } })
type EthereumProvider = Parameters<typeof custom>[0]
declare global { interface Window { ethereum?: EthereumProvider } }

export async function connectAndSign(message: string, expectedChain = 31337) {
  if (!window.ethereum) throw new Error('MetaMask is required for patient wallet signatures.')
  const wallet = createWalletClient({ chain: localChain, transport: custom(window.ethereum) })
  const [account] = await wallet.requestAddresses(); const chainId = await wallet.getChainId()
  if (chainId !== expectedChain) throw new Error(`Switch MetaMask to chain ${expectedChain}.`)
  return { account, signature: await wallet.signMessage({ account, message }) }
}
export async function requestWalletAddress(expectedChain = 31337) {
  if (!window.ethereum) throw new Error('MetaMask is required for patient wallet signatures.')
  const wallet = createWalletClient({ chain: localChain, transport: custom(window.ethereum) }); const [account] = await wallet.requestAddresses()
  if (await wallet.getChainId() !== expectedChain) throw new Error(`Switch MetaMask to chain ${expectedChain}.`)
  return account
}

export async function writeConsent(contract: Address, functionName: 'grantConsent'|'revokeConsent', args: readonly unknown[]): Promise<Hash> {
  if (!window.ethereum) throw new Error('MetaMask is required.')
  const wallet = createWalletClient({ chain: localChain, transport: custom(window.ethereum) }); const [account] = await wallet.requestAddresses()
  if (await wallet.getChainId() !== localChain.id) throw new Error(`Switch MetaMask to chain ${localChain.id}.`)
  const publicClient = createPublicClient({ chain: localChain, transport: http() })
  const simulated = await publicClient.simulateContract({ address: contract, abi: consentAbi, functionName, args, account })
  return wallet.writeContract(simulated.request)
}
export async function registerPatientWallet(contract: Address): Promise<Hash> {
  if (!window.ethereum) throw new Error('MetaMask is required.'); const wallet=createWalletClient({chain:localChain,transport:custom(window.ethereum)});const [account]=await wallet.requestAddresses();if(await wallet.getChainId()!==localChain.id)throw new Error(`Switch MetaMask to chain ${localChain.id}.`)
  const publicClient=createPublicClient({chain:localChain,transport:http()});const simulated=await publicClient.simulateContract({address:contract,abi:authAbi,functionName:'registerPatient',account});return wallet.writeContract(simulated.request)
}
export async function openEmergency(contract:Address,args:readonly unknown[]):Promise<Hash>{
  if(!window.ethereum)throw new Error('MetaMask is required.');const wallet=createWalletClient({chain:localChain,transport:custom(window.ethereum)});const[account]=await wallet.requestAddresses();if(await wallet.getChainId()!==localChain.id)throw new Error(`Switch MetaMask to chain ${localChain.id}.`);const client=createPublicClient({chain:localChain,transport:http()});const simulated=await client.simulateContract({address:contract,abi:emergencyAbi,functionName:'open',args,account});return wallet.writeContract(simulated.request)
}
