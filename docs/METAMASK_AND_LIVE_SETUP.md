# Local wallet and contract setup

Only local development is supported. Do not use a production wallet, recovery phrase, or public-network funds.

```powershell
cd blockchain
npm install
npm test
npm run node
```

Leave the node running. In a second terminal:

```powershell
cd blockchain
npm run deploy:local
```

The node listens on `http://127.0.0.1:8545` with chain ID `31337` and prints throwaway funded accounts. Deployment exports generated addresses and ABIs for the backend and frontend. Rebooting the node resets chain state; deploy again and use the newly generated manifest.

An Ethereum account signs local contract transactions only. It is not an RSA-OAEP record-decryption key. Browser record keys are created and recovered through the encrypted-record vault.
